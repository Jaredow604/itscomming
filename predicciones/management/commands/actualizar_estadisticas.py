from django.core.management.base import BaseCommand
import pandas as pd
from predicciones.models import Equipos

class Command(BaseCommand):
    help = 'Descarga estadísticas detalladas de la Premier League y actualiza los promedios'

    def handle(self, *args, **kwargs):
        self.stdout.write('Descargando base de datos completa de la Premier League (Temporada 25/26)...')

        # URL directa al archivo CSV de la Premier League (E0 = English Premier League)
        url_csv = "https://www.football-data.co.uk/mmz4281/2526/E0.csv"

        try:
            # Pandas lee el archivo directamente desde internet
            df = pd.read_csv(url_csv)
            self.stdout.write(self.style.SUCCESS(f'¡Datos descargados! {len(df)} partidos analizados.'))

            # Extraemos la lista de todos los equipos únicos
            equipos_unicos = set(df['HomeTeam'].unique()) | set(df['AwayTeam'].unique())

            for nombre_equipo in equipos_unicos:
                # 1. Filtrar partidos de Local
                df_local = df[df['HomeTeam'] == nombre_equipo]
                goles_local = df_local['FTHG'].sum()  # FTHG: Full Time Home Goals
                corners_local = df_local['HC'].sum()  # HC: Home Corners
                tiros_local = df_local['HST'].sum()   # HST: Home Shots on Target

                # 2. Filtrar partidos de Visitante
                df_visita = df[df['AwayTeam'] == nombre_equipo]
                goles_visita = df_visita['FTAG'].sum() # FTAG: Full Time Away Goals
                corners_visita = df_visita['AC'].sum() # AC: Away Corners
                tiros_visita = df_visita['AST'].sum()  # AST: Away Shots on Target

                # 3. Calcular totales y promedios
                total_partidos = len(df_local) + len(df_visita)

                if total_partidos > 0:
                    prom_goles = (goles_local + goles_visita) / total_partidos
                    prom_corners = (corners_local + corners_visita) / total_partidos
                    prom_tiros = (tiros_local + tiros_visita) / total_partidos

                    # 4. Guardar en la base de datos de Django
                    equipo, creado = Equipos.objects.update_or_create(
                        nombre=nombre_equipo,
                        defaults={
                            'prom_goles': round(prom_goles, 2),
                            'prom_corners': round(prom_corners, 2),
                            'prom_tiros_puerta': round(prom_tiros, 2)
                        }
                    )

                    estado = "✨ Creado" if creado else "🔄 Actualizado"
                    self.stdout.write(f'{estado}: {nombre_equipo} | Goles: {round(prom_goles,2)} | Córners: {round(prom_corners,2)}')

            self.stdout.write(self.style.SUCCESS('¡Toda la base de datos ha sido actualizada con estadísticas reales!'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ocurrió un error al procesar los datos: {e}'))