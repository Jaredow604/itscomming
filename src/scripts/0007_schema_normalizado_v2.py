"""
0007_schema_normalizado_v2.py — Migración Django para el Esquema Normalizado v2.0

Cambios respecto a versiones anteriores:
  - Partido: agrega UniqueConstraint (local, visitante, fecha) y campo fstatus
  - Equipos: elimina prom_goles/corners/tiros (ahora son calculados en TeamRollingStats)
             los campos se MANTIENEN en la tabla para compatibilidad con Django ORM y UI,
             pero el modelo ML ya no los lee directamente.
  - AliasEquipo: migrada a alias_equipos (nombre de tabla consistente)
  - DailySchedule: agrega FKs opcionales a equipos

NOTA: Esta migración es ADITIVA. No elimina datos existentes.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('predicciones', '0006_remove_equipos_logo_url'),
    ]

    operations = [

        # ── 1. Agregar logo_url a Equipos ──────────────────────────────────
        migrations.AddField(
            model_name='equipos',
            name='logo_url',
            field=models.CharField(max_length=500, null=True, blank=True),
        ),

        # ── 2. Agregar fstatus a Partido ───────────────────────────────────
        migrations.AddField(
            model_name='partido',
            name='fstatus',
            field=models.CharField(max_length=50, default='Fixture', null=True, blank=True),
        ),

        # ── 3. UniqueConstraint en Partido (local + visitante + fecha) ──────
        # Evita duplicados cuando el scraper corre múltiples veces
        migrations.AlterUniqueTogether(
            name='partido',
            unique_together={('local', 'visitante', 'fecha')},
        ),

        # ── 4. Agregar FKs opcionales a DailySchedule ─────────────────────
        migrations.AddField(
            model_name='dailyschedule',
            name='equipo_local',
            field=models.ForeignKey(
                to='predicciones.Equipos',
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='schedules_local',
                null=True, blank=True
            ),
        ),
        migrations.AddField(
            model_name='dailyschedule',
            name='equipo_visitante',
            field=models.ForeignKey(
                to='predicciones.Equipos',
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='schedules_visitante',
                null=True, blank=True
            ),
        ),

        # ── 5. UniqueConstraint en DailySchedule ──────────────────────────
        migrations.AlterUniqueTogether(
            name='dailyschedule',
            unique_together={('sport', 'home_team', 'away_team', 'match_date')},
        ),
    ]
