import logging
from django.core.management.base import BaseCommand
from predicciones.models import Equipos, EntidadHuerfana, AliasEquipo
# Importamos el resolver que ya habías construido (ajusta la ruta si es necesario)
from src.data_processing.entity_resolver import EntityResolver
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from django.conf import settings

logger = logging.getLogger("Normalizacion")

class Command(BaseCommand):
    help = "Normaliza entidades huérfanas vinculándolas a los equipos maestros"

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Iniciando normalización de llaves foráneas y entidades huérfanas..."))

        # Conectar SQLAlchemy para usar tu EntityResolver (usando la BD de Django)
        # Asumiendo SQLite por tu estructura (db.sqlite3). Si usas PostgreSQL, cambia este string.
        engine = create_engine(f"sqlite:///{settings.DATABASES['default']['NAME']}")
        session = Session(engine)
        resolver = EntityResolver(session)

        # 1. Obtener entidades no resueltas
        huerfanos = EntidadHuerfana.objects.filter(resuelto=False)
        total_huerfanos = huerfanos.count()

        if total_huerfanos == 0:
            self.stdout.write(self.style.SUCCESS("No hay entidades huérfanas por normalizar."))
            return

        self.stdout.write(f"Procesando {total_huerfanos} entidades...")
        
        vinculados = 0
        nuevos_equipos = 0

        for huerfano in huerfanos:
            nombre_crudo = huerfano.nombre_crudo
            try:
                # 2. Pasarlo por tu EntityResolver
                # Tu resolver usa string matching y retorna el ID del equipo (existente o nuevo)
                id_central = resolver.resolve_team(name=nombre_crudo)
                
                # 3. Traer la instancia de Django
                equipo_maestro = Equipos.objects.get(id=id_central) # O id_equipo, dependiendo de tu primary key en SQLAlchemy
                
                # 4. Crear el Alias para que la próxima vez pase directo
                AliasEquipo.objects.get_or_create(
                    nombre_fuente=nombre_crudo,
                    defaults={'equipo': equipo_maestro}
                )

                # 5. Marcar como resuelto
                huerfano.resuelto = True
                huerfano.save()
                
                vinculados += 1
                self.stdout.write(self.style.SUCCESS(f"Vinculado: '{nombre_crudo}' -> '{equipo_maestro.nombre}'"))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error procesando '{nombre_crudo}': {str(e)}"))

        # Commit final para SQLAlchemy si el resolver hizo cambios
        session.commit()

        self.stdout.write(self.style.SUCCESS(
            f"Normalización completa. {vinculados} entidades vinculadas exitosamente."
        ))