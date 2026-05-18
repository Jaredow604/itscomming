import logging
from django.core.management.base import BaseCommand
import sys
import os

# Importamos las rutinas de ingesta de datos
# Al estar en un management command, Django ya está inicializado.
from importar_h2h import poblar_historial
from actualizar_stats import actualizar_promedios

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Ejecuta el pipeline automatizado de ingesta de datos (Stats, Momios y H2H)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando Pipeline de Ingesta 'Bare Metal'..."))
        
        # 1. Ingesta de H2H (Importar datos históricos o recientes)
        try:
            self.stdout.write("Ejecutando extraer_historial (H2H)...")
            poblar_historial()
            self.stdout.write(self.style.SUCCESS("✅ Datos H2H extraídos y actualizados exitosamente."))
        except Exception as e:
            logger.error(f"Fallo crítico en importar_h2h: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f"❌ Error en H2H: {e}"))

        # 2. Actualización de Promedios y Estadísticas (Stats)
        try:
            self.stdout.write("Ejecutando actualizar_stats...")
            actualizar_promedios()
            self.stdout.write(self.style.SUCCESS("✅ Estadísticas y promedios calculados exitosamente."))
        except Exception as e:
            logger.error(f"Fallo crítico en actualizar_stats: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f"❌ Error en Estadísticas: {e}"))

        self.stdout.write(self.style.SUCCESS("Pipeline Finalizado."))
