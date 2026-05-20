"""
player_prop_engine.py — Motor de análisis de Player Props multi-deporte.

Responsabilidades:
- Consulta odds reales de The-Odds-API con fallback a líneas estimadas
- Extrae game logs históricos de jugadores (NBA, MLB, Soccer)
- Calcula promedios móviles (L5, L10, season)
- Detecta tendencias (regresión lineal sobre últimos juegos)
- Splits home/away y historial vs oponente
- Detección de rachas activas
- Cálculo de Expected Value (EV) real
- Genera props con recomendación y confianza
"""

import logging
import math
import os
import hashlib
from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np
import requests
import torch

from database import SessionLocal
from src.data.models import (
    PlayerStatsNBA, PlayerStatsMLB, PlayerStatsFutbol,
    Match, NBAPlayerHistory, Team,
)
from sqlalchemy import text

logger = logging.getLogger(__name__)

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

SPORT_ODDS_KEYS = {
    "soccer": ["soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a",
               "soccer_germany_bundesliga", "soccer_france_ligue_one",
               "soccer_mexico_ligamx", "soccer_uefa_champs_league"],
    "nba": ["basketball_nba"],
    "mlb": ["baseball_mlb"],
}

PROP_MARKETS = {
    "soccer": ["player_goals", "player_shots_on_target", "player_assists"],
    "nba": ["player_points", "player_rebounds", "player_assists",
            "player_threes", "player_pts_reb_ast"],
    "mlb": ["player_hits", "player_home_runs", "player_rbis",
            "player_pitcher_strikeouts"],
}


# ============================================================
# 1. ODDS API — Líneas reales de casinos
# ============================================================

def fetch_odds(sport: str) -> list[dict]:
    """
    Consulta The-Odds-API para obtener líneas de player props.
    Retorna lista de dicts con: player_name, market, line, odds_decimal, team, opponent.
    Fallback a líneas estimadas si no hay API key o no hay datos.
    """
    if not ODDS_API_KEY:
        logger.info("ODDS_API_KEY no configurada. Usando líneas estimadas.")
        return []

    odds_keys = SPORT_ODDS_KEYS.get(sport, [])
    all_odds = []

    for odds_key in odds_keys:
        try:
            url = f"{ODDS_API_BASE}/sports/{odds_key}/odds"
            params = {
                "apiKey": ODDS_API_KEY,
                "regions": "us,eu",
                "markets": "h2h,totals",
                "oddsFormat": "decimal",
            }
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                events = resp.json()
                for event in events:
                    home = event.get("home_team", "")
                    away = event.get("away_team", "")
                    bookmakers = event.get("bookmakers", [])
                    for bm in bookmakers:
                        for mkt in bm.get("markets", []):
                            if mkt.get("key") == "totals":
                                for outcome in mkt.get("outcomes", []):
                                    all_odds.append({
                                        "market": outcome.get("name", "totals"),
                                        "line": outcome.get("point", 0),
                                        "odds_decimal": outcome.get("price", 1.91),
                                        "home_team": home,
                                        "away_team": away,
                                        "sport": sport,
                                    })
        except Exception as e:
            logger.warning(f"Error fetching odds for {odds_key}: {e}")

    return all_odds


def estimate_player_line(player_avg: float, player_std: float, prop_type: str) -> tuple[float, float]:
    """
    Estima línea de casino basada en promedio y desviación del jugador.
    Retorna (line, odds_decimal).
    """
    if player_std == 0:
        player_std = player_avg * 0.15

    line = round(player_avg - 0.25 * player_std, 1)
    line = _round_to_half(line)

    if line <= 0:
        line = 0.5

    odds = round(1.85 + (player_avg - line) * 0.1, 2)
    odds = max(1.50, min(2.50, odds))

    return line, odds


def _round_to_half(val: float) -> float:
    """Redondea al .5 más cercano."""
    return math.floor(val) + 0.5


# ============================================================
# 2. GAME LOGS — Historial de partidos del jugador
# ============================================================

