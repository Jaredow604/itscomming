import pandas as pd
from sqlalchemy import create_engine
import time
from datetime import datetime

from src.data_ingestion.apis.nba_client import NBAClient

def run_nba_backfill(temporadas=None):
    """
    Backfill historico de NBA con soporte multi-temporada.

    Args:
        temporadas: Lista de temporadas. Default: ["2023-24", "2024-25", "2025-26"]
    """
    if temporadas is None:
        temporadas = ["2023-24", "2024-25", "2025-26"]

    print("==========================================================")
    print(f"🏀 INICIANDO BACKFILL NBA: {len(temporadas)} temporadas")
    print("==========================================================")

    db_url = os.getenv("DB_URL", "postgresql://postgres:Jk9oe@localhost:5432/itscoming_db")
    engine = create_engine(db_url)

    total_rows = 0

    for temporada in temporadas:
        year_str = temporada.split('-')[0]
        start_date = f"{year_str}-10-22"
        end_year = int(year_str) + 1
        end_date = f"{end_year}-06-15"

        print(f"\n--- Temporada {temporada} ({start_date} a {end_date}) ---")

        fechas = pd.date_range(start=start_date, end=end_date)
        lista_fechas = fechas.strftime("%d/%m/%Y").tolist()
        print(f"  Calendario: {len(lista_fechas)} dias a procesar.")

        client = NBAClient()
        todos_los_partidos = []

        for idx, fecha in enumerate(lista_fechas, start=1):
            if idx % 30 == 0:
                print(f"  Progreso: {idx}/{len(lista_fechas)} dias...")

            try:
                df_diario = client.get_player_props_by_date(fecha)

                if df_diario is not None and not df_diario.empty:
                    todos_los_partidos.append(df_diario)
            except Exception as e:
                print(f"  Error en {fecha}: {e}")

        if not todos_los_partidos:
            print(f"  Sin datos para {temporada}.")
            continue

        df_master = pd.concat(todos_los_partidos, ignore_index=True)
        print(f"  Matriz consolidada: {df_master.shape[0]} filas, {df_master.shape[1]} columnas.")

        df_master.columns = [str(c).lower().replace(' ', '_').replace('.', '').replace('-', '_') for c in df_master.columns]

        try:
            df_master.to_sql('nba_player_history', engine, if_exists='append', index=False)
            total_rows += len(df_master)
            print(f"  Inyectados {len(df_master)} registros.")
        except Exception as e:
            print(f"  Error SQL: {e}")

        time.sleep(2)

    print("\n==========================================================")
    print(f"🚀 BACKFILL COMPLETADO: {total_rows} registros totales.")
    print("==========================================================")

if __name__ == "__main__":
    run_nba_backfill()
