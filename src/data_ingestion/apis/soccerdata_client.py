import logging
import time
import random
import pandas as pd
import soccerdata as sd
from sqlalchemy import create_engine

logger = logging.getLogger(__name__)

class SoccerDataClient:
    """
    Cliente para la extracción de métricas avanzadas (xG, xA, tiros, etc.)
    desde FBref utilizando la librería soccerdata.
    """

    def __init__(self, seasons=None):
        """
        Inicializa el cliente estableciendo el objetivo en las 5 grandes ligas
        de Europa y la combinada.

        Args:
            seasons: Lista de temporadas. Default: ["2324", "2425", "2526"]
        """
        self.target_leagues = [
            'ENG-Premier League',
            'ESP-La Liga',
            'ITA-Serie A',
            'GER-Bundesliga',
            'FRA-Ligue 1',
            'Big 5 European Leagues Combined',
            'MEX-Liga MX'
        ]

        seasons_list = seasons if seasons is not None else ["2324", "2425", "2526"]
        seasons_list = [seasons_list] if isinstance(seasons_list, str) else seasons_list

        logger.info("Iniciando conexión con FBref... (Esto puede tardar unos segundos)")
        self.fbref = sd.FBref(
            leagues=self.target_leagues,
            seasons=seasons_list
        )
        logger.info("SoccerDataClient inicializado correctamente con FBref.")

    def get_advanced_team_stats(self, stat_type='shooting'):
        """
        Extrae estadísticas avanzadas a nivel de equipo.
        Maneja el aplanamiento estricto de MultiIndex devuelto por soccerdata
        y rellena valores nulos con 0 para mantener consistencia en SQL.
        """
        if not self.fbref:
            logger.error("Cliente FBref no está inicializado. Abortando extracción de equipo.")
            return pd.DataFrame()

        try:
            logger.info(f"Extrayendo team stats para stat_type='{stat_type}'...")
            df = self.fbref.read_team_season_stats(stat_type=stat_type)
            
            # Dimensional Reduction: MultiIndex a índice plano
            df = df.reset_index()
            
            # Aplanamiento de columnas jerárquicas
            if isinstance(df.columns, pd.MultiIndex):
                new_cols = []
                for col in df.columns.values:
                    # Filtro de niveles residuales generados por pandas
                    clean_levels = [str(c) for c in col if c and not str(c).startswith('Unnamed')]
                    new_cols.append('_'.join(clean_levels).strip('_'))
                df.columns = new_cols
            
            # Limpieza de nulos
            df = df.fillna(0)
            
            logger.info(f"Extracción exitosa de team stats: {len(df)} registros obtenidos.")
            return df
            
        except ValueError as ve:
            logger.warning(f"FBref ValueError (posible bloqueo o dato no encontrado): {ve}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error inesperado en extraccion de team stats: {e}")
            return pd.DataFrame()

    def get_advanced_player_stats(self, stat_type='standard'):
        """
        Extrae estadísticas avanzadas a nivel de jugador.
        Maneja la misma lógica estricta de aplanamiento de MultiIndex que en equipos,
        y formatea columnas para estar alineadas con el ORM del proyecto.
        """
        if not self.fbref:
            logger.error("Cliente FBref no está inicializado. Abortando extracción de jugador.")
            return pd.DataFrame()

        try:
            logger.info(f"Extrayendo player stats para stat_type='{stat_type}'...")
            df = self.fbref.read_player_season_stats(stat_type=stat_type)
            
            # Dimensional Reduction: MultiIndex a índice plano
            df = df.reset_index()
            
            # Aplanamiento de jerarquía columnar
            if isinstance(df.columns, pd.MultiIndex):
                new_cols = []
                for col in df.columns.values:
                    clean_levels = [str(c) for c in col if c and not str(c).startswith('Unnamed')]
                    new_cols.append('_'.join(clean_levels).strip('_'))
                df.columns = new_cols
            
            # Estandarización de nomenclaturas primarias para Entity Resolution

            rename_mapping = {
                'player': 'nombre_jugador',
                'team': 'team_name'
            }
            
            # Búsqueda dinámica de similitudes post-aplanamiento

            dynamic_rename = {}
            for col in df.columns:
                lower_col = col.lower()
                if lower_col == 'player':
                    dynamic_rename[col] = 'nombre_jugador'
                elif lower_col == 'team':
                    dynamic_rename[col] = 'team_name'
                    
            if dynamic_rename:
                df = df.rename(columns=dynamic_rename)
            else:
                df = df.rename(columns=rename_mapping)
            
            # 4. Limpieza de nulos
            df = df.fillna(0)
            
            # Log métrico para diagnóstico de EntityResolver en Liga MX

            league_col = next((col for col in df.columns if str(col).lower() in ['league', 'comp', 'competition']), None)
            if league_col:
                mx_players = df[df[league_col].astype(str).str.contains('Liga MX', case=False, na=False)]
                if not mx_players.empty:
                    logger.info(f"Detectados {len(mx_players)} jugadores de MEX-Liga MX para revisión en el EntityResolver.")
            
            logger.info(f"Extracción exitosa de player stats: {len(df)} registros obtenidos.")
            return df
            
        except ValueError as ve:
            logger.warning(f"FBref ValueError (posible bloqueo de IPs o sin datos en target): {ve}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error inesperado en extraccion de player stats: {e}")
            return pd.DataFrame()