def get_player_game_log(player_name: str, team_name: str, sport: str, n_games: int = 15) -> list[dict]:
    """
    Extrae los últimos n_games del jugador desde la BD.
    Retorna lista de dicts con stats del juego.
    """
    session = SessionLocal()
    try:
        if sport == "nba":
            return _get_nba_game_log(session, player_name, team_name, n_games)
        elif sport == "mlb":
            return _get_mlb_game_log(session, player_name, team_name, n_games)
        elif sport == "soccer":
            return _get_soccer_game_log(session, player_name, team_name, n_games)
        return []
    except Exception as e:
        logger.warning(f"Error getting game log for {player_name}: {e}")
        return []
    finally:
        session.close()


def _get_nba_game_log(session, player_name: str, team_name: str, n: int) -> list[dict]:
    query = text("""
        SELECT j.puntos, j.rebotes, j.asistencias, j.robos, j.bloqueos,
               j.perdidas, j.triples, j.minutos,
               p.fecha, e_h.nombre as home_name, e_a.nombre as away_name
        FROM stats_jugador_nba j
        JOIN jugadores jug ON jug.id_jugador = j.id_jugador
        JOIN partidos p ON p.id_partido = j.id_partido
        JOIN equipos e_h ON e_h.id_equipo = p.id_local
        JOIN equipos e_a ON e_a.id_equipo = p.id_visitante
        WHERE jug.nombre ILIKE :pname
        ORDER BY p.fecha DESC
        LIMIT :n
    """)
    rows = session.execute(query, {"pname": f"%{player_name}%", "n": n}).fetchall()

    logs = []
    for r in rows:
        is_home = team_name.lower() in (r.home_name or "").lower()
        logs.append({
            "date": str(r.fecha) if r.fecha else "",
            "opponent": r.away_name if is_home else r.home_name,
            "home_away": "home" if is_home else "away",
            "points": r.puntos or 0,
            "rebounds": r.rebotes or 0,
            "assists": r.asistencias or 0,
            "steals": r.robos or 0,
            "blocks": r.bloqueos or 0,
            "turnovers": r.perdidas or 0,
            "threes": r.triples or 0,
            "minutes": r.minutos or 0,
        })
    return logs


def _get_mlb_game_log(session, player_name: str, team_name: str, n: int) -> list[dict]:
    query = text("""
        SELECT j.turnos_al_bate, j.hits, j.carreras, j.home_runs,
               j.carreras_impulsadas, j.bases_por_bolas, j.ponches,
               p.fecha, e_h.nombre as home_name, e_a.nombre as away_name
        FROM stats_jugador_mlb j
        JOIN jugadores jug ON jug.id_jugador = j.id_jugador
        JOIN partidos p ON p.id_partido = j.id_partido
        JOIN equipos e_h ON e_h.id_equipo = p.id_local
        JOIN equipos e_a ON e_a.id_equipo = p.id_visitante
        WHERE jug.nombre ILIKE :pname
        ORDER BY p.fecha DESC
        LIMIT :n
    """)
    rows = session.execute(query, {"pname": f"%{player_name}%", "n": n}).fetchall()

    logs = []
    for r in rows:
        is_home = team_name.lower() in (r.home_name or "").lower()
        logs.append({
            "date": str(r.fecha) if r.fecha else "",
            "opponent": r.away_name if is_home else r.home_name,
            "home_away": "home" if is_home else "away",
            "at_bats": r.turnos_al_bate or 0,
            "hits": r.hits or 0,
            "runs": r.carreras or 0,
            "home_runs": r.home_runs or 0,
            "rbis": r.carreras_impulsadas or 0,
            "walks": r.bases_por_bolas or 0,
            "strikeouts": r.ponches or 0,
        })
    return logs


