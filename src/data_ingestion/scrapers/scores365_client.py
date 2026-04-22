import os
import logging
import httpx
import pandas as pd
import asyncio
import logging
from typing import Dict, Any, Optional, List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configuración básica de logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Scores365Client")

class Scores365Client:
    """
    Cliente API-First Avanzado para Ingeniería Inversa de 365Scores.
    Consume directamente el backend JSON (webws.365scores.com) evitando el renderizado DOM.
    Incorpora soporte de resiliencia y anti-ban con Tenacity y HTTPX.
    """

    def __init__(self, 
                 country_id: int = 31, 
                 lang_id: int = 27, 
                 app_type_id: int = 5, 
                 timezone_name: str = "America/Mexico_City", 
                 bookmaker_id: int = 4,
                 target_competitions: Optional[List[int]] = None,
                 timeout: int = 15):
        """
        Inicializa el cliente de 365Scores estableciendo cabeceras realistas y preferencias globales geográficas.
        """
        self.base_url = "https://webws.365scores.com/web"
        # NBA (103), MLB (438), Premier League (7), La Liga (11), Serie A (17), Bundesliga (25), Champions (67), Liga MX (229)
        self.target_competitions = target_competitions if target_competitions is not None else [103, 438, 7, 11, 17, 25, 67, 229]
        
        # Parámetros de geolocalización extraídos del hardcoding directos a la instancia
        self.global_params = {
            "appTypeId": app_type_id,
            "langId": lang_id,
            "timezoneName": timezone_name,
            "userCountryId": country_id,
            "bookmakerId": bookmaker_id
        }

        # Cabeceras ofensivas de alta fiabilidad
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
            "Origin": "https://www.365scores.com",
            "Referer": "https://www.365scores.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "Connection": "keep-alive"
        }
        self.timeout = timeout

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1.5, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True
    )
    def _fetch_json(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Método central de peticiones con retroceso exponencial."""
        url = f"{self.base_url}{endpoint}"
        
        # Inyecta los parámetros globales de configuración
        final_params = self.global_params.copy()
        if params:
            final_params.update(params)

        logger.debug(f"Pidiendo endpoint REST: {url} | Params: {final_params}")
        
        with httpx.Client(headers=self.headers, timeout=self.timeout, http2=True) as client:
            response = client.get(url, params=final_params)
            response.raise_for_status()
            return response.json()

    async def get_fixtures_by_date(self, date_str: str) -> list:
        """
        Descubre los partidos por fecha (DD/MM/YYYY) y filtra solo las competiciones objetivo (NBA, MLB, etc.)
        que tengan datos de H2H disponibles.
        """
        endpoint = f"{self.base_url}/games/"
        
        # Parámetros para buscar los partidos en una fecha histórica
        params = {
            "appTypeId": 5,
            "langId": 27,
            "timezoneName": "America/Mexico_City",
            "userCountryId": 31,
            "bookmakerId": 4,
            "startDate": date_str,
            "endDate": date_str
        }

        logging.info(f"Localizando fixture de partidos para {date_str} (Filtro Alta Calidad)...")
        valid_games = []

        try:
            async with httpx.AsyncClient(http2=True) as client:
                # AQUÍ es donde se define 'response'
                response = await client.get(
                    endpoint, 
                    headers=self.headers, 
                    params=params, 
                    timeout=15.0
                )
                response.raise_for_status()
                
                # Ahora sí, extraemos el JSON con seguridad
                data = response.json()
                
                # Iniciamos nuestro filtro láser
                for game in data.get('games', []):
                    comp_id = game.get('competitionId')
                    game_id = game.get('id')
                    
                    # 1. Filtro primario: ¿Es NBA (103) o MLB (438)?
                    if comp_id in self.target_competitions:
                        
                        
                        
                        home = game.get('homeCompetitor', {}).get('name', 'Local')
                        away = game.get('awayCompetitor', {}).get('name', 'Visita')
                            
                        logging.info(f" Match identificado: {home} vs {away} (Liga: {comp_id}, ID: {game_id})")
                        valid_games.append(game_id)
                            
        except httpx.HTTPStatusError as exc:
            logging.error(f"Error HTTP buscando partidos: {exc.response.status_code}")
        except Exception as e:
            logging.error(f"Error inesperado leyendo el fixture: {e}")

        logging.info(f"Se descubrieron {len(valid_games)} partidos de ALTA CALIDAD listados para revisión.")
        return valid_games

    def get_match_stats(self, match_id: int) -> pd.DataFrame:
        """
        Extrae estadísticas en profundidad (nombres reales, marcadores, y stats específicos).
        """
        logger.info(f"Resolviendo Match Stats para GameID: {match_id}")
        endpoint = "/game/"
        params = {"gameId": match_id}

        try:
            payload = self._fetch_json(endpoint, params)
            game_data = payload.get("game", {})
            
            if not game_data:
                return pd.DataFrame()
                
            home_team_id = game_data.get("homeCompetitor", {}).get("id")
            away_team_id = game_data.get("awayCompetitor", {}).get("id")
            
            home_team_name = game_data.get("homeCompetitor", {}).get("name", "Unknown Local")
            away_team_name = game_data.get("awayCompetitor", {}).get("name", "Unknown Visita")

            flattened_data = {
                "match_id": match_id,
                "competition_id": game_data.get("competitionId", 103),
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "home_team_name": home_team_name,
                "away_team_name": away_team_name,
                "home_points": game_data.get("homeCompetitor", {}).get("score", 0),
                "away_points": game_data.get("awayCompetitor", {}).get("score", 0),
                "home_score": game_data.get("homeCompetitor", {}).get("score", 0),
                "away_score": game_data.get("awayCompetitor", {}).get("score", 0),
            }

            stats_list = game_data.get("statistics", [])
            for stat in stats_list:
                stat_name = str(stat.get("name", "unknown")).lower().replace(" ", "_").replace("-", "_")
                flattened_data[f"home_{stat_name}"] = stat.get("homeValue")
                flattened_data[f"away_{stat_name}"] = stat.get("awayValue")

            # Inicialización preventiva (Pre-fetch mapping schema) de keys
            llaves_futbol = [
                'goals', 'ball_possession', 'shots_on_target', 
                'corners', 'yellow_cards', 'red_cards', 'expected_goals'
            ]
            for key in llaves_futbol:
                flattened_data.setdefault(f"home_{key}", 0.0 if key == 'expected_goals' else 0)
                flattened_data.setdefault(f"away_{key}", 0.0 if key == 'expected_goals' else 0)

            df = pd.DataFrame([flattened_data])
            return df
            
        except httpx.HTTPError as e:
            logger.error(f"Exception: Falla no recuperada en extracción de estadísticas del partido (Game): {e}")
            return pd.DataFrame()

    def get_h2h_by_game(self, game_id: int) -> pd.DataFrame:
        """
        Extrae el Historial Head-2-Head utilizando el ID del partido.
        """
        endpoint = "/games/h2h/"
        params = {"gameId": game_id}

        try:
            payload = self._fetch_json(endpoint, params)
            games_h2h = payload.get("games", [])
            
            if not games_h2h:
                logger.debug(f"Datos históricos de H2H no encontrados para Juego {game_id}.")
                return pd.DataFrame()

            df_h2h = pd.json_normalize(games_h2h)
            df_h2h.columns = [col.replace('.', '_').lower() for col in df_h2h.columns]
            
            return df_h2h

        except httpx.HTTPError as e:
            logger.error(f"Exception: Error de conectividad de red al extraer historial H2H: {e}")
            return pd.DataFrame()

    def get_soccer_player_stats(self, game_id: int) -> pd.DataFrame:
        """
        Extrae Player Props para futbol parseando las alineaciones del JSON de 365scores usando IDs numéricos.
        """
        import httpx
        import pandas as pd
        import logging
        
        url = f"https://webws.365scores.com/web/game/?appTypeId=5&langId=31&gameId={game_id}"
        try:
            response = httpx.get(url, timeout=15.0)
            response.raise_for_status()
            game_data = response.json().get('game', {})
        except Exception as e:
            logging.error(f"Error de red/timeout en GameID {game_id}: {e}")
            return pd.DataFrame()
            
        if not game_data:
            return pd.DataFrame()
            
        all_players_stats = []
        
        for side in ['homeCompetitor', 'awayCompetitor']:
            team_data = game_data.get(side, {})
            team_id = team_data.get('id', 0)
            team_name = team_data.get('name', 'Equipo Desconocido')
            
            lineups = team_data.get('lineups', {})
            members = lineups.get('members', [])
            
            if not members:
                # Fallback de capa 2: nodo boxscore
                members_boxscore = game_data.get('boxscore', {}).get('players', [])
                if members_boxscore:
                    # Validación secundaria de presencia de datos en nodo alternativo
                    members = members_boxscore
                    
            print(f"DEBUG: Procesando Game {game_id}. Equipo {team_name}. Encontrados {len(members)} miembros.")
            
            for player in members:
                p_id = player.get('id', 0)
                p_name = player.get('name', 'Jugador Desconocido')
                
                stats = player.get('statistics', [])
                
                stat_map = {}
                for st in stats:
                    # Mapeo doble vía keys paramétricas y keys de respaldo de texto (string hash)
                    stat_id = st.get('id')
                    val = st.get('value', 0)
                    if stat_id is not None:
                        stat_map[stat_id] = val
                    name_key = str(st.get('name', '')).lower().strip()
                    if name_key:
                        stat_map[name_key] = val
                    
                player_dict = {
                    'id_jugador': p_id,
                    'nombre_jugador': p_name,
                    'team_id': team_id,
                    'team_name': team_name,
                    'minutos': int(stat_map.get(41, stat_map.get('minutes played', stat_map.get('minutos jugados', 0)))),
                    'goles': int(stat_map.get(1, stat_map.get('goals', stat_map.get('goles', 0)))),
                    'asistencias': int(stat_map.get(2, stat_map.get('assists', stat_map.get('asistencias', 0)))),
                    'tiros_totales': int(stat_map.get(13, stat_map.get('total shots', stat_map.get('tiros', 0)))),
                    'tiros_puerta': int(stat_map.get(14, stat_map.get('shots on target', stat_map.get('tiros a puerta', 0)))),
                    'pases_precisos': int(stat_map.get(15, stat_map.get('accurate passes', stat_map.get('pases completados', 0)))),
                    'faltas_cometidas': int(stat_map.get('fouls', stat_map.get('faltas cometidas', 0))),
                    'amarillas': int(stat_map.get('yellow cards', 0)),
                    'rojas': int(stat_map.get('red cards', 0))
                }
                
                all_players_stats.append(player_dict)
                
        comp_id = game_data.get('competitionId', 0)
        if comp_id in [7, 11, 17, 25, 67, 229]:
            logging.info(f"EXTRACCIÓN (FÚTBOL ÉLITE): {len(all_players_stats)} registros de Player Props para GameID {game_id} (CompId {comp_id}).")
            
        return pd.DataFrame(all_players_stats)

# =========================================================
# Bloque End-to-End de Búsqueda Activa (Smoke Test)
# =========================================================
if __name__ == "__main__":
    async def ejecutar_smoke_test():
        from datetime import datetime, timedelta
        logging.info("Iniciando Smoke Test End-to-End con Búsqueda Activa...")
        
        client = Scores365Client() 
        
        target_date = (datetime.now() - timedelta(days=3)).strftime("%d/%m/%Y")
        high_quality_fixtures = await client.get_fixtures_by_date(target_date)
        
        if not high_quality_fixtures:
            logging.warning("No hay partidos objetivo hoy. Fin de la prueba.")
            return

        for game_id in high_quality_fixtures:
            logging.info(f" Extrayendo histórico para el GameID: {game_id}...")
            
            df_h2h = client.get_h2h_by_game(game_id)
        
            
            if df_h2h is not None and not df_h2h.empty:
                logging.info(" ¡Jackpot! Datos H2H extraídos con éxito.")
                
            
                
                 
                print("\n MUESTRA DE DATOS LISTA PARA POSTGRESQL:")
                print("-" * 60)
                columnas_interes = ['id', 'startTime', 'homeCompetitor.name', 'awayCompetitor.name', 'homeCompetitor.score', 'awayCompetitor.score']
                columnas_presentes = [c for c in columnas_interes if c in df_h2h.columns]
                print(df_h2h[columnas_presentes].head(5).to_markdown(index=False))
                print("-" * 60)
                break
if __name__ == "__main__":
    # Así es como se arranca el motor asíncrono en Python
    asyncio.run(ejecutar_smoke_test())
