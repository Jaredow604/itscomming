"""
Management command: orquestar_normalizacion

Orquestaci?n completa de normalizaci?n de entidades entre Django ORM
(predicciones_equipos) y SQLAlchemy (equipos).

Flujo:
  Fase 1 ? Construir puente EquipoMapping (Django Equipos <-> SQLAlchemy Team)
  Fase 2 ? Migrar datos FBref desde SQLAlchemy hacia Django
  Fase 3 ? Poblar FK en modelos Django (run normalizar_fk_equipos)
  Fase 4 ? Poblar FK en modelos SQLAlchemy (run vincular_estadisticas_globales)
  Fase 5 ? Reporte de hu?rfanos y cobertura

Uso:
  python manage.py orquestar_normalizacion
  python manage.py orquestar_normalizacion --fase 1
  python manage.py orquestar_normalizacion --dry-run
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.db import transaction
from rapidfuzz import fuzz, process
from database import SessionLocal
from src.data.models import Team as SATeam
from src.data.models import (
    FBrefTeamStats as SAFBrefTeamStats,
    FBrefPlayerStats as SAFBrefPlayerStats,
)

from predicciones.models import (
    Equipos, EquipoMapping, EntidadHuerfana,
    FBrefTeamStats, FBrefPlayerStats, FBrefShootingStats,
)
from predicciones.entity_resolver import clean_team_name

logger = logging.getLogger('orquestar_normalizacion')

UMBRAL_FUZZY = 85


# ==========================================
# FASE 1 ? PUENTE EQUIPO MAPPING
# ==========================================

class FasePuente:
    """
    Construye EquipoMapping haciendo fuzzy match entre
    Django Equipos (predicciones_equipos) y SQLAlchemy Team (equipos).
    """

    def __init__(self, stdout, verbosity, dry_run=False):
        self.stdout = stdout
        self.verbosity = verbosity
        self.dry_run = dry_run

    def log(self, msg):
        if self.verbosity >= 1:
            self.stdout.write(msg)

    def ejecutar(self) -> dict:
        self.log('\n=== FASE 1: Puente EquipoMapping ===')

        if self.dry_run:
            self.log('  Dry-run: se leerian Django Equipos + SQLAlchemy Team')
            self.log('  y se crearian registros EquipoMapping por fuzzy match.')
            return {
                'creados': 0, 'huerfanos_django': [], 'huerfanos_sa': []
            }

        session = SessionLocal()
        try:
            equipos_django = list(Equipos.objects.all())
            equipos_sa: list[SATeam] = session.query(SATeam).all()

            self.log(f'  Django Equipos: {len(equipos_django)}')
            self.log(f'  SQLAlchemy Team: {len(equipos_sa)}')

            choices_sa = {
                t.id_equipo: clean_team_name(t.nombre)
                for t in equipos_sa if t.nombre
            }

            creados = 0
            huerfanos_django = []
            huerfanos_sa = []

            for eq_django in equipos_django:
                nombre_limpio = clean_team_name(eq_django.nombre)

                # Paso 1 ? iexact
                sa_match = session.query(SATeam).filter(
                    SATeam.nombre == eq_django.nombre
                ).first()
                if sa_match:
                    self._crear_o_actualizar_mapping(
                        eq_django, sa_match, 100.0
                    )
                    creados += 1
                    continue

                # Paso 2 ? icontains
                sa_match = session.query(SATeam).filter(
                    SATeam.nombre.ilike(f'%{eq_django.nombre}%')
                ).first()
                if sa_match:
                    self._crear_o_actualizar_mapping(
                        eq_django, sa_match, 95.0
                    )
                    creados += 1
                    continue

                # Paso 3 ? fuzzy
                match = process.extractOne(
                    nombre_limpio, choices_sa,
                    scorer=fuzz.token_sort_ratio,
                    score_cutoff=UMBRAL_FUZZY,
                )
                if match:
                    _, score, sa_id = match
                    sa_match = session.query(SATeam).get(sa_id)
                    self._crear_o_actualizar_mapping(
                        eq_django, sa_match, float(score)
                    )
                    creados += 1
                    continue

                huerfanos_django.append(eq_django.nombre)

            # Detectar equipos SQLAlchemy sin mapping
            sa_ids_mapped = set(
                EquipoMapping.objects.values_list(
                    'sqlalchemy_equipo_id', flat=True
                )
            )
            for sa_team in equipos_sa:
                if sa_team.id_equipo not in sa_ids_mapped:
                    huerfanos_sa.append(sa_team.nombre)

            self.log(f'  Mapping creados: {creados}')
            if huerfanos_django:
                self.log(
                    f'  [!]  Django sin match SA: {len(huerfanos_django)} -> '
                    f'{huerfanos_django[:5]}...'
                )
            if huerfanos_sa:
                self.log(
                    f'  [!]  SQLAlchemy sin match Django: {len(huerfanos_sa)} -> '
                    f'{huerfanos_sa[:5]}...'
                )

            return {
                'creados': creados,
                'huerfanos_django': huerfanos_django,
                'huerfanos_sa': huerfanos_sa,
            }

        finally:
            session.close()

    def _crear_o_actualizar_mapping(
        self, eq_django: Equipos, sa_team: SATeam, confianza: float
    ):
        if self.dry_run:
            return
        EquipoMapping.objects.update_or_create(
            sqlalchemy_equipo_id=sa_team.id_equipo,
            defaults={
                'django_equipo': eq_django,
                'sqlalchemy_equipo_nombre': sa_team.nombre,
                'confianza': confianza,
            },
        )


# ==========================================
# FASE 2 ? MIGRAR FBref DE SQLALCHEMY A DJANGO
# ==========================================

class FaseMigrarFBref:
    """
    Copia datos desde las tablas SQLAlchemy fbref_* hacia los nuevos
    modelos Django predicciones_fbrefteamstats / fbrefplayerstats.
    Resuelve FK usando EquipoMapping.
    """

    TABLAS = [
        ('FBrefTeamStats', SAFBrefTeamStats, FBrefTeamStats),
        ('FBrefPlayerStats', SAFBrefPlayerStats, FBrefPlayerStats),
    ]

    def __init__(self, stdout, verbosity, dry_run=False):
        self.stdout = stdout
        self.verbosity = verbosity
        self.dry_run = dry_run

    def log(self, msg):
        if self.verbosity >= 1:
            self.stdout.write(msg)

    def ejecutar(self):
        self.log('\n=== FASE 2: Migrar FBref SQLAlchemy -> Django ===')

        if self.dry_run:
            self.log('  Dry-run: se migrarian datos de fbref_team_stats')
            self.log('  y fbref_player_stats a modelos Django.')
            return

        mapping_sa_id = {
            m.sqlalchemy_equipo_id: m.django_equipo_id
            for m in EquipoMapping.objects.all()
        }

        session = SessionLocal()
        try:
            for nombre, sa_model, dj_model in self.TABLAS:
                self._migrar_tabla(
                    nombre, sa_model, dj_model, mapping_sa_id, session
                )
        finally:
            session.close()

    def _migrar_tabla(
        self, nombre, sa_model, dj_model, mapping_sa_id, session
    ):
        registros_sa = session.query(sa_model).all()
        self.log(f'\n  [DATOS] {nombre}: {len(registros_sa)} registros en SQLAlchemy')

        if not registros_sa:
            self.log(f'  -> Sin datos para migrar.')
            return

        if self.dry_run:
            self.log(f'  -> Dry-run: se migrar?an {len(registros_sa)} registros.')
            return

        creados = saltados = 0

        for sa_row in registros_sa:
            kwargs = {}
            if hasattr(sa_row, 'league'):
                kwargs['league'] = sa_row.league
            if hasattr(sa_row, 'season'):
                kwargs['season'] = sa_row.season

            # Mapear FK de equipo
            equipo_fk = None
            sa_eq_id = getattr(sa_row, 'equipo_fk', None)
            if sa_eq_id and sa_eq_id in mapping_sa_id:
                equipo_fk_id = mapping_sa_id[sa_eq_id]
                kwargs['equipo_id'] = equipo_fk_id

            if nombre == 'FBrefTeamStats':
                kwargs['team'] = getattr(sa_row, 'team', None)
            elif nombre == 'FBrefPlayerStats':
                kwargs['nombre_jugador'] = getattr(
                    sa_row, 'nombre_jugador', None
                )
                kwargs['team_name'] = getattr(sa_row, 'team_name', None)

            # Evitar duplicados: buscar por campos clave
            exists = self._ya_existe(dj_model, kwargs)
            if exists:
                saltados += 1
                continue

            dj_model.objects.create(**kwargs)
            creados += 1

        self.log(
            f'  -> Creados: {creados} | Saltados (dup): {saltados}'
        )

    def _ya_existe(self, dj_model, kwargs: dict) -> bool:
        if dj_model == FBrefTeamStats:
            team = kwargs.get('team')
            if team:
                return dj_model.objects.filter(team=team).exists()
        elif dj_model == FBrefPlayerStats:
            nombre = kwargs.get('nombre_jugador')
            if nombre:
                return dj_model.objects.filter(
                    nombre_jugador=nombre
                ).exists()
        return False


# ==========================================
# FASE 3 ? POBLAR FK EN DJANGO
# ==========================================

class FaseFKDjango:
    """
    Ejecuta normalizar_fk_equipos internamente para poblar
    los FK que a?n no se resolvieron v?a EquipoMapping.
    """

    def __init__(self, stdout, verbosity, dry_run=False):
        self.stdout = stdout
        self.verbosity = verbosity
        self.dry_run = dry_run

    def log(self, msg):
        if self.verbosity >= 1:
            self.stdout.write(msg)

    def ejecutar(self):
        self.log('\n=== FASE 3: Poblar FK Django ===')
        if self.dry_run:
            self.log('  Dry-run: se ejecutar?a normalizar_fk_equipos')
            return

        call_command('normalizar_fk_equipos', verbosity=self.verbosity)


# ==========================================
# FASE 4 ? POBLAR FK EN SQLALCHEMY
# ==========================================

class FaseFKSQLAlchemy:
    """
    Ejecuta vincular_estadisticas_globales internamente.
    """

    def __init__(self, stdout, verbosity, dry_run=False):
        self.stdout = stdout
        self.verbosity = verbosity
        self.dry_run = dry_run

    def log(self, msg):
        if self.verbosity >= 1:
            self.stdout.write(msg)

    def ejecutar(self):
        self.log('\n=== FASE 4: Poblar FK SQLAlchemy ===')
        if self.dry_run:
            self.log('  Dry-run: se ejecutar?a vincular_estadisticas_globales')
            return

        call_command('vincular_estadisticas_globales', verbosity=self.verbosity)


# ==========================================
# FASE 5 ? REPORTE
# ==========================================

class FaseReporte:
    """
    Reporte consolidado de cobertura de FK y hu?rfanos.
    """

    def __init__(self, stdout, verbosity, dry_run=False):
        self.stdout = stdout
        self.verbosity = verbosity
        self.dry_run = dry_run

    def _pct(self, parte, total):
        if total == 0:
            return 0.0
        return round(parte / total * 100, 1)

    def ejecutar(self):
        self.stdout.write('\n=== FASE 5: Reporte de Normalizacion ===')

        if self.dry_run:
            self.stdout.write('  Dry-run: reporte omitido (ejecutar sin --dry-run).')
            return

        total = seen = 0
        for label, qs, fk_field in [
            ('DailySchedule.home_team_fk', FBrefTeamStats.objects, 'equipo'),
            ('DailySchedule.away_team_fk', FBrefPlayerStats.objects, 'equipo'),
            ('FBrefTeamStats.equipo', FBrefTeamStats.objects, 'equipo'),
            ('FBrefPlayerStats.equipo', FBrefPlayerStats.objects, 'equipo'),
            ('FBrefShootingStats.equipo', FBrefShootingStats.objects, 'equipo'),
        ]:
            total_registros = qs.count()
            if total_registros == 0:
                continue
            fk = {
                k: v for k, v in
                qs.values_list(fk_field).distinct()
            }
            con_fk = qs.exclude(**{f'{fk_field}__isnull': True}).count()
            sin_fk = total_registros - con_fk
            total += total_registros
            if sin_fk == 0 and con_fk > 0:
                seen += 1

            self.stdout.write(
                f'  {label}: {con_fk}/{total_registros} '
                f'({self._pct(con_fk, total_registros)}%) '
                f'{"[OK]" if sin_fk == 0 else f"[!]  {sin_fk} pendientes"}'
            )

        huerfanos = EntidadHuerfana.objects.filter(resuelto=False).count()
        if huerfanos:
            self.stdout.write(
                f'\n  ?  EntidadesHu?rfanas no resueltas: {huerfanos}'
            )
            top_10 = EntidadHuerfana.objects.filter(
                resuelto=False
            ).values_list('nombre_crudo', flat=True)[:10]
            self.stdout.write(f'      Top 10: {list(top_10)}')

        mappings = EquipoMapping.objects.count()
        self.stdout.write(f'\n  ?  EquipoMapping activos: {mappings}')

        self.stdout.write(
            self.style.SUCCESS(
                f'\n[OK] Orquestaci?n completada. '
                f'Tablas vistas: {seen}/{5} con 100% cobertura.'
            )
        )


# ==========================================
# COMANDO PRINCIPAL
# ==========================================

FASES = {
    1: ('Puente Django <-> SQLAlchemy', FasePuente),
    2: ('Migrar FBref SA -> Django', FaseMigrarFBref),
    3: ('FK en Django', FaseFKDjango),
    4: ('FK en SQLAlchemy', FaseFKSQLAlchemy),
    5: ('Reporte', FaseReporte),
}


class Command(BaseCommand):
    help = (
        'Orquestaci?n completa: construye el puente EquipoMapping entre '
        'Django y SQLAlchemy, migra datos FBref, pobla FK en ambos ORMs '
        'y genera reporte de cobertura.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--fase',
            type=int,
            choices=list(FASES),
            help='Ejecutar solo una fase espec?fica (1-5).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular sin escribir en BD.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbosity = options['verbosity']
        fase_objetivo = options['fase']

        fases_a_ejecutar = (
            [fase_objetivo] if fase_objetivo else sorted(FASES)
        )

        for num_fase in fases_a_ejecutar:
            nombre, cls = FASES[num_fase]

            if dry_run:
                self.stdout.write(
                    f'\n[FASE] Fase {num_fase}: {nombre} [DRY-RUN]'
                )
            else:
                self.stdout.write(
                    f'\n[FASE] Fase {num_fase}: {nombre}'
                )

            instancia = cls(
                stdout=self.stdout,
                verbosity=verbosity,
                dry_run=dry_run,
            )
            instancia.ejecutar()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    '\n[!]  Dry-run completado. '
                    'Ejecuta sin --dry-run para aplicar cambios.'
                )
            )