def _get_soccer_game_log(session, player_name: str, team_name: str, n: int) -> list[dict]:
    query = text("""
        SELECT j.minutos, j.goles, j.asistencias, j.tiros_totales,
               j.tiros_puerta, j.pases_precisos, j.faltas_cometidas,
               j.amarillas, j.rojas,
               p.fecha, e_h.nombre as home_name, e_a.nombre as away_name
        FROM stats_jugador_futbol j
        JOIN jugadores jug ON jug.id_jugador = j.id_jugador
        JOIN partidos p ON p.id_partido = j.id_partido
        JOIN equipos e_h ON e_h.id_equipo = p.id_local
        JOIN equipos e_a ON e_a.id_equipo = p.id_visitante
        WHERE jug.nombre ILIKE :pname
        ORDER BY p.fecha DESC
        LIMIT :n
    """)
    rows = session.execute(query, {"pname": f"%{player_name}%", "n": n}).fetchall()

    logs = []
    for r in rows:
        is_home = team_name.lower() in (r.home_name or "").lower()
        logs.append({
            "date": str(r.fecha) if r.fecha else "",
            "opponent": r.away_name if is_home else r.home_name,
            "home_away": "home" if is_home else "away",
            "minutes": r.minutos or 0,
            "goals": r.goles or 0,
            "assists": r.asistencias or 0,
            "total_shots": r.tiros_totales or 0,
            "shots_on_target": r.tiros_puerta or 0,
            "accurate_passes": r.pases_precisos or 0,
            "fouls": r.faltas_cometidas or 0,
            "yellow_cards": r.amarillas or 0,
            "red_cards": r.rojas or 0,
        })
    return logs


# ============================================================
# 3. ROLLING AVERAGES — Promedios móviles
# ============================================================

def calculate_rolling_averages(game_log: list[dict], stat_key: str) -> dict:
    """
    Calcula promedios L5, L10 y season-to-date para una stat específica.
    Retorna dict con l5_avg, l10_avg, season_avg, l5_values, l10_values.
    """
    if not game_log:
        return {"l5_avg": 0, "l10_avg": 0, "season_avg": 0, "l5_values": [], "l10_values": []}

    values = [g.get(stat_key, 0) for g in game_log]

    l5 = values[:5]
    l10 = values[:10]
    season = values

    return {
        "l5_avg": round(np.mean(l5), 2) if l5 else 0,
        "l10_avg": round(np.mean(l10), 2) if l10 else 0,
        "season_avg": round(np.mean(season), 2) if season else 0,
        "l5_std": round(np.std(l5), 2) if len(l5) > 1 else 0,
        "l10_std": round(np.std(l10), 2) if len(l10) > 1 else 0,
        "season_std": round(np.std(season), 2) if len(season) > 1 else 0,
        "l5_values": l5,
        "l10_values": l10,
        "n_games": len(values),
    }


# ============================================================
# 4. TREND DETECTION — Regresión lineal sobre últimos juegos
# ============================================================

def detect_trends(game_log: list[dict], stat_key: str) -> dict:
    """
    Detecta tendencia usando regresión lineal simple sobre los últimos juegos.
    Retorna dict con direction (up/down/flat), strength (-1 a 1), slope.
    """
    if len(game_log) < 3:
        return {"direction": "flat", "strength": 0, "slope": 0}

    values = [g.get(stat_key, 0) for g in game_log[:10]]
    n = len(values)
    x = np.arange(n, dtype=float)
    y = np.array(values, dtype=float)

    x_mean = np.mean(x)
    y_mean = np.mean(y)

    denom = np.sum((x - x_mean) ** 2)
    if denom == 0:
        return {"direction": "flat", "strength": 0, "slope": 0}

    slope = np.sum((x - x_mean) * (y - y_mean)) / denom

    y_std = np.std(y)
    if y_std == 0:
        return {"direction": "flat", "strength": 0, "slope": round(slope, 4)}

    normalized_slope = slope / y_std

    if normalized_slope > 0.15:
        direction = "up"
    elif normalized_slope < -0.15:
        direction = "down"
    else:
        direction = "flat"

    strength = round(max(-1.0, min(1.0, normalized_slope)), 3)

    return {
        "direction": direction,
        "strength": strength,
        "slope": round(slope, 4),
    }


# ============================================================
# 5. HOME/AWAY SPLITS
# ============================================================

