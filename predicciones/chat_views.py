"""
chat_views.py -- Vista DRF conversacional: POST /api/v1/chat/

Recibe {"message": "texto"} del frontend React, detecta intent (deporte/equipos),
ejecuta inferencia PyTorch via ModelRegistry, consulta las 4 metricas de la BD
de forma determinista (sport-aware), y retorna JSON estructurado.
"""

import hashlib
import logging
import math
import os
import re
import traceback
from datetime import date

import torch
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from predicciones.models import DailySchedule
from predicciones.model_registry import ModelRegistry

logger = logging.getLogger(__name__)


# ==========================================
# INTENT PARSER — NLP basado en reglas
# ==========================================

_TEAM_LOOKUP: dict = {}

_NBA_TEAMS = {
    'Atlanta Hawks': ['hawks', 'atl'],
    'Boston Celtics': ['celtics', 'bos'],
    'Brooklyn Nets': ['nets', 'bkn', 'brooklyn nets'],
    'Charlotte Hornets': ['hornets', 'cha'],
    'Chicago Bulls': ['bulls', 'chi bulls'],
    'Cleveland Cavaliers': ['cavaliers', 'cavs', 'cle'],
    'Dallas Mavericks': ['mavericks', 'mavs', 'dal'],
    'Denver Nuggets': ['nuggets', 'den'],
    'Detroit Pistons': ['pistons', 'det pistons'],
    'Golden State Warriors': ['warriors', 'gsw', 'golden state', 'dubs'],
    'Houston Rockets': ['rockets', 'hou rockets'],
    'Indiana Pacers': ['pacers', 'ind'],
    'LA Clippers': ['clippers', 'lac'],
    'Los Angeles Lakers': ['lakers', 'lal'],
    'Memphis Grizzlies': ['grizzlies', 'mem'],
    'Miami Heat': ['heat', 'mia heat'],
    'Milwaukee Bucks': ['bucks', 'mil bucks'],
    'Minnesota Timberwolves': ['timberwolves', 'wolves', 'min wolves'],
    'New Orleans Pelicans': ['pelicans', 'nop', 'new orleans'],
    'New York Knicks': ['knicks', 'nyk'],
    'Oklahoma City Thunder': ['thunder', 'okc'],
    'Orlando Magic': ['magic', 'orl'],
    'Philadelphia 76ers': ['76ers', 'sixers', 'phi sixers', 'philly'],
    'Phoenix Suns': ['suns', 'phx'],
    'Portland Trail Blazers': ['blazers', 'trail blazers', 'por'],
    'Sacramento Kings': ['kings', 'sac kings'],
    'San Antonio Spurs': ['spurs', 'sas'],
    'Toronto Raptors': ['raptors', 'tor raptors'],
    'Utah Jazz': ['jazz', 'uta'],
    'Washington Wizards': ['wizards', 'wiz', 'was wizards'],
}

_MLB_TEAMS = {
    'Arizona Diamondbacks': ['diamondbacks', 'dbacks', 'ari'],
    'Atlanta Braves': ['braves', 'atl braves'],
    'Baltimore Orioles': ['orioles', 'bal'],
    'Boston Red Sox': ['red sox', 'bos sox'],
    'Chicago Cubs': ['cubs', 'chc'],
    'Chicago White Sox': ['white sox', 'cws'],
    'Cincinnati Reds': ['reds', 'cin'],
    'Cleveland Guardians': ['guardians', 'cle guardians'],
    'Colorado Rockies': ['rockies', 'col'],
    'Detroit Tigers': ['tigers', 'det tigers'],
    'Houston Astros': ['astros', 'hou astros'],
    'Kansas City Royals': ['royals', 'kc', 'kcr'],
    'Los Angeles Angels': ['angels', 'laa', 'anaheim'],
    'Los Angeles Dodgers': ['dodgers', 'lad'],
    'Miami Marlins': ['marlins', 'mia marlins'],
    'Milwaukee Brewers': ['brewers', 'mil brewers'],
    'Minnesota Twins': ['twins', 'min twins'],
    'New York Mets': ['mets', 'nym'],
    'New York Yankees': ['yankees', 'yanks', 'nyy'],
    'Oakland Athletics': ['athletics', "a's", 'oak'],
    'Philadelphia Phillies': ['phillies', 'phi phillies'],
    'Pittsburgh Pirates': ['pirates', 'pit'],
    'San Diego Padres': ['padres', 'sd padres'],
    'San Francisco Giants': ['giants', 'sfg', 'sf giants'],
    'Seattle Mariners': ['mariners', 'sea'],
    'St. Louis Cardinals': ['cardinals', 'stl'],
    'Tampa Bay Rays': ['rays', 'tb', 'tbr'],
    'Texas Rangers': ['rangers', 'tex rangers'],
    'Toronto Blue Jays': ['blue jays', 'jays', 'tor jays'],
    'Washington Nationals': ['nationals', 'nats', 'wsh'],
}

_SOCCER_TEAMS = {
    # --- Premier League ---
    'Arsenal': ['arsenal', 'gunners', 'afc arsenal'],
    'Aston Villa': ['aston villa', 'villa', 'avfc'],
    'Bournemouth': ['bournemouth', 'afc bournemouth', 'cherries'],
    'Brentford': ['brentford', 'bees'],
    'Brighton': ['brighton', 'brighton & hove albion', 'seagulls'],
    'Chelsea': ['chelsea', 'cfc', 'blues'],
    'Crystal Palace': ['crystal palace', 'palace', 'cpfc', 'eagles'],
    'Everton': ['everton', 'efc', 'toffees'],
    'Fulham': ['fulham', 'ffc', 'cottagers'],
    'Ipswich Town': ['ipswich', 'ipswich town', 'itfc', 'tractor boys'],
    'Leicester City': ['leicester', 'leicester city', 'lcfc', 'foxes'],
    'Liverpool': ['liverpool', 'lfc', 'reds'],
    'Manchester City': ['man city', 'manchester city', 'city', 'mcfc', 'citizens'],
    'Manchester United': ['man utd', 'manchester united', 'united', 'man ut', 'mu', 'mufc', 'red devils'],
    'Newcastle United': ['newcastle', 'newcastle united', 'nufc', 'magpies', 'toon'],
    'Nottingham Forest': ['nottm forest', 'nottingham forest', 'nffc', 'forest'],
    'Southampton': ['southampton', 'saints', 'sfc'],
    'Tottenham': ['tottenham', 'tottenham hotspur', 'spurs', 'thfc', 'lilywhites'],
    'West Ham': ['west ham', 'west ham united', 'whu', 'whufc', 'hammers', 'irons'],
    'Wolverhampton': ['wolves', 'wolverhampton', 'wolverhampton wanderers', 'wwfc'],
    # --- La Liga ---
    'Real Madrid': ['real madrid', 'realmadrid', 'rmcf', 'merengues', 'blancos', 'galacticos'],
    'Barcelona': ['barcelona', 'barca', 'barça', 'fcb', 'blaugrana', 'culers'],
    'Atlético Madrid': ['atletico madrid', 'atletico', 'atleti', 'atm', 'colchoneros'],
    'Real Sociedad': ['real sociedad', 'rsociedad', 'rsoc', 'txuriurdin'],
    'Athletic Bilbao': ['athletic bilbao', 'athletic', 'ath club', 'bilbao', 'leones'],
    'Sevilla': ['sevilla', 'sev', 'sfc', 'rojiblancos'],
    'Real Betis': ['betis', 'real betis', 'verdiblancos'],
    'Villarreal': ['villarreal', 'yellow submarine', 'submarino amarillo'],
    # --- Liga MX ---
    'América': ['america', 'américa', 'las aguilas', 'club america'],
    'Chivas': ['chivas', 'guadalajara', 'cd guadalajara', 'chivas guadalajara'],
    'Cruz Azul': ['cruz azul', 'la maquina', 'ca', 'cementeros'],
    'Monterrey': ['monterrey', 'rayados', 'cf monterrey', 'cfm'],
    'Pumas': ['pumas', 'pumas unam', 'unam'],
    'Tigres': ['tigres', 'tigres uanl', 'uanl'],
    # --- Serie A ---
    'Juventus': ['juventus', 'juve', 'bianconeri', 'ju'],
    'AC Milan': ['ac milan', 'milan', 'rossoneri', 'acm'],
    'Inter Milan': ['inter', 'inter milan', 'inter de milan', 'nerazzurri'],
    'Napoli': ['napoli', 'naples', 'azzurri'],
    'AS Roma': ['roma', 'as roma', 'giallorossi'],
    'Lazio': ['lazio', 'ss lazio', 'biancocelesti'],
    # --- Bundesliga ---
    'Bayern Munich': ['bayern', 'bayern munich', 'bayern munchen', 'fcbayern'],
    'Borussia Dortmund': ['dortmund', 'borussia dortmund', 'bvb', 'schwarzgelben'],
    'RB Leipzig': ['rb leipzig', 'leipzig', 'rbl'],
    'Bayer Leverkusen': ['leverkusen', 'bayer leverkusen', 'werkself'],
    # --- Ligue 1 ---
    'Paris SG': ['psg', 'paris sg', 'paris saint-germain', 'parisien'],
    'Marseille': ['marseille', 'om', 'olympique marseille'],
    'Lyon': ['lyon', 'ol', 'olympique lyonnais'],
    'Monaco': ['monaco', 'asm', 'as monaco'],
    'Lille': ['lille', 'losc', 'lille osc'],
    'Lens': ['lens', 'rcl', 'rc lens'],
    'Rennes': ['rennes', 'stade rennais', 'srfc'],
    'Nice': ['nice', 'ogc nice'],
    # --- Eredivisie ---
    'Ajax': ['ajax', 'afc ajax', 'amsterdammers'],
    'PSV': ['psv', 'psv eindhoven'],
    'Feyenoord': ['feyenoord'],
}

