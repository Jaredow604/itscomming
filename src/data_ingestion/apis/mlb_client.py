import pandas as pd
import statsapi 
from datetime import datetime


class MLBClient:
    def __init__(self):
        pass
        
    def get_player_props_by_date(self, date_str: str) -> pd.DataFrame:
        """
        Extrae las métricas utilizando exclusivamente la capa oficial de statsapi 
        (Sin scraping de 365Scores).
        """
        all_players_stats = []
        
        # Conversión de fecha DD/MM/YYYY a YYYY-MM-DD para statsapi
        try:
            fmt_date = datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            fmt_date = date_str
            
        # Consultar endpoints oficiales de calendario
        schedule = statsapi.schedule(date=fmt_date)
        
        for game in schedule:
            game_id = game['game_id']
            # Consultar endpoint oficial de recuento (Dictionary format)
            box = statsapi.boxscore_data(game_id)
            
            home_name = game.get('home_name', 'Rival Desconocido')
            away_name = game.get('away_name', 'Rival Desconocido')
            
            for side in ['away', 'home']:
                team_name = home_name if side == 'home' else away_name
                rival_name = away_name if side == 'home' else home_name
                
                players = box.get(side, {}).get('players', {})
                for p_id, p_stats in players.items():
                    b_stats = p_stats.get('stats', {}).get('batting', {})
                    if b_stats:
                        all_players_stats.append({
                            'id_jugador_mlb': p_id,
                            'nombre_jugador': p_stats.get('person', {}).get('fullName'),
                            'id_partido_mlb': game_id,
                            'team_name': team_name,
                            'rival_name': rival_name,
                            'turnos_al_bate': int(b_stats.get('atBats', 0)),
                            'hits': int(b_stats.get('hits', 0)),
                            'carreras': int(b_stats.get('runs', 0)),
                            'home_runs': int(b_stats.get('homeRuns', 0)),
                            'carreras_impulsadas': int(b_stats.get('rbi', 0)),
                            'bases_por_bolas': int(b_stats.get('baseOnBalls', 0)),
                            'ponches': int(b_stats.get('strikeOuts', 0)),
                        })
                        
        # Retorno de pandas data frame
        return pd.DataFrame(all_players_stats)