def get_home_away_splits(game_log: list[dict], stat_key: str) -> dict:
    """
    Compara rendimiento como local vs visitante.
    """
    home_vals = [g.get(stat_key, 0) for g in game_log if g.get("home_away") == "home"]
    away_vals = [g.get(stat_key, 0) for g in game_log if g.get("home_away") == "away"]

    return {
        "home_avg": round(np.mean(home_vals), 2) if home_vals else 0,
        "home_n": len(home_vals),
        "away_avg": round(np.mean(away_vals), 2) if away_vals else 0,
        "away_n": len(away_vals),
        "home_away_diff": round(np.mean(home_vals) - np.mean(away_vals), 2) if home_vals and away_vals else 0,
    }


# ============================================================
# 6. VS OPPONENT HISTORY
# ============================================================

def get_vs_opponent_history(player_name: str, opponent_name: str, sport: str, stat_key: str) -> dict:
    """
    Historial del jugador contra el oponente específico.
    """
    session = SessionLocal()
    try:
        if sport == "nba":
            query = text("""
                SELECT j.puntos, j.rebotes, j.asistencias, j.triples
                FROM stats_jugador_nba j
                JOIN jugadores jug ON jug.id_jugador = j.id_jugador
                JOIN partidos p ON p.id_partido = j.id_partido
                JOIN equipos e_h ON e_h.id_equipo = p.id_local
                JOIN equipos e_a ON e_a.id_equipo = p.id_visitante
                WHERE jug.nombre ILIKE :pname
                  AND (e_h.nombre ILIKE :opp OR e_a.nombre ILIKE :opp)
                ORDER BY p.fecha DESC
                LIMIT 10
            """)
        elif sport == "mlb":
            query = text("""
                SELECT j.hits, j.home_runs, j.carreras_impulsadas, j.ponches
                FROM stats_jugador_mlb j
                JOIN jugadores jug ON jug.id_jugador = j.id_jugador
                JOIN partidos p ON p.id_partido = j.id_partido
                JOIN equipos e_h ON e_h.id_equipo = p.id_local
                JOIN equipos e_a ON e_a.id_equipo = p.id_visitante
                WHERE jug.nombre ILIKE :pname
                  AND (e_h.nombre ILIKE :opp OR e_a.nombre ILIKE :opp)
                ORDER BY p.fecha DESC
                LIMIT 10
            """)
        elif sport == "soccer":
            query = text("""
                SELECT j.goles, j.asistencias, j.tiros_puerta, j.tiros_totales
                FROM stats_jugador_futbol j
                JOIN jugadores jug ON jug.id_jugador = j.id_jugador
                JOIN partidos p ON p.id_partido = j.id_partido
                JOIN equipos e_h ON e_h.id_equipo = p.id_local
                JOIN equipos e_a ON e_a.id_equipo = p.id_visitante
                WHERE jug.nombre ILIKE :pname
                  AND (e_h.nombre ILIKE :opp OR e_a.nombre ILIKE :opp)
                ORDER BY p.fecha DESC
                LIMIT 10
            """)
        else:
            return {"avg": 0, "n_games": 0, "values": []}

        rows = session.execute(query, {"pname": f"%{player_name}%", "opp": f"%{opponent_name}%"}).fetchall()

        stat_map = {
            "nba": {"points": "puntos", "rebounds": "rebotes", "assists": "asistencias", "threes": "triples"},
            "mlb": {"hits": "hits", "home_runs": "home_runs", "rbis": "carreras_impulsadas", "strikeouts": "ponches"},
            "soccer": {"goals": "goles", "assists": "asistencias", "shots_on_target": "tiros_puerta", "total_shots": "tiros_totales"},
        }

        col_name = stat_map.get(sport, {}).get(stat_key, stat_key)
        values = []
        for r in rows:
            for idx, col in enumerate(r._mapping.keys()):
                if col == col_name or (col_name in col.lower()):
                    val = r._mapping[col]
                    if val is not None:
                        values.append(float(val))
                    break

        if not values:
            return {"avg": 0, "n_games": 0, "values": []}

        return {
            "avg": round(np.mean(values), 2),
            "n_games": len(values),
            "values": values,
        }
    except Exception as e:
        logger.warning(f"Error vs opponent history: {e}")
        return {"avg": 0, "n_games": 0, "values": []}
    finally:
        session.close()


# ============================================================
# 7. STREAK DETECTION — Rachas activas
# ============================================================