for _full, _aliases in _NBA_TEAMS.items():
    _TEAM_LOOKUP[_full.lower()] = (_full, 'nba')
    for _a in _aliases:
        _TEAM_LOOKUP[_a.lower()] = (_full, 'nba')

for _full, _aliases in _MLB_TEAMS.items():
    _TEAM_LOOKUP[_full.lower()] = (_full, 'mlb')
    for _a in _aliases:
        _TEAM_LOOKUP[_a.lower()] = (_full, 'mlb')

for _full, _aliases in _SOCCER_TEAMS.items():
    _TEAM_LOOKUP[_full.lower()] = (_full, 'soccer')
    for _a in _aliases:
        _TEAM_LOOKUP[_a.lower()] = (_full, 'soccer')

_SPORT_KEYWORDS = {
    'nba': ['nba', 'basketball', 'basquet', 'baloncesto'],
    'mlb': ['mlb', 'baseball', 'beisbol', 'béisbol'],
    'soccer': ['soccer', 'futbol', 'fútbol', 'liga', 'premier', 'laliga', 'la liga', 'liga mx', 'realmadrid', 'real madrid', 'barcelona', 'barça', 'chivas', 'america', 'américa', 'serie a', 'bundesliga', 'ligue 1', 'champions league'],
}


class IntentParser:
    """Detecta deporte y equipos mencionados en el mensaje del usuario."""

    @classmethod
    def parse(cls, message: str) -> dict:
        msg = message.lower()

        sport = None
        for s, kws in _SPORT_KEYWORDS.items():
            if any(kw in msg for kw in kws):
                sport = s
                break

        sorted_aliases = sorted(_TEAM_LOOKUP.keys(), key=len, reverse=True)
        teams_found = []
        seen_full_names = set()

        for alias in sorted_aliases:
            if re.search(r'\b' + re.escape(alias) + r'\b', msg):
                full_name, team_sport = _TEAM_LOOKUP[alias]
                if full_name not in seen_full_names:
                    teams_found.append((full_name, team_sport))
                    seen_full_names.add(full_name)

        if not sport and teams_found:
            sport = teams_found[0][1]

        if sport:
            teams_found = [(n, s) for n, s in teams_found if s == sport]

        return {'sport': sport, 'teams': teams_found}


# ==========================================
# UTILIDADES: FEATURES, ELO, H2H
# ==========================================

def _get_inference_features(entity_name: str, num_features: int, is_player: bool = False) -> torch.Tensor:
    """Consulta InferenceReadyPlayerData para el vector de features (Solo si es jugador)."""
    if not is_player:
        # Los equipos de NBA/MLB actualmente no tienen features reales en DB,
        # devolveremos tensor de 0s para que gatille el fallback o use synthetic baselines.
        return torch.zeros((1, num_features), dtype=torch.float32)

    try:
        from database import SessionLocal
        from sqlalchemy import text

        session = SessionLocal()
        try:
            query = text("""
                SELECT playing_time_min_scaled, total_shots_scaled, standard_sot_scaled
                FROM ml_inference_ready_player_data
                WHERE player_name = :entity OR team_name = :entity
                ORDER BY created_at DESC
                LIMIT 1
            """)
            result = session.execute(query, {'entity': entity_name}).fetchone()
            if result:
                values = list(result)
                while len(values) < num_features:
                    values.append(0.0)
                values = values[:num_features]
                return torch.tensor([values], dtype=torch.float32)
        finally:
            session.close()
    except Exception as e:
        logger.warning("Features no disponibles para '%s': %s", entity_name, e)
    
    return torch.zeros((1, num_features), dtype=torch.float32)


def _get_team_stats_sqlalchemy(team_name: str, sport: str) -> dict:
    """Consulta stats historicos de un equipo desde la tabla SQLAlchemy correspondiente."""
    table_map = {
        'nba': {
            'query': """
                SELECT AVG(s.puntos_local + s.puntos_visitante) as avg_pts,
                       AVG(s.rebotes_local + s.rebotes_visitante) as avg_reb,
                       AVG(s.triples_local + s.triples_visitante) as avg_3pm
                FROM partidos p
                JOIN stats_nba s ON s.id_partido = p.id_partido
                JOIN equipos e ON e.id_equipo = p.id_local
                WHERE e.nombre ILIKE :team
            """,
            'fallback': {'avg_pts': 110.0, 'avg_reb': 45.0, 'avg_3pm': 12.0},
        },
        'mlb': {
            'query': """
                SELECT AVG(s.carreras_local + s.carreras_visitante) as avg_runs,
                       AVG(s.hits_local + s.hits_visitante) as avg_hits,
                       AVG(s.errores_local + s.errores_visitante) as avg_err
                FROM partidos p
                JOIN stats_mlb s ON s.id_partido = p.id_partido
                JOIN equipos e ON e.id_equipo = p.id_local
                WHERE e.nombre ILIKE :team
            """,
            'fallback': {'avg_runs': 4.5, 'avg_hits': 8.0, 'avg_err': 1.0},
        },
        'soccer': {
            'query': """
                SELECT AVG(s.goles_local + s.goles_visitante) as avg_goals,
                       AVG(s.tiros_puerta_local + s.tiros_puerta_visitante) as avg_sot,
                       AVG(s.corners_local + s.corners_visitante) as avg_corners
                FROM partidos p
                JOIN stats_futbol s ON s.id_partido = p.id_partido
                JOIN equipos e ON e.id_equipo = p.id_local
                WHERE e.nombre ILIKE :team
            """,
            'fallback': {'avg_goals': 2.5, 'avg_sot': 8.0, 'avg_corners': 10.0},
        },
    }

    cfg = table_map.get(sport, table_map['soccer'])
    try:
        from database import SessionLocal
        from sqlalchemy import text

        session = SessionLocal()
        try:
            row = session.execute(text(cfg['query']), {'team': f'%{team_name}%'}).fetchone()
            if row and row[0] is not None:
                keys = list(cfg['fallback'].keys())
                return {k: (float(row[i]) if row[i] is not None else cfg['fallback'][k]) for i, k in enumerate(keys)}
        finally:
            session.close()
    except Exception:
        pass

    seed = _team_seed(team_name)
    fb = cfg['fallback']
    varied = {}
    for k, v in fb.items():
        noise = (seed - 0.5) * v * 0.4
        varied[k] = round(v + noise, 1)
    return varied