class MatchHistoryScraper:
    def __init__(self):
        self.db_url = os.getenv("DB_URL", "postgresql://postgres:Jk9oe@localhost:5432/itscoming_db")
        self.engine = create_engine(self.db_url)
        self.ligas = ['ENG-Premier League', 'ESP-La Liga', 'GER-Bundesliga', 'ITA-Serie A', 'FRA-Ligue 1']
        self.temporadas = ['2122', '2223', '2324', '2425', '2526']

    def extract_and_load(self):
        start_time = time.time()
        print("Iniciando extracción Stealth & Checkpoint de Match Logs (FBref)...")
        
        total_guardados = 0
        
        for liga in self.ligas:
            for temporada in self.temporadas:
                print(f"\n---> Procesando: {liga} | Temporada: {temporada}")
                try:
                    fbref = sd.FBref(leagues=liga, seasons=temporada)
                    df = fbref.read_schedule()
                except Exception as e:
                    print(f"\n[!] Advertencia: FBref bloqueó la IP o falló la conexión: {e}")
                    print("Iniciando enfriamiento largo de 120s...")
                    time.sleep(120)
                    continue
                
                if df.empty:
                    print("No se encontraron datos.")
                    continue
                    
                df = df.reset_index()
                
                # Limpieza Quant (Data Prep)
                score_col = 'score' if 'score' in df.columns else 'Score' if 'Score' in df.columns else None
                if score_col:
                    df = df[df[score_col].notna()]
                    splits = df[score_col].str.split(r'–|-', expand=True, regex=True)
                    if splits.shape[1] >= 2:
                        df['home_score'] = splits[0].str.strip()
                        df['away_score'] = splits[1].str.strip()
                else:
                    print("Advertencia: No se encontró la columna de marcador ('score').")

                # Renombrar columnas
                rename_map = {
                    'date': 'date',
                    'home_team': 'home_team',
                    'away_team': 'away_team',
                    'home_xg': 'home_xg',
                    'away_xg': 'away_xg'
                }
                
                map_cols = {}
                for col in df.columns:
                    l_col = str(col).lower()
                    if l_col in rename_map:
                        map_cols[col] = rename_map[l_col]
                
                df = df.rename(columns=map_cols)
                
                # Universal snake_case
                df.columns = [str(c).lower().replace(' ', '_') for c in df.columns]

                # ESTANDARIZACIÓN ESTRICTA (Defensa contra Schema Drift)
                columnas_base = ['league', 'season', 'date', 'home_team', 'away_team', 'home_score', 'away_score', 'home_xg', 'away_xg']
                df = df.reindex(columns=columnas_base)

                if not df.empty:
                    # CRÍTICO: append, no replace
                    df.to_sql('match_history_stats', con=self.engine, if_exists='append', index=False)
                    print(f"Chunk volcado exitosamente: {len(df)} registros agregados.")
                    total_guardados += len(df)
                    
                    sleep_time = random.randint(15, 35)
                    print(f"Éxito. Esperando {sleep_time}s para emular comportamiento humano...")
                    time.sleep(sleep_time)

        end_time = time.time()
        print("\n=== Extracción Finalizada ===")
        print(f"Total de partidos guardados en DB: {total_guardados}")
        print(f"Tiempo de ejecución total: {end_time - start_time:.2f} segundos")

if __name__ == '__main__':
    scraper = MatchHistoryScraper()
    scraper.extract_and_load()