def detect_streaks(game_log: list[dict], stat_key: str, threshold: float) -> Optional[str]:
    """
    Detecta racha activa: juegos consecutivos por encima del threshold.
    Retorna string descriptivo o None si no hay racha significativa (>= 3).
    """
    if not game_log:
        return None

    values = [g.get(stat_key, 0) for g in game_log]
    streak = 0
    for v in values:
        if v >= threshold:
            streak += 1
        else:
            break

    if streak >= 3:
        stat_labels = {
            "points": "pts", "rebounds": "reb", "assists": "ast",
            "threes": "triples", "goals": "goles", "hits": "hits",
            "home_runs": "HR", "rbis": "RBI", "shots_on_target": "SOT",
            "strikeouts": "K",
        }
        label = stat_labels.get(stat_key, stat_key)
        return f"{streak} juegos consecutivos con {threshold}+ {label}"

    return None


# ============================================================
# 8. HOT/COLD CLASSIFICATION
# ============================================================

def classify_hot_cold(trends: dict, rolling: dict) -> str:
    """
    Clasifica si el jugador está hot, cold o neutral.
    """
    direction = trends.get("direction", "flat")
    strength = abs(trends.get("strength", 0))
    l5 = rolling.get("l5_avg", 0)
    season = rolling.get("season_avg", 0)

    if season == 0:
        return "neutral"

    ratio = l5 / season if season > 0 else 1

    if direction == "up" and strength > 0.2 and ratio > 1.1:
        return "hot"
    elif direction == "down" and strength > 0.2 and ratio < 0.85:
        return "cold"
    return "neutral"


# ============================================================
# 9. EV CALCULATION — Expected Value real
# ============================================================

def calculate_ev(projected: float, casino_line: float, odds_decimal: float) -> dict:
    """
    Calcula Expected Value para una apuesta.
    EV = (prob * payout) - (1 - prob) * stake

    Usa distribución normal para estimar probabilidad de over/under.
    """
    if casino_line <= 0 or odds_decimal <= 1:
        return {"over_prob": 0.5, "under_prob": 0.5, "ev_over_pct": 0, "ev_under_pct": 0, "recommendation": "NO BET", "confidence": "lean"}

    diff = projected - casino_line
    std = max(abs(projected) * 0.15, 0.5)

    z = diff / std
    over_prob = _normal_cdf(z)
    under_prob = 1 - over_prob

    payout_over = odds_decimal - 1
    ev_over = (over_prob * payout_over) - (under_prob * 1)
    ev_over_pct = round(ev_over * 100, 2)

    payout_under = odds_decimal - 1
    ev_under = (under_prob * payout_under) - (over_prob * 1)
    ev_under_pct = round(ev_under * 100, 2)

    if ev_over_pct > ev_under_pct and ev_over_pct > 0:
        recommendation = "OVER"
        ev_pct = ev_over_pct
        prob = over_prob
    elif ev_under_pct > 0:
        recommendation = "UNDER"
        ev_pct = ev_under_pct
        prob = under_prob
    else:
        recommendation = "NO BET"
        ev_pct = max(ev_over_pct, ev_under_pct)
        prob = max(over_prob, under_prob)

    if ev_pct > 10:
        confidence = "high"
    elif ev_pct > 3:
        confidence = "medium"
    else:
        confidence = "lean"

    return {
        "over_prob": round(over_prob, 3),
        "under_prob": round(under_prob, 3),
        "ev_over_pct": ev_over_pct,
        "ev_under_pct": ev_under_pct,
        "recommendation": recommendation,
        "confidence": confidence,
        "ev_pct": round(ev_pct, 2),
    }


def _normal_cdf(z: float) -> float:
    """Aproximación de la CDF normal estándar (función error)."""
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


# ============================================================
# 10. STAT KEY MAPPING por deporte
# ============================================================

STAT_KEY_MAP = {
    "nba": {
        "Puntos": "points",
        "Rebotes": "rebounds",
        "Asistencias": "assists",
        "Triples": "threes",
        "Pts+Reb+Ast": "points",
    },
    "mlb": {
        "Hits": "hits",
        "Home Runs": "home_runs",
        "Carreras Impulsadas": "rbis",
        "Ponches": "strikeouts",
    },
    "soccer": {
        "Goles": "goals",
        "Asistencias": "assists",
        "Tiros a Puerta": "shots_on_target",
        "Tiros Totales": "total_shots",
        "Goles+Asistencias": "goals",
    },
}


