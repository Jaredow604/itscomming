import os
import django
import pandas as pd
import requests
from io import StringIO

# Configurar entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from predicciones.models import Equipos, Partido

def poblar_historial():
    # Temporadas a descargar: 21/22, 22/23, 23/24, 24/25 y la actual 25/26
    seasons = ['2122', '2223', '2324', '2425', '2526']
    base_url = "https://www.football-data.co.uk/mmz4281/{}/E0.csv" # E0 = Premier League

    print("🚀 Iniciando descarga de 5 temporadas de H2H...")

    for s in seasons:
        url = base_url.format(s)
        print(f"--- Procesando Temporada {s} ---")
        
        response = requests.get(url)
        if response.status_code != 200:
            print(f"❌ No se pudo descargar la temporada {s}")
            continue

        df = pd.read_csv(StringIO(response.text))
        
        # Columnas que nos importan: HomeTeam, AwayTeam, FTHG (Goles Local), FTAG (Goles Visita), Date
        df = df[['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']]

        for _, row in df.iterrows():
            try:
                # 1. Buscar o Crear Equipos (Normalización de nombres)
                loc_name = row['HomeTeam']
                vis_name = row['AwayTeam']
                
                equipo_l, _ = Equipos.objects.get_or_create(nombre=loc_name)
                equipo_v, _ = Equipos.objects.get_or_create(nombre=vis_name)

                # 2. Crear el partido histórico
                # Usamos update_or_create para no duplicar si corres el script dos veces
                Partido.objects.update_or_create(
                    local=equipo_l,
                    visitante=equipo_v,
                    fecha_str=row['Date'], # Guardamos la fecha del CSV
                    defaults={
                        'goles_local': int(row['FTHG']),
                        'goles_visitante': int(row['FTAG']),
                        'jugado': True
                    }
                )
            except Exception as e:
                continue # Algunos CSV tienen filas vacías al final

    print("✅ ¡Historial de 5 años cargado con éxito!")

if __name__ == "__main__":
    poblar_historial()