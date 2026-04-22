import pandas as pd
from nba_api.stats.endpoints import playergamelogs

from datetime import datetime

class NBAClient:
    def __init__(self):
        pass
        
    def get_player_props_by_date(self, date_str: str) -> pd.DataFrame:
        """
        Extrae las métricas utilizando la capa oficial de la API de la NBA.
        Incluye formato de fecha estricto y escudo contra Tarpitting (ReadTimeout).
        """
        import time
        import pandas as pd
        from datetime import datetime
        from nba_api.stats.endpoints import playergamelogs

        # 1. Transformación de Fecha (De DD/MM/YYYY a MM/DD/YYYY para la NBA)
        try:
            d = datetime.strptime(date_str, "%d/%m/%Y")
            fecha_nba = d.strftime("%m/%d/%Y")
            
            # Calcular temporada dinámica
            if d.month < 8:
                season_str = f"{d.year - 1}-{str(d.year)[-2:]}"
            else:
                season_str = f"{d.year}-{str(d.year + 1)[-2:]}"
        except Exception as e:
            print(f" Error formateando la fecha {date_str}: {e}")
            return pd.DataFrame()

        # 2. Loop de Exponential Backoff - Retry Policy
        for attempt in range(3):
            try:
                # Esperamos 1s, luego 3s, luego 9s...
                espera = 3 ** attempt
                print(f" Intentando conectar con NBA API (Intento {attempt + 1}/3) - Esperando {espera}s...")
                time.sleep(espera)
                
                # Petición controlada (Rate-limited Request)
                logs = playergamelogs.PlayerGameLogs(
                    date_from_nullable=fecha_nba,
                    date_to_nullable=fecha_nba,
                    season_nullable=season_str
                )
                
                # Si llegamos aquí, el servidor respondió
                df = logs.get_data_frames()[0]
                return df
                
            except Exception as e:
                # Atrapamos el maldito ReadTimeout (o cualquier otra cosa)
                print(f"️ Caída del servidor NBA en intento {attempt + 1}: {e}")

        # 3. Aborto Seguro
        print(f" NBA API inaccesible para la fecha {date_str} tras 3 intentos. Saltando día...")
        return pd.DataFrame() # Retornamos vacío para que el orquestador siga vivo
# =========================================================
# Función de Mapeo de Apoyo 
# =========================================================
def mapear_fila_nba_a_sqlalchemy(df_row: pd.Series, resolve_match_fn, resolve_player_fn):
    from src.data.models import PlayerStatsNBA
    
    id_partido_core = resolve_match_fn(df_row['id_partido_nba'])    
    id_jugador_core = resolve_player_fn(df_row['nombre_jugador']) 
    
    return PlayerStatsNBA(
        id_partido=id_partido_core,
        id_jugador=id_jugador_core,
        minutos=int(df_row['minutos']),
        puntos=int(df_row['puntos']),
        rebotes=int(df_row['rebotes']),
        asistencias=int(df_row['asistencias']),
        robos=int(df_row['robos']),
        bloqueos=int(df_row['bloqueos']),
        perdidas=int(df_row['perdidas']),
        triples=int(df_row['triples'])
    )