def _get_stat_value(game: dict, sport: str, market: str) -> float:
    """Extrae el valor de la stat relevante del game log."""
    key_map = STAT_KEY_MAP.get(sport, {})
    stat_key = key_map.get(market, market.lower().replace(" ", "_"))

    if market == "Pts+Reb+Ast":
        return game.get("points", 0) + game.get("rebounds", 0) + game.get("assists", 0)
    if market == "Goles+Asistencias":
        return game.get("goals", 0) + game.get("assists", 0)

    return game.get(stat_key, 0)


# ============================================================
# 11. ORCHESTRATOR — Generar props para un deporte
# ============================================================

def generate_props_for_sport(sport: str, min_ev: float = 0, resolve_photos: bool = True) -> list[dict]:
    """
    Genera player props completos para un deporte.
    Retorna lista de dicts con toda la info del jugador + props + tendencias.
    """
    session = SessionLocal()
    try:
        players = _get_players_for_sport(session, sport)
    except Exception as e:
        logger.warning(f"Error getting players for {sport}: {e}")
        players = []
    finally:
        session.close()

    if not players:
        players = _get_synthetic_players(sport)

    if resolve_photos:
        players = _resolve_player_photos(players, sport)

    odds_data = fetch_odds(sport)
    results = []

    for player in players:
        player_name = player["name"]
        team_name = player["team"]
        sport_actual = player.get("sport", sport)

        game_log = get_player_game_log(player_name, team_name, sport_actual, n_games=15)

        if not game_log:
            continue

        markets = _get_markets_for_sport(sport_actual)
        props = []

        for market in markets:
            transformed_log = []
            for g in game_log:
                transformed_log.append({
                    **g,
                    "_computed": _get_stat_value(g, sport_actual, market),
                })

            for g in transformed_log:
                g[market.replace(" ", "_").lower()] = g["_computed"]

            stat_key = market.replace(" ", "_").lower()
            rolling = calculate_rolling_averages(transformed_log, stat_key)
            trends = detect_trends(transformed_log, stat_key)
            splits = get_home_away_splits(transformed_log, stat_key)

            projected = rolling["l5_avg"]
            if trends["direction"] == "up":
                projected = projected * (1 + abs(trends["strength"]) * 0.1)
            elif trends["direction"] == "down":
                projected = projected * (1 - abs(trends["strength"]) * 0.1)

            std = rolling.get("l5_std", 0) or rolling.get("season_std", 1)
            if std == 0:
                std = abs(projected) * 0.15 or 0.5

            casino_line, casino_odds = estimate_player_line(projected, std, market)

            for od in odds_data:
                if (od.get("home_team", "").lower() in team_name.lower() or
                    od.get("away_team", "").lower() in team_name.lower()):
                    casino_odds = od.get("odds_decimal", casino_odds)
                    break

            ev_result = calculate_ev(projected, casino_line, casino_odds)

            if ev_result["ev_pct"] >= min_ev:
                props.append({
                    "market": market,
                    "line": casino_line,
                    "casino_odds": casino_odds,
                    "projected": round(projected, 2),
                    "over_prob": ev_result["over_prob"],
                    "under_prob": ev_result["under_prob"],
                    "ev_pct": ev_result["ev_pct"],
                    "recommendation": ev_result["recommendation"],
                    "confidence": ev_result["confidence"],
                })

        if not props:
            continue

        all_stat_keys = [m.replace(" ", "_").lower() for m in _get_markets_for_sport(sport_actual)]
        primary_stat_key = all_stat_keys[0] if all_stat_keys else "points"

        # Map market stat key to actual game log key
        log_key_map = {
            "nba": {"puntos": "points", "rebotes": "rebounds", "asistencias": "assists", "triples": "threes"},
            "mlb": {"hits": "hits", "home_runs": "home_runs", "carreras_impulsadas": "rbis", "ponches": "strikeouts"},
            "soccer": {"goles": "goals", "asistencias": "assists", "tiros_a_puerta": "shots_on_target", "tiros_totales": "total_shots"},
        }
        log_key = log_key_map.get(sport_actual, {}).get(primary_stat_key, primary_stat_key)

        rolling_primary = calculate_rolling_averages(game_log, log_key)
        trends_primary = detect_trends(game_log, log_key)
        splits_primary = get_home_away_splits(game_log, log_key)
        hot_cold = classify_hot_cold(trends_primary, rolling_primary)

        streak_threshold = max(rolling_primary["season_avg"] * 0.8, 1.0)
        streak = detect_streaks(game_log, log_key, streak_threshold)

        opponent = game_log[0].get("opponent", "TBD") if game_log else "TBD"
        game_time = ""
        if game_log and game_log[0].get("date"):
            try:
                dt = datetime.strptime(game_log[0]["date"][:10], "%Y-%m-%d")
                game_time = dt.strftime("%H:%M")
            except Exception:
                pass

        vs_opp = get_vs_opponent_history(player_name, opponent, sport_actual, primary_stat_key)

        best_prop = max(props, key=lambda p: p["ev_pct"])

        results.append({
            "id": f"{sport_actual}_{player_name}_{team_name}",
            "sport": sport_actual,
            "player_name": player_name,
            "team_name": team_name,
            "opponent": opponent,
            "game_time": game_time,
            "photo_url": player.get("photo_url", ""),
            "logo_url": player.get("logo_url", ""),
            "props": sorted(props, key=lambda p: p["ev_pct"], reverse=True),
            "trends": {
                "l5_avg": rolling_primary["l5_avg"],
                "l10_avg": rolling_primary["l10_avg"],
                "season_avg": rolling_primary["season_avg"],
                "trend_direction": trends_primary["direction"],
                "trend_strength": trends_primary["strength"],
                "home_avg": splits_primary["home_avg"],
                "away_avg": splits_primary["away_avg"],
                "vs_opponent_avg": vs_opp.get("avg", None),
                "vs_opponent_games": vs_opp.get("n_games", 0),
                "active_streak": streak,
                "hot_cold": hot_cold,
                "last_10_values": rolling_primary.get("l10_values", []),
            },
            "primary_ev": best_prop["ev_pct"],
            "primary_confidence": best_prop["confidence"],
        })

    results.sort(key=lambda r: r["primary_ev"], reverse=True)
    return results


