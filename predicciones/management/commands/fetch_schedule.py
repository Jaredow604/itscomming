import os
import datetime
import requests
import logging
from django.core.management.base import BaseCommand
from predicciones.models import DailySchedule

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Fetches daily schedule for MLB, NBA, and Soccer using The Odds API.'

    def handle(self, *args, **kwargs):
        hoy = datetime.date.today()
        self.stdout.write(self.style.SUCCESS(f"Ejecutando ETL de Schedule con The Odds API para la fecha: {hoy}"))
        
        api_key = os.getenv('ODDS_API_KEY')
        if not api_key:
            self.stdout.write(self.style.ERROR("ODDS_API_KEY no encontrada en el entorno."))
            return

        nuevos_partidos = []

        sports_map = {
            'nba': ['basketball_nba'],
            'mlb': ['baseball_mlb'],
            'soccer': [
                'soccer_epl',            # Premier League
                'soccer_spain_la_liga',  # La Liga
                'soccer_uefa_champs_league', # UCL
                'soccer_mexico_ligamx',  # Liga MX
            ]
        }

        # The Odds API endpoint
        base_url = "https://api.the-odds-api.com/v4/sports/{sport}/events"

        for app_sport, api_sports in sports_map.items():
            count = 0
            for api_sport in api_sports:
                self.stdout.write(f"Obteniendo datos de {api_sport}...")
                params = {
                    'apiKey': api_key,
                    'commenceTimeFrom': f"{hoy}T00:00:00Z",
                    'commenceTimeTo': f"{hoy}T23:59:59Z",
                }
                
                try:
                    url = base_url.format(sport=api_sport)
                    response = requests.get(url, params=params, timeout=10)
                    if response.status_code == 200:
                        events = response.json()
                        for ev in events:
                            home = ev.get('home_team')
                            away = ev.get('away_team')
                            commence_time_str = ev.get('commence_time')
                            
                            if not home or not away or not commence_time_str:
                                continue
                                
                            try:
                                dt = datetime.datetime.strptime(commence_time_str, '%Y-%m-%dT%H:%M:%SZ')
                                start_time = dt.time()
                            except ValueError:
                                start_time = None
                                
                            nuevos_partidos.append(DailySchedule(
                                sport=app_sport,
                                home_team=home,
                                away_team=away,
                                match_date=hoy,
                                start_time=start_time
                            ))
                            count += 1
                    else:
                        self.stdout.write(self.style.WARNING(f"API Error {response.status_code}: {response.text}"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error extrayendo {api_sport}: {e}"))
            
            self.stdout.write(self.style.SUCCESS(f"-> OK {app_sport.upper()}: {count} partidos encontrados para hoy."))

        # ORQUESTACIÓN DB
        try:
            DailySchedule.objects.filter(match_date=hoy).delete()
            if nuevos_partidos:
                DailySchedule.objects.bulk_create(nuevos_partidos)
                self.stdout.write(self.style.SUCCESS(f"ETL Exitoso: Guardados {len(nuevos_partidos)} partidos totales en DailySchedule para {hoy}."))
            else:
                self.stdout.write(self.style.WARNING("No se encontró ningún partido activo para hoy en The Odds API."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error fatal guardando transacciones DB: {e}"))