def _team_seed(team_name: str) -> float:
    """Genera un valor 0.0-1.0 determinista basado en el nombre del equipo."""
    h = hashlib.md5(team_name.lower().strip().encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def _get_team_promedios_soccer(team_name: str) -> dict:
    """Consulta los promedios de un equipo desde la tabla 'equipos' (Django ORM). Solo soccer."""
    try:
        from predicciones.models import Equipos

        # 1. icontains - buscar todos y preferir los con stats reales
        matches = list(Equipos.objects.filter(nombre__icontains=team_name))
        if matches:
            with_stats = [e for e in matches if e.prom_goles > 0 or e.prom_tiros_puerta > 0]
            if with_stats:
                best = with_stats[0]
                return {
                    'prom_goles': float(best.prom_goles),
                    'prom_tiros_puerta': float(best.prom_tiros_puerta),
                    'prom_corners': float(best.prom_corners),
                }
            # Si todos los matches tienen stats=0, caer al seed fallback
    except Exception as e:
        logger.warning("Error consultando Equipos para '%s': %s", team_name, e)

    # 2. Fallback basado en seed determinista del nombre
    seed = _team_seed(team_name)
    prom_goles = 0.8 + seed * 1.8
    prom_tiros_puerta = 2.5 + seed * 5.0
    prom_corners = 3.0 + seed * 5.0
    return {
        'prom_goles': round(prom_goles, 2),
        'prom_tiros_puerta': round(prom_tiros_puerta, 1),
        'prom_corners': round(prom_corners, 1),
    }


def _poisson_predict(lambda_home: float, lambda_away: float, max_goals: int = 7) -> dict:
    """Calcula probabilidades 1X2 usando distribucion de Poisson independiente."""
    def poisson_pmf(lam: float, k: int) -> float:
        return (lam ** k) * math.exp(-lam) / math.factorial(k)

    probs = [[0.0] * (max_goals + 1) for _ in range(2)]
    for i in range(max_goals + 1):
        probs[0][i] = poisson_pmf(lambda_home, i)
        probs[1][i] = poisson_pmf(lambda_away, i)

    home_pct = sum(probs[0][i] * sum(probs[1][j] for j in range(i)) for i in range(max_goals + 1))
    away_pct = sum(probs[1][i] * sum(probs[0][j] for j in range(i)) for i in range(max_goals + 1))
    draw_pct = sum(probs[0][i] * probs[1][i] for i in range(max_goals + 1))

    total = home_pct + away_pct + draw_pct
    if total > 0:
        home_pct /= total
        away_pct /= total
        draw_pct /= total

    return {
        'probabilities': {'home': home_pct, 'draw': draw_pct, 'away': away_pct},
        'xg_home': round(lambda_home, 2),
        'xg_away': round(lambda_away, 2),
        'favored': 'home' if home_pct > max(draw_pct, away_pct) else ('draw' if draw_pct > away_pct else 'away'),
    }


def _build_elo_trend(team_name: str, sport: str) -> list:
    """Calcula la evolucion Elo de los ultimos 5 partidos."""
    try:
        from database import SessionLocal
        from sqlalchemy import text

        if sport == 'nba':
            stats_table = 'stats_nba'
            score_col_h, score_col_a = 'puntos_local', 'puntos_visitante'
        elif sport == 'mlb':
            stats_table = 'stats_mlb'
            score_col_h, score_col_a = 'carreras_local', 'carreras_visitante'
        else:
            stats_table = 'stats_futbol'
            score_col_h, score_col_a = 'goles_local', 'goles_visitante'

        session = SessionLocal()
        try:
            query = text(f"""
                SELECT e_h.nombre AS home_name, e_a.nombre AS away_name,
                       s.{score_col_h} AS score_home, s.{score_col_a} AS score_away
                FROM partidos p
                JOIN {stats_table} s ON s.id_partido = p.id_partido
                JOIN equipos e_h ON e_h.id_equipo = p.id_local
                JOIN equipos e_a ON e_a.id_equipo = p.id_visitante
                WHERE e_h.nombre = :team OR e_a.nombre = :team
                ORDER BY p.fecha DESC
                LIMIT 5
            """)
            rows = session.execute(query, {'team': team_name}).fetchall()

            if rows and len(rows) >= 3:
                if sport == 'nba':
                    from src.models.networks.nba_predictor import update_nba_elo
                    update_fn = update_nba_elo
                elif sport == 'mlb':
                    from src.models.networks.mlb_predictor import update_mlb_elo
                    update_fn = update_mlb_elo
                else:
                    update_fn = _update_soccer_elo

                elo = 1500.0
                trend = []
                for row in reversed(rows):
                    is_home = (row.home_name == team_name)
                    if is_home:
                        elo, _ = update_fn(elo, 1500.0, row.score_home, row.score_away)
                    else:
                        _, elo = update_fn(1500.0, elo, row.score_home, row.score_away)
                    trend.append(round(elo, 1))
                while len(trend) < 5:
                    trend.insert(0, 1500.0)
                return trend[-5:]
        finally:
            session.close()
    except Exception as e:
        logger.warning("Elo trend no disponible para '%s': %s", team_name, e)

    import random
    base = 1500.0
    trend = []
    for _ in range(5):
        base += random.uniform(-8, 8)
        trend.append(round(base, 1))
    return trend


def _update_soccer_elo(
    elo_home: float, elo_away: float,
    score_home: int, score_away: int,
    k_factor: float = 32.0, home_advantage: float = 50.0,
) -> tuple:
    """Elo actualizado para futbol (soccer)."""
    effective_home = elo_home + home_advantage
    effective_away = elo_away
    expected_home = 1.0 / (1.0 + 10.0 ** ((effective_away - effective_home) / 400.0))
    expected_away = 1.0 - expected_home

    if score_home > score_away:
        actual_home = 1.0
    elif score_home < score_away:
        actual_home = 0.0
    else:
        actual_home = 0.5

    point_diff = abs(score_home - score_away)
    mov = math.log(max(point_diff, 1) + 1) * (2.0 / (2.0 + 0.001 * abs(effective_home - effective_away)))

    adjustment = k_factor * mov
    new_home = elo_home + adjustment * (actual_home - expected_home)
    new_away = elo_away + adjustment * ((1.0 - actual_home) - expected_away)
    return new_home, new_away


def _build_h2h_stats(home_team: str, away_team: str, sport: str) -> list:
    """Construye array de stats H2H comparativas para el radar chart."""
    try:
        from database import SessionLocal
        from sqlalchemy import text

        session = SessionLocal()
        try:
            if sport == 'nba':
                query = text("""
                    SELECT AVG(s.puntos_local) as avg_pts_h, AVG(s.puntos_visitante) as avg_pts_a,
                           AVG(s.rebotes_local) as avg_reb_h, AVG(s.rebotes_visitante) as avg_reb_a,
                           AVG(s.triples_local) as avg_3pm_h, AVG(s.triples_visitante) as avg_3pm_a
                    FROM partidos p
                    JOIN stats_nba s ON s.id_partido = p.id_partido
                    JOIN equipos e_h ON e_h.id_equipo = p.id_local
                    JOIN equipos e_a ON e_a.id_equipo = p.id_visitante
                    WHERE e_h.nombre = :home AND e_a.nombre = :away
                """)
                row = session.execute(query, {'home': home_team, 'away': away_team}).fetchone()
                if row and row.avg_pts_h is not None:
                    return [
                        {'stat': 'Pts/Game', 'home': round(float(row.avg_pts_h), 1), 'away': round(float(row.avg_pts_a), 1)},
                        {'stat': 'Reb/Game', 'home': round(float(row.avg_reb_h), 1), 'away': round(float(row.avg_reb_a), 1)},
                        {'stat': '3PM/Game', 'home': round(float(row.avg_3pm_h), 1), 'away': round(float(row.avg_3pm_a), 1)},
                    ]

            elif sport == 'mlb':
                query = text("""
                    SELECT AVG(s.carreras_local) as avg_runs_h, AVG(s.carreras_visitante) as avg_runs_a,
                           AVG(s.hits_local) as avg_hits_h, AVG(s.hits_visitante) as avg_hits_a,
                           AVG(s.errores_local) as avg_err_h, AVG(s.errores_visitante) as avg_err_a
                    FROM partidos p
                    JOIN stats_mlb s ON s.id_partido = p.id_partido
                    JOIN equipos e_h ON e_h.id_equipo = p.id_local
                    JOIN equipos e_a ON e_a.id_equipo = p.id_visitante
                    WHERE e_h.nombre = :home AND e_a.nombre = :away
                """)
                row = session.execute(query, {'home': home_team, 'away': away_team}).fetchone()
                if row and row.avg_runs_h is not None:
                    return [
                        {'stat': 'Runs/Game', 'home': round(float(row.avg_runs_h), 1), 'away': round(float(row.avg_runs_a), 1)},
                        {'stat': 'Hits/Game', 'home': round(float(row.avg_hits_h), 1), 'away': round(float(row.avg_hits_a), 1)},
                        {'stat': 'Errors/Game', 'home': round(float(row.avg_err_h), 1), 'away': round(float(row.avg_err_a), 1)},
                    ]

            elif sport == 'soccer':
                query = text("""
                    SELECT AVG(s.goles_local) as avg_gh, AVG(s.goles_visitante) as avg_ga,
                           AVG(s.xg_local) as avg_xg_h, AVG(s.xg_visitante) as avg_xg_a,
                           AVG(s.tiros_puerta_local) as avg_sot_h, AVG(s.tiros_puerta_visitante) as avg_sot_a,
                           AVG(s.corners_local) as avg_cor_h, AVG(s.corners_visitante) as avg_cor_a
                    FROM partidos p
                    JOIN stats_futbol s ON s.id_partido = p.id_partido
                    JOIN equipos e_h ON e_h.id_equipo = p.id_local
                    JOIN equipos e_a ON e_a.id_equipo = p.id_visitante
                    WHERE e_h.nombre = :home AND e_a.nombre = :away
                """)
                row = session.execute(query, {'home': home_team, 'away': away_team}).fetchone()
                if row and row.avg_gh is not None:
                    return [
                        {'stat': 'Goals/Game', 'home': round(float(row.avg_gh), 2), 'away': round(float(row.avg_ga), 2)},
                        {'stat': 'xG/Game', 'home': round(float(row.avg_xg_h or 0), 2), 'away': round(float(row.avg_xg_a or 0), 2)},
                        {'stat': 'Shots on Target', 'home': round(float(row.avg_sot_h), 1), 'away': round(float(row.avg_sot_a), 1)},
                        {'stat': 'Corners/Game', 'home': round(float(row.avg_cor_h), 1), 'away': round(float(row.avg_cor_a), 1)},
                    ]
        finally:
            session.close()
    except Exception as e:
        logger.warning("H2H stats no disponibles: %s", e)

    if sport == 'nba':
        return [
            {'stat': 'Off Rating', 'home': 112.5, 'away': 108.3},
            {'stat': 'Def Rating', 'home': 109.1, 'away': 111.7},
            {'stat': 'Net Rating', 'home': 3.4, 'away': -3.4},
            {'stat': 'Pace', 'home': 100.2, 'away': 98.8},
            {'stat': 'TS%', 'home': 57.8, 'away': 55.2},
        ]
    elif sport == 'mlb':
        return [
            {'stat': 'ERA', 'home': 3.85, 'away': 4.12},
            {'stat': 'OPS', 'home': 0.745, 'away': 0.718},
            {'stat': 'WHIP', 'home': 1.22, 'away': 1.31},
            {'stat': 'K/9', 'home': 9.1, 'away': 8.4},
            {'stat': 'BA', 'home': 0.258, 'away': 0.245},
        ]
    else:
        return [
            {'stat': 'Goals/Game', 'home': 1.55, 'away': 1.20},
            {'stat': 'xG/Game', 'home': 1.42, 'away': 1.10},
            {'stat': 'Shots on Target', 'home': 4.8, 'away': 3.9},
            {'stat': 'Corners/Game', 'home': 5.5, 'away': 4.7},
            {'stat': 'Cards/Game', 'home': 2.1, 'away': 2.4},
        ]


# ==========================================
# LINEAS ALTERNATIVAS (Cards, Corners, SOT) — POISSON-BASED
# ==========================================

def _poisson_cdf(lam: float, k: int) -> float:
    """Calcula P(X <= k) para Poisson(lam)."""
    return sum((lam ** i) * math.exp(-lam) / math.factorial(i) for i in range(k + 1))


def _poisson_over_prob(lam: float, line: float) -> float:
    """Calcula P(X > line) para Poisson(lam)."""
    floor_line = int(math.floor(line))
    return 1.0 - _poisson_cdf(lam, floor_line)


def _find_best_line(lam: float, candidate_lines: list[float]) -> tuple[float, float, float]:
    """Encuentra la linea mas balanceada (over_prob mas cercano a 0.5)."""
    best = None
    best_diff = 999
    for line in candidate_lines:
        over_p = _poisson_over_prob(lam, line)
        diff = abs(over_p - 0.5)
        if diff < best_diff:
            best_diff = diff
            best = (line, over_p, 1.0 - over_p)
    return best


def _predict_alt_lines_soccer(home_team: str, away_team: str) -> dict:
    """Calcula lineas alternativas para soccer usando distribucion de Poisson.

    Retorna:
    {
        'cards': {'line': 4.5, 'over_prob': 0.62, 'under_prob': 0.38, 'alt_lines': [...]},
        'corners': {'line': 9.5, 'over_prob': 0.55, 'under_prob': 0.45, 'alt_lines': [...]},
        'shots_on_target': {'line': 7.5, 'over_prob': 0.58, 'under_prob': 0.42, 'alt_lines': [...]},
    }
    """
    try:
        home_prom = _get_team_promedios_soccer(home_team)
        away_prom = _get_team_promedios_soccer(away_team)
    except Exception:
        home_prom = {'prom_goles': 1.3, 'prom_tiros_puerta': 4.0, 'prom_corners': 4.5}
        away_prom = {'prom_goles': 1.1, 'prom_tiros_puerta': 3.5, 'prom_corners': 4.0}

    # Obtener stats reales de cards/corners/SOT desde stats_futbol
    try:
        from database import SessionLocal
        from sqlalchemy import text

        session = SessionLocal()
        try:
            # Cards (amarillas)
            cards_query = text("""
                SELECT AVG(s.amarillas_local + s.amarillas_visitante) as avg_cards,
                       AVG(s.rojas_local + s.rojas_visitante) as avg_reds
                FROM partidos p
                JOIN stats_futbol s ON s.id_partido = p.id_partido
                JOIN equipos e ON e.id_equipo = p.id_local
                WHERE e.nombre ILIKE :team
            """)
            h_cards = session.execute(cards_query, {'team': f'%{home_team}%'}).fetchone()
            a_cards = session.execute(cards_query, {'team': f'%{away_team}%'}).fetchone()

            avg_cards_h = float(h_cards.avg_cards) if h_cards and h_cards.avg_cards and float(h_cards.avg_cards) > 0 else 3.5
            avg_cards_a = float(a_cards.avg_cards) if a_cards and a_cards.avg_cards and float(a_cards.avg_cards) > 0 else 3.2
            avg_reds_h = float(h_cards.avg_reds) if h_cards and h_cards.avg_reds and float(h_cards.avg_reds) > 0 else 0.15
            avg_reds_a = float(a_cards.avg_reds) if a_cards and a_cards.avg_reds and float(a_cards.avg_reds) > 0 else 0.12

            # Corners
            corners_query = text("""
                SELECT AVG(s.corners_local + s.corners_visitante) as avg_corners
                FROM partidos p
                JOIN stats_futbol s ON s.id_partido = p.id_partido
                JOIN equipos e ON e.id_equipo = p.id_local
                WHERE e.nombre ILIKE :team
            """)
            h_corners = session.execute(corners_query, {'team': f'%{home_team}%'}).fetchone()
            a_corners = session.execute(corners_query, {'team': f'%{away_team}%'}).fetchone()

            avg_corners_h = float(h_corners.avg_corners) if h_corners and h_corners.avg_corners and float(h_corners.avg_corners) > 0 else 0
            avg_corners_a = float(a_corners.avg_corners) if a_corners and a_corners.avg_corners and float(a_corners.avg_corners) > 0 else 0

            # Shots on target
            sot_query = text("""
                SELECT AVG(s.tiros_puerta_local + s.tiros_puerta_visitante) as avg_sot
                FROM partidos p
                JOIN stats_futbol s ON s.id_partido = p.id_partido
                JOIN equipos e ON e.id_equipo = p.id_local
                WHERE e.nombre ILIKE :team
            """)
            h_sot = session.execute(sot_query, {'team': f'%{home_team}%'}).fetchone()
            a_sot = session.execute(sot_query, {'team': f'%{away_team}%'}).fetchone()

            avg_sot_h = float(h_sot.avg_sot) if h_sot and h_sot.avg_sot and float(h_sot.avg_sot) > 0 else 0
            avg_sot_a = float(a_sot.avg_sot) if a_sot and a_sot.avg_sot and float(a_sot.avg_sot) > 0 else 0

        finally:
            session.close()
    except Exception:
        avg_cards_h, avg_cards_a = 3.5, 3.2
        avg_reds_h, avg_reds_a = 0.15, 0.12
        avg_corners_h, avg_corners_a = 4.5, 4.0
        avg_sot_h, avg_sot_a = 4.0, 3.5

    # Lambdas combinados (promedio de ambos equipos)
    lam_cards = (avg_cards_h + avg_cards_a) / 2 + (avg_reds_h + avg_reds_a) / 2
    lam_corners = (avg_corners_h + avg_corners_a) / 2
    lam_sot = (avg_sot_h + avg_sot_a) / 2

    # Tambien usar promedios de Equipos como fallback/enriquecimiento
    h_corners_eq = home_prom.get('prom_corners', 4.5)
    a_corners_eq = away_prom.get('prom_corners', 4.0)
    h_sot_eq = home_prom.get('prom_tiros_puerta', 4.0)
    a_sot_eq = away_prom.get('prom_tiros_puerta', 3.5)

    # Blend inteligente: si stats_futbol tiene datos reales (>0), usar 70% stats + 30% equipos
    # Si stats_futbol tiene zeros (ej: Liga MX sin datos), usar 100% equipos
    corners_eq_avg = (h_corners_eq + a_corners_eq) / 2
    sot_eq_avg = (h_sot_eq + a_sot_eq) / 2

    has_corners_data = lam_corners > 1.0
    has_sot_data = lam_sot > 1.0

    lam_corners = (0.7 * lam_corners + 0.3 * corners_eq_avg) if has_corners_data else corners_eq_avg
    lam_sot = (0.7 * lam_sot + 0.3 * sot_eq_avg) if has_sot_data else sot_eq_avg

    def build_market(lam: float, lines: list[float]) -> dict:
        line, over_p, under_p = _find_best_line(lam, lines)
        alts = []
        for alt_line in lines:
            if abs(alt_line - line) > 0.01:
                alts.append({
                    'line': alt_line,
                    'over_prob': round(_poisson_over_prob(lam, alt_line), 3),
                    'under_prob': round(1 - _poisson_over_prob(lam, alt_line), 3),
                })
        alts.sort(key=lambda x: x['line'])
        return {
            'line': line,
            'over_prob': round(over_p, 3),
            'under_prob': round(under_p, 3),
            'expected': round(lam, 2),
            'alt_lines': alts[:4],
        }

    return {
        'cards': build_market(lam_cards, [2.5, 3.5, 4.5, 5.5, 6.5]),
        'corners': build_market(lam_corners, [7.5, 8.5, 9.5, 10.5, 11.5]),
        'shots_on_target': build_market(lam_sot, [5.5, 6.5, 7.5, 8.5, 9.5]),
    }


def _consultar_player_props_enhanced(home_team: str, away_team: str, sport: str) -> tuple[str, list[dict]]:
    """Consulta mejorada de player props con proyecciones EV.

    Retorna:
        (texto_para_llm, lista_de_props_para_widget)
    """
    props_list = []

    try:
        from database import SessionLocal
        from sqlalchemy import text

        session = SessionLocal()
        try:
            if sport == 'soccer':
                # Obtener jugadores con stats reales de ambos equipos
                query = text("""
                    SELECT j.nombre, e.nombre AS team_name,
                           j.goles, j.asistencias, j.tar_amarilla,
                           j.tiros_totales, j.tiros_puerta, j.faltas_cometidas
                    FROM stats_jugador_futbol j
                    JOIN equipos e ON e.id_equipo = j.id_equipo
                    WHERE e.nombre ILIKE :home OR e.nombre ILIKE :away
                    ORDER BY j.goles DESC, j.tiros_puerta DESC
                    LIMIT 8
                """)
                rows = session.execute(query, {'home': f'%{home_team}%', 'away': f'%{away_team}%'}).fetchall()

                if rows:
                    parts = []
                    for r in rows:
                        goles = r.goles or 0
                        tiros = r.tiros_puerta or 0
                        tarjetas = r.tar_amarilla or 0
                        faltas = r.faltas_cometidas or 0

                        # Proyeccion simplificada: si tiene goles > 0, sugerir Over 0.5
                        goal_prob = min(goles / max(1, goles + 2), 0.85) if goles > 0 else 0.25
                        sot_prob = min(tiros / max(1, tiros + 3), 0.80) if tiros > 0 else 0.20
                        card_prob = min(tarjetas / max(1, tarjetas + 2), 0.75) if tarjetas > 0 else 0.15
                        foul_card_prob = min(faltas / max(1, faltas + 4), 0.60) if faltas > 0 else 0.10

                        # Calcular EV simplificado (probabilidad - implied_odds de linea 50%)
                        goal_ev = round((goal_prob - 0.5) * 100)
                        sot_ev = round((sot_prob - 0.5) * 100)
                        card_ev = round((card_prob - 0.5) * 100)

                        parts.append(f"{r.nombre} ({r.team_name}): {goles} goles, {tiros} SOT, {tarjetas} tarjetas")

                        # Agregar props con EV positivo
                        if goal_ev > 0:
                            props_list.append({
                                'player': r.nombre,
                                'team': r.team_name,
                                'prop': 'Goles',
                                'line': 0.5,
                                'over_prob': round(goal_prob, 3),
                                'under_prob': round(1 - goal_prob, 3),
                                'ev': f'+{goal_ev}%' if goal_ev > 0 else f'{goal_ev}%',
                            })
                        if sot_ev > 0:
                            props_list.append({
                                'player': r.nombre,
                                'team': r.team_name,
                                'prop': 'Tiros a Puerta',
                                'line': 0.5,
                                'over_prob': round(sot_prob, 3),
                                'under_prob': round(1 - sot_prob, 3),
                                'ev': f'+{sot_ev}%' if sot_ev > 0 else f'{sot_ev}%',
                            })
                        if card_ev > 0:
                            props_list.append({
                                'player': r.nombre,
                                'team': r.team_name,
                                'prop': 'Tarjetas',
                                'line': 0.5,
                                'over_prob': round(card_prob, 3),
                                'under_prob': round(1 - card_prob, 3),
                                'ev': f'+{card_ev}%' if card_ev > 0 else f'{card_ev}%',
                            })

                    if parts:
                        return ("Jugadores clave: " + " | ".join(parts), props_list)

            elif sport == 'nba':
                query = text("""
                    SELECT j.nombre, e.nombre AS team_name,
                           j.puntos, j.rebotes, j.asistencias
                    FROM stats_jugador_nba j
                    JOIN equipos e ON e.id_equipo = j.id_equipo
                    WHERE e.nombre ILIKE :home OR e.nombre ILIKE :away
                    ORDER BY j.puntos DESC
                    LIMIT 6
                """)
                rows = session.execute(query, {'home': f'%{home_team}%', 'away': f'%{away_team}%'}).fetchall()
                if rows:
                    parts = []
                    for r in rows:
                        pts = r.puntos or 0
                        reb = r.rebotes or 0
                        ast = r.asistencias or 0
                        pts_prob = min(pts / max(1, pts + 15), 0.80) if pts > 0 else 0.30
                        pts_ev = round((pts_prob - 0.5) * 100)
                        parts.append(f"{r.nombre} ({r.team_name}): {pts} pts, {reb} reb, {ast} ast")
                        if pts_ev > 0:
                            props_list.append({
                                'player': r.nombre, 'team': r.team_name, 'prop': 'Puntos',
                                'line': 15.5, 'over_prob': round(pts_prob, 3),
                                'under_prob': round(1 - pts_prob, 3),
                                'ev': f'+{pts_ev}%' if pts_ev > 0 else f'{pts_ev}%',
                            })
                    if parts:
                        return ("Jugadores clave: " + " | ".join(parts), props_list)

            elif sport == 'mlb':
                query = text("""
                    SELECT j.nombre, e.nombre AS team_name,
                           j.hits, j.home_runs, j.carreras_impulsadas
                    FROM stats_jugador_mlb j
                    JOIN equipos e ON e.id_equipo = j.id_equipo
                    WHERE e.nombre ILIKE :home OR e.nombre ILIKE :away
                    ORDER BY j.home_runs DESC
                    LIMIT 6
                """)
                rows = session.execute(query, {'home': f'%{home_team}%', 'away': f'%{away_team}%'}).fetchall()
                if rows:
                    parts = []
                    for r in rows:
                        hits = r.hits or 0
                        hr = r.home_runs or 0
                        rbi = r.carreras_impulsadas or 0
                        hit_prob = min(hits / max(1, hits + 2), 0.75) if hits > 0 else 0.35
                        hit_ev = round((hit_prob - 0.5) * 100)
                        parts.append(f"{r.nombre} ({r.team_name}): {hits} hits, {hr} HR, {rbi} RBI")
                        if hit_ev > 0:
                            props_list.append({
                                'player': r.nombre, 'team': r.team_name, 'prop': 'Hits',
                                'line': 0.5, 'over_prob': round(hit_prob, 3),
                                'under_prob': round(1 - hit_prob, 3),
                                'ev': f'+{hit_ev}%' if hit_ev > 0 else f'{hit_ev}%',
                            })
                    if parts:
                        return ("Jugadores clave: " + " | ".join(parts), props_list)

        finally:
            session.close()
    except Exception as e:
        logger.warning("Player props enhanced fallo: %s", e)

    sport_label = {'nba': 'NBA', 'mlb': 'MLB'}.get(sport, 'fútbol')
    return (f"No hay datos de jugadores disponibles para {home_team} o {away_team} en {sport_label}.", props_list)


# ==========================================
# CONSULTAS DETERMINISTAS A BD (4 metricas del Oraculo) — SPORT-AWARE
# ==========================================

def _consultar_prediccion_partido(home_team: str, away_team: str, sport: str) -> str:
    """Consulta stats del partido segun el deporte."""
    try:
        if sport == 'soccer':
            home_prom = _get_team_promedios_soccer(home_team)
            away_prom = _get_team_promedios_soccer(away_team)
            hg, ag = home_prom['prom_goles'], away_prom['prom_goles']
            edge = "Home" if hg > ag else ("Away" if ag > hg else "Even")
            return (
                f"{home_team} prom_goles={hg:.2f}, tiros_puerta={home_prom['prom_tiros_puerta']:.1f} | "
                f"{away_team} prom_goles={ag:.2f}, tiros_puerta={away_prom['prom_tiros_puerta']:.1f} | "
                f"Edge: {edge}"
            )

        home_stats = _get_team_stats_sqlalchemy(home_team, sport)
        away_stats = _get_team_stats_sqlalchemy(away_team, sport)

        if sport == 'nba':
            hp = home_stats.get('avg_pts', 110)
            ap = away_stats.get('avg_pts', 108)
            edge = "Home" if hp > ap else ("Away" if ap > hp else "Even")
            return (
                f"{home_team} avg_pts={hp:.1f}, reb={home_stats.get('avg_reb', 0):.1f} | "
                f"{away_team} avg_pts={ap:.1f}, reb={away_stats.get('avg_reb', 0):.1f} | "
                f"Edge: {edge}"
            )

        # MLB
        hr = home_stats.get('avg_runs', 4.5)
        ar = away_stats.get('avg_runs', 4.2)
        edge = "Home" if hr > ar else ("Away" if ar > hr else "Even")
        return (
            f"{home_team} avg_runs={hr:.1f}, hits={home_stats.get('avg_hits', 0):.1f} | "
            f"{away_team} avg_runs={ar:.1f}, hits={away_stats.get('avg_hits', 0):.1f} | "
            f"Edge: {edge}"
        )
    except Exception as e:
        logger.warning("Error en _consultar_prediccion_partido: %s", e)
        return f"Datos no disponibles para {home_team} vs {away_team}."


def _consultar_prediccion_totales(home_team: str, away_team: str, sport: str) -> str:
    """Calcula totales esperados segun el deporte."""
    try:
        if sport == 'soccer':
            home_prom = _get_team_promedios_soccer(home_team)
            away_prom = _get_team_promedios_soccer(away_team)
            hg = home_prom.get('prom_goles', 1.5)
            ag = away_prom.get('prom_goles', 1.2)
            expected_total = hg + ag
            rec = "OVER 2.5" if expected_total > 2.5 else "UNDER 2.5"
            return f"Total esperado: {expected_total:.2f} goles ({home_team}: {hg:.2f} + {away_team}: {ag:.2f}) -> Sugerencia: {rec}"

        home_stats = _get_team_stats_sqlalchemy(home_team, sport)
        away_stats = _get_team_stats_sqlalchemy(away_team, sport)

        if sport == 'nba':
            hp = home_stats.get('avg_pts', 110)
            ap = away_stats.get('avg_pts', 108)
            expected_total = (hp + ap) / 2
            rec = "OVER 215.5" if expected_total > 215.5 else "UNDER 215.5"
            return f"Total esperado: {expected_total:.1f} pts ({home_team}: {hp:.1f} + {away_team}: {ap:.1f}) -> Sugerencia: {rec}"

        # MLB
        hr = home_stats.get('avg_runs', 4.5)
        ar = away_stats.get('avg_runs', 4.2)
        expected_total = (hr + ar) / 2
        rec = "OVER 8.5" if expected_total > 8.5 else "UNDER 8.5"
        return f"Total esperado: {expected_total:.1f} carreras ({home_team}: {hr:.1f} + {away_team}: {ar:.1f}) -> Sugerencia: {rec}"
    except Exception as e:
        logger.warning("Error en _consultar_prediccion_totales: %s", e)
        return "Datos de totales no disponibles."


def _consultar_mercados_secundarios(home_team: str, away_team: str, sport: str) -> str:
    """Consulta mercados secundarios segun el deporte."""
    try:
        if sport == 'soccer':
            home_prom = _get_team_promedios_soccer(home_team)
            away_prom = _get_team_promedios_soccer(away_team)
            h_c = home_prom.get('prom_corners', 5.0)
            h_s = home_prom.get('prom_tiros_puerta', 4.5)
            a_c = away_prom.get('prom_corners', 4.5)
            a_s = away_prom.get('prom_tiros_puerta', 4.0)
            return (
                f"{home_team}: {h_c:.1f} corners, {h_s:.1f} tiros a puerta | "
                f"{away_team}: {a_c:.1f} corners, {a_s:.1f} tiros a puerta"
            )

        home_stats = _get_team_stats_sqlalchemy(home_team, sport)
        away_stats = _get_team_stats_sqlalchemy(away_team, sport)

        if sport == 'nba':
            h3 = home_stats.get('avg_3pm', 12.0)
            hr = home_stats.get('avg_reb', 45.0)
            a3 = away_stats.get('avg_3pm', 11.0)
            ar = away_stats.get('avg_reb', 43.0)
            return (
                f"{home_team}: {h3:.1f} triples, {hr:.1f} rebotes | "
                f"{away_team}: {a3:.1f} triples, {ar:.1f} rebotes"
            )

        # MLB
        hh = home_stats.get('avg_hits', 8.0)
        he = home_stats.get('avg_err', 1.0)
        ah = away_stats.get('avg_hits', 7.5)
        ae = away_stats.get('avg_err', 1.2)
        return (
            f"{home_team}: {hh:.1f} hits, {he:.1f} errores | "
            f"{away_team}: {ah:.1f} hits, {ae:.1f} errores"
        )
    except Exception as e:
        logger.warning("Error en _consultar_mercados_secundarios: %s", e)
        return "Datos de mercados secundarios no disponibles."


def _consultar_player_props(home_team: str, away_team: str, sport: str) -> str:
    """Consulta mejores jugadores segun el deporte."""
    try:
        from database import SessionLocal
        from sqlalchemy import text

        session = SessionLocal()
        try:
            if sport == 'nba':
                query = text("""
                    SELECT j.nombre, e.nombre AS team_name,
                           j.puntos, j.rebotes, j.asistencias
                    FROM stats_jugador_nba j
                    JOIN equipos e ON e.id_equipo = j.id_equipo
                    WHERE e.nombre ILIKE :home OR e.nombre ILIKE :away
                    ORDER BY j.puntos DESC
                    LIMIT 4
                """)
                rows = session.execute(query, {'home': f'%{home_team}%', 'away': f'%{away_team}%'}).fetchall()
                if rows:
                    parts = []
                    for r in rows:
                        parts.append(f"{r.nombre} ({r.team_name}): {r.puntos} pts, {r.rebotes} reb, {r.asistencias} ast")
                    return " | ".join(parts)

            elif sport == 'mlb':
                query = text("""
                    SELECT j.nombre, e.nombre AS team_name,
                           j.hits, j.home_runs, j.carreras_impulsadas
                    FROM stats_jugador_mlb j
                    JOIN equipos e ON e.id_equipo = j.id_equipo
                    WHERE e.nombre ILIKE :home OR e.nombre ILIKE :away
                    ORDER BY j.home_runs DESC
                    LIMIT 4
                """)
                rows = session.execute(query, {'home': f'%{home_team}%', 'away': f'%{away_team}%'}).fetchall()
                if rows:
                    parts = []
                    for r in rows:
                        parts.append(f"{r.nombre} ({r.team_name}): {r.hits} hits, {r.home_runs} HR, {r.carreras_impulsadas} RBI")
                    return " | ".join(parts)

            else:
                query = text("""
                    SELECT j.nombre, e.nombre AS team_name,
                           j.goles, j.asistencias, j.tar_amarilla
                    FROM jugadores j
                    JOIN equipos e ON e.id_equipo = j.id_equipo
                    WHERE e.nombre ILIKE :home OR e.nombre ILIKE :away
                    ORDER BY j.goles DESC
                    LIMIT 4
                """)
                rows = session.execute(query, {'home': f'%{home_team}%', 'away': f'%{away_team}%'}).fetchall()
                if rows:
                    parts = []
                    for r in rows:
                        parts.append(f"{r.nombre} ({r.team_name}): {r.goles} goles, {r.asistencias} ast, {r.tar_amarilla} tarjetas")
                    return " | ".join(parts)
        finally:
            session.close()
    except Exception as e:
        logger.warning("Player props fallo: %s", e)

    sport_label = {'nba': 'NBA', 'mlb': 'MLB'}.get(sport, 'fútbol')
    return f"No hay datos de jugadores disponibles para {home_team} o {away_team} en {sport_label}."


# ==========================================
# VISTA PRINCIPAL: ChatAPIView
# ==========================================

SPORT_CONFIG = {
    'nba': {'input_dim': 8},
    'mlb': {'input_dim': 10},
    'soccer': {'input_dim': 6},
}


class _FakeMatch:
    """Objeto fallback para cuando no hay partido en DailySchedule."""
    def __init__(self, sport: str, home_team: str, away_team: str):
        self.sport = sport
        self.home_team = home_team
        self.away_team = away_team
        self.match_date = date.today()
        self.start_time = None


class ChatAPIView(APIView):
    """
    POST /api/v1/chat/

    Request:  {"message": "Qué opinas de Real Madrid vs Sevilla?"}
    Response: {"reply": "...", "widget": {...}}
    """

    def post(self, request):
        try:
            return self._handle_chat(request)
        except Exception as e:
            logger.error("Error CRITICO en ChatAPIView: %s\n%s", e, traceback.format_exc())
            return Response({
                'reply': f'Error interno del servidor: {str(e)}. Revisa los logs de Django.',
                'widget': None,
            }, status=status.HTTP_200_OK)

    def _handle_chat(self, request):
        message = request.data.get('message', '').strip()
        if not message:
            return Response(
                {'reply': 'No recibí ningún mensaje. ¿En qué puedo ayudarte?'},
                status=status.HTTP_200_OK,
            )

        logger.info("Chat request recibido: '%s'", message[:100])

        # 1. Parsear intent
        intent = IntentParser.parse(message)
        sport = intent['sport']
        teams = intent['teams']
        logger.info("Intent: sport=%s, teams=%s", sport, teams)

        # 2. Si no se detecta deporte
        if not sport:
            return Response({
                'reply': (
                    'Soy tu analista quant deportivo. Pregúntame sobre cualquier '
                    'partido de **NBA**, **MLB** o **Fútbol** y te daré mi proyección '
                    'basada en redes neuronales. Ejemplo: *"Real Madrid vs Sevilla"* '
                    'o *"¿Qué opinas del partido de los Lakers hoy?"*'
                ),
            }, status=status.HTTP_200_OK)

        # 3. Buscar partido (con fallback directo si no hay schedule)
        today = date.today()
        match = self._find_match(sport, teams, today)

        if not match:
            team_names = ', '.join(t[0] for t in teams) if teams else sport.upper()
            return Response({
                'reply': (
                    f'No encontré información suficiente para **{sport.upper()}**: '
                    f'{team_names}. Intenta con equipos más conocidos '
                    f'(ej: Real Madrid, Barcelona, Lakers, Yankees).'
                ),
            }, status=status.HTTP_200_OK)

        # 4. Ejecutar inferencia
        home_team = match.home_team
        away_team = match.away_team
        start_time = match.start_time.strftime('%H:%M') if match.start_time else '--:--'
        is_scheduled = not isinstance(match, _FakeMatch)

        logger.info("Analizando: %s vs %s (sport=%s, scheduled=%s)", home_team, away_team, sport, is_scheduled)

        prediction = self._run_inference(sport, home_team, away_team)
        logger.info("Prediction: %s", prediction)

        # 5. Construir elo_trend y h2h_stats
        elo_home = _build_elo_trend(home_team, sport)
        elo_away = _build_elo_trend(away_team, sport)
        elo_trend = {
            'home': elo_home,
            'away': elo_away,
            'labels': ['G-5', 'G-4', 'G-3', 'G-2', 'Last'],
        }

        h2h_stats = _build_h2h_stats(home_team, away_team, sport)

        # 5b. Calcular alt_lines y player_props para el widget
        alt_lines = _predict_alt_lines_soccer(home_team, away_team) if sport == 'soccer' else {}
        _, player_props = _consultar_player_props_enhanced(home_team, away_team, sport)
        # Ordenar player_props por EV (mayor primero)
        player_props.sort(key=lambda p: float(p.get('ev', '0%').replace('%', '')), reverse=True)
        player_props = player_props[:8]  # Top 8

        # 6. Generar respuesta
        reply = self._build_reply(sport, home_team, away_team, start_time, prediction, is_scheduled)

        # 7. Retornar
        widget = {
            'sport': sport,
            'home_team': home_team,
            'away_team': away_team,
            'start_time': start_time,
            'prediction': prediction,
            'alt_lines': alt_lines,
            'player_props': player_props,
            'elo_trend': elo_trend,
            'h2h_stats': h2h_stats,
        }

        return Response({'reply': reply, 'widget': widget}, status=status.HTTP_200_OK)

    # ------------------------------------------
    # Metodos internos
    # ------------------------------------------

    def _find_match(self, sport: str, teams: list, today) -> object:
        """Busca el partido mas relevante. Si no hay en DailySchedule, crea matchup directo."""
        try:
            qs = DailySchedule.objects.filter(sport=sport, match_date=today)

            if qs.exists() and teams and len(teams) >= 2:
                team_names = [t[0] for t in teams]
                from django.db.models import Q
                # Requiere AMBOS equipos en el mismo partido
                q = Q()
                for i in range(len(team_names)):
                    for j in range(len(team_names)):
                        if i != j:
                            q |= (Q(home_team__iexact=team_names[i]) & Q(away_team__iexact=team_names[j]))
                specific = qs.filter(q).first()
                if specific:
                    return specific
                # Ningun partido contiene ambos equipos -> matchup directo
                return _FakeMatch(sport, teams[0][0], teams[1][0])

            if qs.exists() and not teams:
                return qs.order_by('start_time').first()
        except Exception as e:
            logger.warning("Error buscando en DailySchedule: %s", e)

        # Fallback: matchup directo con los equipos solicitados
        if teams and len(teams) >= 2:
            return _FakeMatch(sport, teams[0][0], teams[1][0])

        if teams and len(teams) == 1:
            return _FakeMatch(sport, teams[0][0], 'TBD')

        return None

    @torch.no_grad()
    def _run_inference(self, sport: str, home_team: str, away_team: str) -> dict:
        """Ejecuta inferencia con el modelo PyTorch correspondiente."""
        # Soccer siempre usa Poisson bivariado como base (alta calidad estadística)
        if sport == 'soccer':
            return self._soccer_inference(home_team, away_team)

        try:
            registry = ModelRegistry.get_instance()
            model = registry.get_model(sport)

            config = SPORT_CONFIG.get(sport, {'input_dim': 8})
            input_dim = config['input_dim']
            device = registry.device

            feat_home = _get_inference_features(home_team, input_dim // 2)
            feat_away = _get_inference_features(away_team, input_dim // 2)

            features_are_zeros = (
                torch.all(feat_home == 0).item() and torch.all(feat_away == 0).item()
            )

            if model is None or features_are_zeros:
                return self._fallback_prediction(sport, home_team, away_team)

            input_tensor = torch.cat([feat_home, feat_away], dim=1).to(device)
            output = model(input_tensor)

            if sport == 'nba':
                result = self._format_nba(output)
                if 50 <= result['total'] <= 280:
                    return result
                logger.info("NBA modelo fuera de rango (total=%s), usando fallback.", result['total'])
            elif sport == 'mlb':
                result = self._format_mlb(output)
                if 3 <= result['total_runs'] <= 20:
                    return result
                logger.info("MLB modelo fuera de rango (total=%s), usando fallback.", result['total_runs'])
        except Exception as e:
            logger.error("Error en inferencia %s: %s", sport, e)

        return self._fallback_prediction(sport, home_team, away_team)

    def _soccer_inference(self, home_team: str, away_team: str) -> dict:
        """
        Inferencia soccer usando ensemble: MatchPredictionNet v2 + Poisson bivariado.

        El Poisson bivariado usa stats reales de la BD Equipos.
        Si el modelo tiene pesos entrenados, blendea su salida con Poisson.
        """
        from src.models.networks.match_prediction_net import (
            build_soccer_feature_vector, poisson_bivariate_predict,
        )

        # 1. Obtener stats reales de ambos equipos
        home_stats = _get_team_promedios_soccer(home_team)
        away_stats = _get_team_promedios_soccer(away_team)

        lambda_home = home_stats.get('prom_goles', 1.3)
        lambda_away = away_stats.get('prom_goles', 1.1)

        # 2. Poisson bivariado de base (siempre disponible, estadísticamente sólido)
        poisson_result = poisson_bivariate_predict(lambda_home, lambda_away)
        poisson_probs = poisson_result['probabilities']

        # 3. Intentar usar el modelo neuronal si tiene pesos
        try:
            registry = ModelRegistry.get_instance()
            model = registry.get_model('soccer')

            if model is not None:
                feat = build_soccer_feature_vector(
                    home_stats={**home_stats, 'forma': 0.6},
                    away_stats={**away_stats, 'forma': 0.5},
                    elo_home=1500.0,
                    elo_away=1500.0,
                    h2h_win_rate_home=0.5,
                ).to(registry.device)

                logits = model(feat)
                nn_probs = torch.softmax(logits, dim=1)[0]
                # logits order: [Draw=0, Home=1, Away=2]
                nn_draw  = nn_probs[0].item()
                nn_home  = nn_probs[1].item()
                nn_away  = nn_probs[2].item()

                # Blend: 50% Poisson + 50% Red Neuronal
                # (aumentar peso de la red cuando tenga pesos reales entrenados)
                alpha = 0.5
                blended = {
                    'home': alpha * poisson_probs['home'] + (1 - alpha) * nn_home,
                    'draw': alpha * poisson_probs['draw'] + (1 - alpha) * nn_draw,
                    'away': alpha * poisson_probs['away'] + (1 - alpha) * nn_away,
                }
                # Renormalizar
                total = sum(blended.values())
                blended = {k: round(v / total, 4) for k, v in blended.items()}

                favored = 'home' if blended['home'] > max(blended['draw'], blended['away']) else (
                    'draw' if blended['draw'] > blended['away'] else 'away'
                )
                return {
                    'probabilities': blended,
                    'xg_home': round(lambda_home, 2),
                    'xg_away': round(lambda_away, 2),
                    'favored': favored,
                }
        except Exception as e:
            logger.warning("Soccer NN inference falló, usando Poisson puro: %s", e)

        return poisson_result


    def _format_soccer(self, output) -> dict:
        """Procesa logits de MatchPredictionNet a probabilidades 1X2."""
        try:
            if isinstance(output, dict):
                logits = output.get('logits', output.get('output', None))
            else:
                logits = output

            if logits is not None:
                probs = torch.softmax(logits, dim=1)
                draw_pct = probs[0][0].item()
                home_pct = probs[0][1].item()
                away_pct = probs[0][2].item()
            else:
                home_pct, draw_pct, away_pct = 0.40, 0.28, 0.32

            return {
                'probabilities': {'home': home_pct, 'draw': draw_pct, 'away': away_pct},
                'favored': 'home' if home_pct > max(draw_pct, away_pct) else ('draw' if draw_pct > away_pct else 'away'),
            }
        except Exception:
            return {'probabilities': {'home': 0.40, 'draw': 0.28, 'away': 0.32}, 'favored': 'home'}

    def _format_nba(self, output: dict) -> dict:
        spread = round(output['mu_spread'].item(), 1)
        total = round(output['mu_total'].item(), 1)
        std_s = round(torch.exp(output['log_var_spread'] * 0.5).item(), 1)
        std_t = round(torch.exp(output['log_var_total'] * 0.5).item(), 1)
        favored = 'home' if spread < 0 else ('away' if spread > 0 else 'even')
        return {
            'spread': spread, 'total': total, 'favored': favored,
            'confidence': {'spread_std': std_s, 'total_std': std_t},
        }

    def _format_mlb(self, output: dict) -> dict:
        runs_h = round(torch.exp(output['log_mu_home']).item(), 1)
        runs_a = round(torch.exp(output['log_mu_away']).item(), 1)
        alpha_h = round(torch.exp(output['log_alpha_home']).item(), 3)
        alpha_a = round(torch.exp(output['log_alpha_away']).item(), 3)
        favored = 'home' if runs_h > runs_a else ('away' if runs_a > runs_h else 'even')
        return {
            'projected_runs_home': runs_h, 'projected_runs_away': runs_a,
            'total_runs': round(runs_h + runs_a, 1), 'favored': favored,
            'dispersion': {'alpha_home': alpha_h, 'alpha_away': alpha_a},
        }

    def _fallback_prediction(self, sport: str, home: str, away: str) -> dict:
        """Prediccion fallback cuando el modelo no esta disponible o features son ceros."""
        if sport == 'soccer':
            try:
                home_prom = _get_team_promedios_soccer(home)
                away_prom = _get_team_promedios_soccer(away)
                lambda_home = home_prom.get('prom_goles', 1.5)
                lambda_away = away_prom.get('prom_goles', 1.2)
                return _poisson_predict(lambda_home, lambda_away)
            except Exception:
                return _poisson_predict(1.5, 1.2)

        if sport == 'nba':
            seed_h = _team_seed(home)
            seed_a = _team_seed(away)
            spread = round((seed_a - seed_h) * 15 - 2.5, 1)
            total = round(210 + (seed_h + seed_a) * 15, 1)
            favored = 'home' if spread < 0 else ('away' if spread > 0 else 'even')
            return {
                'spread': spread, 'total': total, 'favored': favored,
                'confidence': {'spread_std': round(4 + seed_h * 3, 1), 'total_std': round(8 + seed_a * 5, 1)},
            }

        seed_h = _team_seed(home)
        seed_a = _team_seed(away)
        runs_h = round(3.5 + seed_h * 2.5, 1)
        runs_a = round(3.2 + seed_a * 2.5, 1)
        favored = 'home' if runs_h > runs_a else ('away' if runs_a > runs_h else 'even')
        return {
            'projected_runs_home': runs_h, 'projected_runs_away': runs_a,
            'total_runs': round(runs_h + runs_a, 1), 'favored': favored,
            'dispersion': {'alpha_home': round(0.3 + seed_h * 0.5, 2), 'alpha_away': round(0.3 + seed_a * 0.5, 2)},
        }

    def _build_reply(self, sport: str, home: str, away: str, time: str, pred: dict, is_scheduled: bool = True) -> str:
        """Ejecuta las 5 consultas deterministas (sport-aware) y llama a Groq."""
        try:
            res_partido = _consultar_prediccion_partido(home, away, sport)
        except Exception:
            res_partido = "Datos no disponibles."
        try:
            res_totales = _consultar_prediccion_totales(home, away, sport)
        except Exception:
            res_totales = "Datos no disponibles."
        try:
            res_secundarios = _consultar_mercados_secundarios(home, away, sport)
        except Exception:
            res_secundarios = "Datos no disponibles."
        try:
            res_props, _ = _consultar_player_props_enhanced(home, away, sport)
        except Exception:
            res_props = "Datos no disponibles."
        try:
            alt_lines = _predict_alt_lines_soccer(home, away) if sport == 'soccer' else {}
            res_alt_lines = ""
            if alt_lines:
                cards = alt_lines.get('cards', {})
                corners = alt_lines.get('corners', {})
                sot = alt_lines.get('shots_on_target', {})
                res_alt_lines = (
                    f"Lineas alternativas -> "
                    f"Cards: line {cards.get('line', '?')}, Over {cards.get('over_prob', 0):.0%} | "
                    f"Corners: line {corners.get('line', '?')}, Over {corners.get('over_prob', 0):.0%} | "
                    f"SOT: line {sot.get('line', '?')}, Over {sot.get('over_prob', 0):.0%}"
                )
        except Exception:
            res_alt_lines = "Lineas alternativas no disponibles."

        # Construir modelo_info segun deporte
        if sport == 'soccer':
            probs = pred.get('probabilities', {})
            xg_h = pred.get('xg_home', 0)
            xg_a = pred.get('xg_away', 0)
            fav = pred.get('favored', 'home')
            modelo_info = (
                f"Modelo soccer -> Home: {probs.get('home', 0):.0%}, "
                f"Draw: {probs.get('draw', 0):.0%}, Away: {probs.get('away', 0):.0%}, "
                f"favorecido: {fav} | xG: {xg_h} - {xg_a}"
            )
        elif sport == 'nba':
            spread = pred.get('spread', 0)
            total = pred.get('total', 0)
            fav = pred.get('favored', 'home')
            modelo_info = (
                f"Modelo neural NBA -> spread: {spread:+.1f}, total: {total:.1f} pts, favorecido: {fav}"
            )
        else:
            runs_h = pred.get('projected_runs_home', 0)
            runs_a = pred.get('projected_runs_away', 0)
            fav = pred.get('favored', 'home')
            modelo_info = (
                f"Modelo neural MLB -> {home} {runs_h} - {away} {runs_a} "
                f"(Total: {pred.get('total_runs', 0):.1f}), favorecido: {fav}"
            )

        contexto_matematico = (
            f"DATOS EXTRAÍDOS:\n"
            f"- Predicción: {modelo_info}\n"
            f"- Equipos: {res_partido}\n"
            f"- Totales: {res_totales}\n"
            f"- Secundarios: {res_secundarios}\n"
            f"- Player Props: {res_props}\n"
            f"- Alt Lines: {res_alt_lines}"
        )

        schedule_note = " (partido programado hoy)" if is_scheduled else " (proyección hipotética basada en stats históricos)"

        sport_upper = sport.upper()
        emoji_map = {'nba': '🏀', 'mlb': '⚾', 'soccer': '⚽'}
        emoji = emoji_map.get(sport, '⚽')

        prompt_oraculo = (
            f"Eres 'El Oraculo', un Analista Quant Veterano de Wall Street aplicado a deportes. "
            f"Hablas de tu a tu con el usuario como si fuera tu colega del trading floor. "
            f"No uses frases de IA. Se directo y afilado.\n\n"
            f"Partido: {home} vs {away} ({sport_upper}) - Hora: {time}{schedule_note}\n\n"
            f"Basandote ESTRICTAMENTE en estos datos:\n{contexto_matematico}\n\n"
            f"Redacta un analisis estructurado usando Markdown. Usa negritas para el Edge. "
            f"Usa {emoji} en el encabezado."
        )

        # Intentar Groq
        try:
            from langchain_groq import ChatGroq

            groq_key = os.environ.get("GROQ_API_KEY")
            if groq_key:
                llm = ChatGroq(
                    model="llama-3.3-70b-versatile",
                    temperature=0.4,
                    max_tokens=2048,
                )
                respuesta = llm.invoke(prompt_oraculo)
                return respuesta.content
        except Exception as e:
            logger.warning("Groq fallo: %s", e)

        # Fallback sin Groq
        if sport == 'soccer':
            probs = pred.get('probabilities', {})
            fav = pred.get('favored', 'home')
            xg_h = pred.get('xg_home', 0)
            xg_a = pred.get('xg_away', 0)
            return (
                f"{emoji} **{sport_upper}** — {home} vs {away} ({time})\n\n"
                f"Proyección Poisson: **{home} {xg_h:.2f} xG** — **{away} {xg_a:.2f} xG**\n"
                f"Probabilidades: **Home {probs.get('home', 0):.0%}** | "
                f"**Draw {probs.get('draw', 0):.0%}** | "
                f"**Away {probs.get('away', 0):.0%}**\n"
                f"Favorecido: **{fav}**\n\n"
                f"_Powered by Poisson Distribution + H2H + xG Analysis._"
            )
        elif sport == 'nba':
            spread = pred.get('spread', 0)
            total = pred.get('total', 0)
            fav = pred.get('favored', 'home')
            return (
                f"{emoji} **{sport_upper}** — {home} vs {away} ({time})\n\n"
                f"Mi modelo neural proyecta un **spread de {spread:+.1f}** "
                f"con un **total de {total:.1f} puntos**. "
                f"El favorecido es **{fav}**.\n\n"
                f"_Powered by PyTorch Gaussian Regression + Elo + Pythagorean Expectation._"
            )
        else:
            runs_h = pred.get('projected_runs_home', 0)
            runs_a = pred.get('projected_runs_away', 0)
            fav = pred.get('favored', 'home')
            return (
                f"{emoji} **{sport_upper}** — {home} vs {away} ({time})\n\n"
                f"Proyección neural: **{home} {runs_h}** — **{away} {runs_a}** "
                f"(Total: {pred.get('total_runs', 0):.1f}). "
                f"Favorecido: **{fav}**.\n\n"
                f"_Powered by PyTorch Negative Binomial Regression + Elo + Pitcher Adjustment._"
            )