def _get_players_for_sport(session, sport: str) -> list[dict]:
    """Obtiene lista de jugadores activos para un deporte."""
    players = []

    if sport == "soccer":
        query = text("""
            SELECT jug.nombre, e.nombre as team_name,
                   MAX(irpd.photo_url) as photo_url, '' as logo_url, 'soccer' as sport
            FROM stats_jugador_futbol j
            JOIN jugadores jug ON jug.id_jugador = j.id_jugador
            JOIN equipos e ON e.id_equipo = jug.id_equipo
            LEFT JOIN ml_inference_ready_player_data irpd
              ON irpd.player_name = jug.nombre
            GROUP BY jug.nombre, e.nombre
            ORDER BY SUM(j.goles) DESC
            LIMIT 50
        """)
        rows = session.execute(query).fetchall()
        for r in rows:
            players.append({
                "name": r.nombre,
                "team": r.team_name,
                "photo_url": r.photo_url or "",
                "logo_url": r.logo_url or "",
                "sport": "soccer",
            })

    elif sport == "nba":
        query = text("""
            SELECT jug.nombre, e.nombre as team_name,
                   '' as photo_url, '' as logo_url, 'nba' as sport
            FROM stats_jugador_nba j
            JOIN jugadores jug ON jug.id_jugador = j.id_jugador
            JOIN equipos e ON e.id_equipo = jug.id_equipo
            GROUP BY jug.nombre, e.nombre
            ORDER BY SUM(j.puntos) DESC
            LIMIT 50
        """)
        rows = session.execute(query).fetchall()
        for r in rows:
            players.append({
                "name": r.nombre,
                "team": r.team_name,
                "photo_url": "",
                "logo_url": "",
                "sport": "nba",
            })

    elif sport == "mlb":
        query = text("""
            SELECT jug.nombre, e.nombre as team_name,
                   '' as photo_url, '' as logo_url, 'mlb' as sport
            FROM stats_jugador_mlb j
            JOIN jugadores jug ON jug.id_jugador = j.id_jugador
            JOIN equipos e ON e.id_equipo = jug.id_equipo
            GROUP BY jug.nombre, e.nombre
            ORDER BY SUM(j.home_runs) DESC
            LIMIT 50
        """)
        rows = session.execute(query).fetchall()
        for r in rows:
            players.append({
                "name": r.nombre,
                "team": r.team_name,
                "photo_url": "",
                "logo_url": "",
                "sport": "mlb",
            })

    return players


