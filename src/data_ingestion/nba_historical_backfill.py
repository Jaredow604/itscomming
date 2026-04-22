import pandas as pd
from sqlalchemy import create_engine
import time
from datetime import datetime

# Importación de tu clase robusta 
from src.data_ingestion.apis.nba_client import NBAClient

def run_nba_backfill():
    print("==========================================================")
    print("🏀 INICIANDO BACKFILL HISTÓRICO NBA (Season REG 23-24)")
    print("==========================================================")
    hoy=datetime.today().strftime('%Y-%m-%d')
    # 1. Generador de Fechas (Calendario)
    start_date = "2023-10-24" # Inicio real de la temporada NBA 2023-24
    end_date = "2024-04-14"   # Fin de la temporada regular
    
    print(f"[*] Configurando Orquestador para la Temporada 24-25 (Hasta {hoy})...")
    fechas = pd.date_range(start="2024-10-22", end=hoy)
    
    # Casteamos la serie térmica a formato string explícito "DD/MM/YYYY" para el client
    lista_fechas = fechas.strftime("%d/%m/%Y").tolist()
    print(f"Calendario inicializado: {len(lista_fechas)} días a procesar.\n")
    
    # 2. El Bucle de Extracción (El Tractor de Datos)
    client = NBAClient()
    todos_los_partidos = []
    
    for idx, fecha in enumerate(lista_fechas, start=1):
        print(f"[{idx}/{len(lista_fechas)}] Extrayendo Game Logs de la jornada: {fecha}...")
        try:
            df_diario = client.get_player_props_by_date(fecha)
            
            if df_diario is not None and not df_diario.empty:
                registros = len(df_diario)
                print(f"   -> ✅ Extraídos {registros} perfiles estadísticos.")
                todos_los_partidos.append(df_diario)
            else:
                print(f"   -> ⏸️ Jornada en blanco (no se jugaron partidos o no hay logs).")
        except Exception as e:
            print(f"   -> ❌ Error crudo en API al procesar la fecha {fecha}: {e}")
            
    print("\n==========================================================")
    print("📥 EXTRACCIÓN MASIVA FINALIZADA. PROCEDIENDO A LIMPIEZA...")
    
    # Verificación de Salvaguarda
    if not todos_los_partidos:
        print("Operación abortada: El array de recopilación está vacío. Posible bloqueo de API.")
        return
        
    # 3. Consolidación y Limpieza (Transform)
    df_master = pd.concat(todos_los_partidos, ignore_index=True)
    print(f"Matriz Consolidada: Forma final de {df_master.shape[0]} filas y {df_master.shape[1]} columnas.")
    
    # Mapeo universal de strings para evitar problemas en SQL Syntax
    print("Aplicando lowercase cleansing a las columnas...")
    df_master.columns = [str(c).lower().replace(' ', '_').replace('.', '').replace('-', '_') for c in df_master.columns]

    # 4. Inyección Final en BD (Load)
    db_url = "postgresql://postgres:Jk9oe@localhost:5432/itscoming_db"
    print(f"Estableciendo handshake con PostgreSQL en tabla 'nba_player_history'...")
    engine = create_engine(db_url)
    
    try:
        # Usamos if_exists='append' estricto para no sobrescribir esquemas 
        df_master.to_sql('nba_player_history', engine, if_exists='append', index=False)
        print(f"🚀 ¡ÉXITO! Se han inyectado permanentemente {len(df_master)} logs de jugadores.")
    except Exception as e:
        print(f"❌ Catástrofe de Indexación en SQL: {e}")
        
    print("==========================================================")

if __name__ == "__main__":
    run_nba_backfill()