def _get_synthetic_players(sport: str) -> list[dict]:
    """Genera jugadores sintéticos para demo cuando no hay datos reales."""
    synthetic = {
        "nba": [
            {"name": "LeBron James", "team": "Lakers", "sport": "nba"},
            {"name": "Stephen Curry", "team": "Warriors", "sport": "nba"},
            {"name": "Giannis Antetokounmpo", "team": "Bucks", "sport": "nba"},
            {"name": "Luka Doncic", "team": "Mavericks", "sport": "nba"},
            {"name": "Nikola Jokic", "team": "Nuggets", "sport": "nba"},
            {"name": "Jayson Tatum", "team": "Celtics", "sport": "nba"},
            {"name": "Kevin Durant", "team": "Suns", "sport": "nba"},
            {"name": "Joel Embiid", "team": "76ers", "sport": "nba"},
        ],
        "mlb": [
            {"name": "Aaron Judge", "team": "Yankees", "sport": "mlb"},
            {"name": "Shohei Ohtani", "team": "Dodgers", "sport": "mlb"},
            {"name": "Ronald Acuña Jr", "team": "Braves", "sport": "mlb"},
            {"name": "Mookie Betts", "team": "Dodgers", "sport": "mlb"},
            {"name": "Juan Soto", "team": "Yankees", "sport": "mlb"},
            {"name": "Bobby Witt Jr", "team": "Royals", "sport": "mlb"},
        ],
        "soccer": [
            {"name": "Erling Haaland", "team": "Manchester City", "sport": "soccer"},
            {"name": "Kylian Mbappé", "team": "Real Madrid", "sport": "soccer"},
            {"name": "Mohamed Salah", "team": "Liverpool", "sport": "soccer"},
            {"name": "Harry Kane", "team": "Bayern Munich", "sport": "soccer"},
            {"name": "Vinicius Jr", "team": "Real Madrid", "sport": "soccer"},
            {"name": "Bukayo Saka", "team": "Arsenal", "sport": "soccer"},
            {"name": "Lautaro Martínez", "team": "Inter Milan", "sport": "soccer"},
            {"name": "Robert Lewandowski", "team": "Barcelona", "sport": "soccer"},
        ],
    }

    players = synthetic.get(sport, [])
    for p in players:
        p["photo_url"] = ""
        p["logo_url"] = ""
    return players


def _resolve_player_photos(players: list[dict], sport: str) -> list[dict]:
    """Resuelve fotos de jugadores via ESPN CDN para los que no tienen photo_url."""
    try:
        from predicciones.player_photo_resolver import resolve_player_photo

        for player in players:
            if player.get("photo_url"):
                continue
            photo_url = resolve_player_photo(player["name"], player["team"], player.get("sport", sport))
            if photo_url:
                player["photo_url"] = photo_url
    except Exception as e:
        logger.warning(f"Photo resolver failed: {e}")
    return players


def _get_markets_for_sport(sport: str) -> list[str]:
    """Retorna lista de mercados de props para un deporte."""
    markets = {
        "nba": ["Puntos", "Rebotes", "Asistencias", "Triples", "Pts+Reb+Ast"],
        "mlb": ["Hits", "Home Runs", "Carreras Impulsadas", "Ponches"],
        "soccer": ["Goles", "Asistencias", "Tiros a Puerta", "Tiros Totales", "Goles+Asistencias"],
    }
    return markets.get(sport, [])
