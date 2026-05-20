"""
ingesta_futbol.py — Ingesta completa de Futbol (2+ temporadas)

Fuentes:
  - football-data.co.uk: Historico de partidos y stats de equipo
  - FBref (via soccerdata): Stats avanzados de jugadores (xG, tiros, etc.)
  - 365Scores: Datos en tiempo real y player props
  - ESPN API: Logos de equipos

Uso:
    python scripts/ingesta_futbol.py --todo
    python scripts/ingesta_futbol.py --ligas PL SP1 --temporadas 2324 2425 2526
    python scripts/ingesta_futbol.py --solo-csv
    python scripts/ingesta_futbol.py --solo-fbref
    python scripts/ingesta_futbol.py --solo-365scores
"""

import os
import sys
import logging
import argparse
import time
import random
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.models import (
    Team, Player, Match, AliasEquipo,
    MatchStatsFutbol, PlayerStatsFutbol,
    MatchHistoryStats, MLMatchFeatures,
    LeagueTable, RawPlayerData,
)
from database import SessionLocal, engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("IngestaFutbol")

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURACION
# ──────────────────────────────────────────────────────────────────────────────

FOOTBALL_DATA_UK = {
    "PL":  {"url": "https://www.football-data.co.uk/mmz4281/{season}/E0.csv", "nombre": "Premier League"},
    "SP1": {"url": "https://www.football-data.co.uk/mmz4281/{season}/SP1.csv", "nombre": "La Liga"},
    "D1":  {"url": "https://www.football-data.co.uk/mmz4281/{season}/D1.csv", "nombre": "Bundesliga"},
    "I1":  {"url": "https://www.football-data.co.uk/mmz4281/{season}/I1.csv", "nombre": "Serie A"},
    "F1":  {"url": "https://www.football-data.co.uk/mmz4281/{season}/F1.csv", "nombre": "Ligue 1"},
    "MEX": {"url": "https://www.football-data.co.uk/new/MEX.csv", "nombre": "Liga MX", "all_seasons": True},
}

TEMPORADAS = ["2324", "2425", "2526"]

ESPN_FUTBOL = [
    {"league_name": "Premier League", "prefix": 100000,
     "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/teams?limit=100"},
    {"league_name": "La Liga", "prefix": 100000,
     "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/teams?limit=100"},
    {"league_name": "Liga MX", "prefix": 100000,
     "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/mex.1/teams?limit=100"},
]


def resolve_team(session, nombre: str, liga: str = None) -> int | None:
    nombre_lower = nombre.lower().strip()

    result = session.execute(
        text("SELECT a.id_equipo FROM alias_equipos a WHERE a.nombre_fuente = :n LIMIT 1"),
        {"n": nombre_lower}
    ).fetchone()
    if result:
        return result[0]

    result = session.execute(
        text("SELECT id_equipo FROM equipos WHERE LOWER(nombre) = :n LIMIT 1"),
        {"n": nombre_lower}
    ).fetchone()
    if result:
        return result[0]

    if liga:
        result = session.execute(
            text("SELECT id_equipo FROM equipos WHERE LOWER(nombre) LIKE :p AND liga = :l LIMIT 1"),
            {"p": f"%{nombre_lower}%", "l": liga}
        ).fetchone()
        if result:
            return result[0]

    return None


def add_alias(session, nombre: str, id_equipo: int):
    existing = session.execute(
        text("SELECT id FROM alias_equipos WHERE nombre_fuente = :n"),
        {"n": nombre.lower().strip()}
    ).fetchone()
    if not existing:
        session.execute(
            text("INSERT INTO alias_equipos (nombre_fuente, id_equipo) VALUES (:n, :id)"),
            {"n": nombre.lower().strip(), "id": id_equipo}
        )


# ──────────────────────────────────────────────────────────────────────────────
# PASO 1: EQUIPOS DESDE ESPN
# ──────────────────────────────────────────────────────────────────────────────

def cargar_equipos_espn():
    logger.info("[FUTBOL] Cargando equipos desde ESPN API...")

    with Session(engine) as session:
        total = 0
        for config in ESPN_FUTBOL:
            try:
                resp = requests.get(config["url"], timeout=15)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                teams = data.get('sports', [{}])[0].get('leagues', [{}])[0].get('teams', [])

                for item in teams:
                    t = item.get('team', {})
                    espn_id = int(t.get('id', 0))
                    canonical_id = config["prefix"] + espn_id
                    nombre = t.get('displayName', t.get('name', ''))
                    corto = t.get('shortDisplayName', '')
                    logos = t.get('logos', [])
                    logo = logos[0].get('href', '') if logos else ''

                    existing = session.query(Team).filter(Team.id_equipo == canonical_id).first()
                    if existing:
                        if not existing.logo_url and logo:
                            existing.logo_url = logo
                        continue

                    session.add(Team(
                        id_equipo=canonical_id,
                        nombre=nombre,
                        liga=config["league_name"],
                        logo_url=logo,
                    ))
                    session.flush()
                    add_alias(session, nombre, canonical_id)
                    if corto and corto != nombre:
                        add_alias(session, corto, canonical_id)
                    total += 1

                session.commit()
                logger.info(f"  {config['league_name']}: {len(teams)} equipos")

            except Exception as e:
                logger.error(f"  Error {config['league_name']}: {e}")
                session.rollback()

        logger.info(f"[FUTBOL] {total} equipos nuevos.")


# ──────────────────────────────────────────────────────────────────────────────
# PASO 2: PARTIDOS DESDE football-data.co.uk
# ──────────────────────────────────────────────────────────────────────────────

def cargar_partidos_csv(ligas=None, temporadas=None):
    ligas = ligas or list(FOOTBALL_DATA_UK.keys())
    temporadas = temporadas or TEMPORADAS

    logger.info(f"[FUTBOL] Cargando partidos CSV: ligas={ligas}, temporadas={temporadas}")

    total_insertados = 0
    total_partidos_core = 0

    for liga_key in ligas:
        info = FOOTBALL_DATA_UK[liga_key]
        is_all_seasons = info.get("all_seasons", False)

        if is_all_seasons:
            # Archivo all-seasons-in-one: descargar una vez y filtrar por Season
            url = info["url"]
            logger.info(f"  Descargando {info['nombre']} (all-seasons)...")

            try:
                df = pd.read_csv(url)
            except Exception as e:
                logger.warning(f"  No se pudo descargar: {e}")
                continue

            if df.empty:
                continue

            df = df.rename(columns={
                'Date': 'date', 'Home': 'home', 'Away': 'away',
                'HG': 'hg', 'AG': 'ag',
                'HS': 'hs', 'AS': 'as',
                'HST': 'hst', 'AST': 'ast',
                'HC': 'hc', 'AC': 'ac',
                'HY': 'hy', 'AY': 'ay',
                'HR': 'hr', 'AR': 'ar',
            })
            df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
            df = df.dropna(subset=['date', 'home', 'away'])

            # Filtrar por temporadas solicitadas
            if 'Season' in df.columns:
                # Mapear '2023/2024' -> '23-24' (formato consistente con ligas europeas)
                season_map = {f"20{t[:2]}/20{t[2:]}": f"{t[:2]}-{t[2:]}" for t in temporadas}
                df['season_label'] = df['Season'].map(season_map)
                df = df.dropna(subset=['season_label'])
                logger.info(f"  {info['nombre']}: {len(df)} partidos tras filtrar temporadas {temporadas}")
            else:
                logger.warning(f"  {info['nombre']}: columna Season no encontrada, usando todas las filas")
                df['season_label'] = 'unknown'

            with Session(engine) as session:
                for _, row in df.iterrows():
                    match_date = row['date']
                    home_name = row['home']
                    away_name = row['away']
                    season_label = row['season_label']

                    existing_mh = session.query(MatchHistoryStats).filter_by(
                        home_team=home_name, away_team=away_name,
                        date=match_date, league=info["nombre"], season=season_label,
                    ).first()

                    if existing_mh:
                        continue

                    hg = int(row['hg']) if pd.notna(row.get('hg')) else None
                    ag = int(row['ag']) if pd.notna(row.get('ag')) else None

                    session.add(MatchHistoryStats(
                        league=info["nombre"],
                        season=season_label,
                        date=match_date,
                        home_team=home_name,
                        away_team=away_name,
                        home_score=hg,
                        away_score=ag,
                    ))
                    total_insertados += 1

                    if hg is not None and ag is not None:
                        home_id = resolve_team(session, home_name, info["nombre"])
                        away_id = resolve_team(session, away_name, info["nombre"])

                        if home_id and away_id:
                            match_id = int(match_date.timestamp()) + hash(home_name + away_name) % 100000

                            existing_match = session.query(Match).filter(Match.id_partido == match_id).first()
                            if not existing_match:
                                session.add(Match(
                                    id_partido=match_id,
                                    id_local=home_id,
                                    id_visitante=away_id,
                                    fecha=match_date,
                                    fstatus='Ended',
                                ))

                                session.add(MatchStatsFutbol(
                                    id_partido=match_id,
                                    goles_local=hg,
                                    goles_visitante=ag,
                                    tiros_puerta_local=int(row.get('hst', 0) or 0),
                                    tiros_puerta_visitante=int(row.get('ast', 0) or 0),
                                    corners_local=int(row.get('hc', 0) or 0),
                                    corners_visitante=int(row.get('ac', 0) or 0),
                                    amarillas_local=int(row.get('hy', 0) or 0),
                                    amarillas_visitante=int(row.get('ay', 0) or 0),
                                    rojas_local=int(row.get('hr', 0) or 0),
                                    rojas_visitante=int(row.get('ar', 0) or 0),
                                ))
                                total_partidos_core += 1

                session.commit()

            logger.info(f"  {info['nombre']}: {len(df)} partidos historicos insertados")

        else:
            # Ligas europeas: archivo por temporada
            for temp in temporadas:
                url = info["url"].format(season=temp)
                logger.info(f"  Descargando {info['nombre']} {temp}...")

                try:
                    df = pd.read_csv(url)
                except Exception as e:
                    logger.warning(f"  No se pudo descargar: {e}")
                    continue

                if df.empty:
                    continue

                df = df.rename(columns={
                    'Date': 'date', 'HomeTeam': 'home', 'AwayTeam': 'away',
                    'FTHG': 'hg', 'FTAG': 'ag',
                    'HS': 'hs', 'AS': 'as',
                    'HST': 'hst', 'AST': 'ast',
                    'HC': 'hc', 'AC': 'ac',
                    'HY': 'hy', 'AY': 'ay',
                    'HR': 'hr', 'AR': 'ar',
                })
                df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
                df = df.dropna(subset=['date', 'home', 'away'])

                season_label = f"{temp[:2]}-{temp[2:]}"

                with Session(engine) as session:
                    for _, row in df.iterrows():
                        match_date = row['date']
                        home_name = row['home']
                        away_name = row['away']

                        existing_mh = session.query(MatchHistoryStats).filter_by(
                            home_team=home_name, away_team=away_name,
                            date=match_date, league=info["nombre"], season=season_label,
                        ).first()

                        if existing_mh:
                            continue

                        hg = int(row['hg']) if pd.notna(row.get('hg')) else None
                        ag = int(row['ag']) if pd.notna(row.get('ag')) else None

                        session.add(MatchHistoryStats(
                            league=info["nombre"],
                            season=season_label,
                            date=match_date,
                            home_team=home_name,
                            away_team=away_name,
                            home_score=hg,
                            away_score=ag,
                        ))
                        total_insertados += 1

                        if hg is not None and ag is not None:
                            home_id = resolve_team(session, home_name, info["nombre"])
                            away_id = resolve_team(session, away_name, info["nombre"])

                            if home_id and away_id:
                                match_id = int(match_date.timestamp()) + hash(home_name + away_name) % 100000

                                existing_match = session.query(Match).filter(Match.id_partido == match_id).first()
                                if not existing_match:
                                    session.add(Match(
                                        id_partido=match_id,
                                        id_local=home_id,
                                        id_visitante=away_id,
                                        fecha=match_date,
                                        fstatus='Ended',
                                    ))

                                    session.add(MatchStatsFutbol(
                                        id_partido=match_id,
                                        goles_local=hg,
                                        goles_visitante=ag,
                                        tiros_puerta_local=int(row.get('hst', 0) or 0),
                                        tiros_puerta_visitante=int(row.get('ast', 0) or 0),
                                        corners_local=int(row.get('hc', 0) or 0),
                                        corners_visitante=int(row.get('ac', 0) or 0),
                                        amarillas_local=int(row.get('hy', 0) or 0),
                                        amarillas_visitante=int(row.get('ay', 0) or 0),
                                        rojas_local=int(row.get('hr', 0) or 0),
                                        rojas_visitante=int(row.get('ar', 0) or 0),
                                    ))
                                    total_partidos_core += 1

                    session.commit()

                logger.info(f"  {info['nombre']} {temp}: {len(df)} partidos historicos")

    logger.info(f"[FUTBOL] {total_insertados} match_history_stats, {total_partidos_core} partidos core.")


# ──────────────────────────────────────────────────────────────────────────────
# PASO 2.5: CALCULAR PROMEDIOS DE EQUIPOS DESDE MATCH_HISTORY_STATS
# ──────────────────────────────────────────────────────────────────────────────

def calcular_promedios_equipos(ligas=None):
    """Calcula prom_goles, prom_tiros_puerta, prom_corners para todos los equipos.

    Usa MatchHistoryStats para goles (todas las ligas) y stats_futbol para
    corners/tiros (solo ligas europeas con datos disponibles).
    """
    logger.info("[FUTBOL] Calculando promedios de equipos...")

    with Session(engine) as session:
        # 1. Calcular prom_goles desde MatchHistoryStats (todas las ligas)
        matches = session.query(MatchHistoryStats).filter(
            MatchHistoryStats.home_score.isnot(None),
            MatchHistoryStats.away_score.isnot(None),
        ).all()

        if not matches:
            logger.info("  No hay partidos para calcular promedios.")
            return

        team_goals = {}
        for m in matches:
            home = m.home_team
            away = m.away_team
            hg = m.home_score
            ag = m.away_score

            if home not in team_goals:
                team_goals[home] = {'goles': 0, 'partidos': 0}
            if away not in team_goals:
                team_goals[away] = {'goles': 0, 'partidos': 0}

            team_goals[home]['goles'] += hg
            team_goals[home]['partidos'] += 1
            team_goals[away]['goles'] += ag
            team_goals[away]['partidos'] += 1

        # 2. Calcular corners/tiros desde stats_futbol (solo donde hay datos)
        query_sot = text("""
            SELECT e.nombre,
                   AVG(s.tiros_puerta_local) as avg_sot,
                   AVG(s.corners_local) as avg_corners
            FROM partidos p
            JOIN stats_futbol s ON s.id_partido = p.id_partido
            JOIN equipos e ON e.id_equipo = p.id_local
            WHERE p.fstatus = 'Ended'
              AND (s.tiros_puerta_local > 0 OR s.corners_local > 0)
            GROUP BY e.nombre
        """)
        sot_rows = session.execute(query_sot).fetchall()

        team_sot = {}
        for row in sot_rows:
            team_sot[row[0]] = {
                'prom_tiros_puerta': round(float(row[1]), 2) if row[1] else 0,
                'prom_corners': round(float(row[2]), 2) if row[2] else 0,
            }

        # 3. Actualizar tabla equipos
        actualizados = 0
        for team_name, stats in team_goals.items():
            if stats['partidos'] == 0:
                continue

            prom_goles = round(stats['goles'] / stats['partidos'], 2)
            sot_data = team_sot.get(team_name, {})
            prom_sot = sot_data.get('prom_tiros_puerta', 0)
            prom_corners = sot_data.get('prom_corners', 0)

            # Actualizar por nombre exacto (case-insensitive)
            result = session.execute(
                text("""
                    UPDATE equipos SET 
                        prom_goles = :pg,
                        prom_tiros_puerta = :pt,
                        prom_corners = :pc
                    WHERE LOWER(nombre) = :nombre
                """),
                {
                    "pg": prom_goles,
                    "pt": prom_sot,
                    "pc": prom_corners,
                    "nombre": team_name.lower()
                }
            )

            if result.rowcount == 0:
                # Intentar con alias
                alias_result = session.execute(
                    text("SELECT id_equipo FROM alias_equipos WHERE LOWER(nombre_fuente) = :nombre"),
                    {"nombre": team_name.lower()}
                ).fetchone()

                if alias_result:
                    session.execute(
                        text("""
                            UPDATE equipos SET 
                                prom_goles = :pg,
                                prom_tiros_puerta = :pt,
                                prom_corners = :pc
                            WHERE id_equipo = :id
                        """),
                        {
                            "pg": prom_goles,
                            "pt": prom_sot,
                            "pc": prom_corners,
                            "id": alias_result[0]
                        }
                    )
                    actualizados += 1
            else:
                actualizados += 1

        session.commit()
        logger.info(f"[FUTBOL] {actualizados} equipos actualizados ({len(team_sot)} con SOT/corners).")


# ──────────────────────────────────────────────────────────────────────────────
# PASO 3: FBREF PLAYER STATS (via soccerdata)
# ──────────────────────────────────────────────────────────────────────────────

def cargar_fbref_player_stats(ligas=None, temporadas=None):
    """Carga stats de jugadores desde FBref usando soccerdata."""
    ligas = ligas or ['ENG-Premier League', 'ESP-La Liga', 'MEX-Liga MX']
    temporadas = temporadas or ['2324', '2425', '2526']

    logger.info(f"[FUTBOL] Cargando FBref player stats...")

    try:
        import soccerdata as sd
    except ImportError:
        logger.error("soccerdata no instalado. pip install soccerdata")
        return

    total_raw = 0

    for liga in ligas:
        for temp in temporadas:
            logger.info(f"  FBref: {liga} {temp}...")

            try:
                fbref = sd.FBref(leagues=liga, seasons=temp)
                df = fbref.read_player_season_stats(stat_type='standard')
            except Exception as e:
                logger.warning(f"  Error FBref {liga} {temp}: {e}")
                time.sleep(30)
                continue

            if df is None or df.empty:
                continue

            df = df.reset_index()
            if isinstance(df.columns, pd.MultiIndex):
                new_cols = []
                for col in df.columns.values:
                    clean = [str(c) for c in col if c and not str(c).startswith('Unnamed')]
                    new_cols.append('_'.join(clean).strip('_'))
                df.columns = new_cols

            for col in df.columns:
                if str(col).lower() == 'player':
                    df = df.rename(columns={col: 'nombre_jugador'})
                elif str(col).lower() == 'team':
                    df = df.rename(columns={col: 'team_name'})

            df = df.fillna(0)

            with Session(engine) as session:
                for _, row in df.iterrows():
                    player_name = str(row.get('nombre_jugador', row.get('Player', '')))
                    team_name = str(row.get('team_name', row.get('Team', '')))

                    if not player_name or player_name == '0':
                        continue

                    min_col = next((c for c in df.columns if '90s' in str(c).lower() or 'min' in str(c).lower()), None)
                    shots_col = next((c for c in df.columns if 'shots' in str(c).lower() and 'total' in str(c).lower()), None)
                    sot_col = next((c for c in df.columns if 'sot' in str(c).lower()), None)
                    gls_col = next((c for c in df.columns if 'gls' in str(c).lower()), None)

                    playing_time = float(row.get(min_col, 0)) if min_col and pd.notna(row.get(min_col)) else 0
                    total_shots = float(row.get(shots_col, 0)) if shots_col and pd.notna(row.get(shots_col)) else 0
                    standard_sot = float(row.get(sot_col, 0)) if sot_col and pd.notna(row.get(sot_col)) else 0
                    performance_gls = float(row.get(gls_col, 0)) if gls_col and pd.notna(row.get(gls_col)) else 0

                    existing = session.execute(
                        text("""
                            SELECT id FROM ml_raw_player_data
                            WHERE player_name = :pn AND team_name = :tn AND deporte = 'futbol'
                            LIMIT 1
                        """),
                        {"pn": player_name, "tn": team_name}
                    ).fetchone()

                    if existing:
                        continue

                    session.execute(
                        text("""
                            INSERT INTO ml_raw_player_data
                            (player_name, team_name, deporte, playing_time_min, total_shots, standard_sot, performance_gls, created_at)
                            VALUES (:pn, :tn, 'futbol', :pt, :ts, :ss, :pg, :ca)
                        """),
                        {
                            "pn": player_name, "tn": team_name,
                            "pt": playing_time, "ts": total_shots,
                            "ss": standard_sot, "pg": performance_gls,
                            "ca": datetime.utcnow(),
                        }
                    )
                    total_raw += 1

                session.commit()

            logger.info(f"  {liga} {temp}: {len(df)} jugadores procesados")
            time.sleep(random.randint(15, 35))

    logger.info(f"[FUTBOL] {total_raw} registros raw_player_data insertados.")


# ──────────────────────────────────────────────────────────────────────────────
# PASO 4: 365SCORES PLAYER PROPS
# ──────────────────────────────────────────────────────────────────────────────

def cargar_365scores_player_props(dias_atras: int = 7):
    """Carga player props desde 365Scores para partidos recientes."""
    logger.info(f"[FUTBOL] Cargando 365Scores player props (ultimos {dias_atras} dias)...")

    try:
        from src.data_ingestion.scrapers.scores365_client import Scores365Client
    except ImportError:
        logger.error("No se pudo importar Scores365Client")
        return

    client = Scores365Client(target_competitions=[7, 11, 17, 25, 67, 229])

    from datetime import timedelta
    fechas = [(datetime.now() - timedelta(days=d)).strftime("%d/%m/%Y") for d in range(dias_atras)]

    total_props = 0

    for fecha in fechas:
        try:
            import asyncio
            game_ids = asyncio.run(client.get_fixtures_by_date(fecha))
        except Exception as e:
            logger.warning(f"  Error obteniendo fixtures {fecha}: {e}")
            continue

        for game_id in game_ids:
            try:
                df_stats = client.get_match_stats(game_id)
                df_players = client.get_soccer_player_stats(game_id)

                if df_stats is not None and not df_stats.empty:
                    with Session(engine) as session:
                        row = df_stats.iloc[0]
                        home_id = resolve_team(session, str(row.get('home_team_name', '')))
                        away_id = resolve_team(session, str(row.get('away_team_name', '')))

                        if home_id and away_id:
                            existing = session.query(Match).filter(Match.id_partido == game_id).first()
                            if not existing:
                                session.add(Match(
                                    id_partido=game_id,
                                    id_local=home_id,
                                    id_visitante=away_id,
                                    fecha=datetime.now(),
                                    fstatus='Ended',
                                ))

                                session.add(MatchStatsFutbol(
                                    id_partido=game_id,
                                    goles_local=int(row.get('home_goals', 0)),
                                    goles_visitante=int(row.get('away_goals', 0)),
                                    tiros_puerta_local=int(row.get('home_shots_on_target', 0)),
                                    tiros_puerta_visitante=int(row.get('away_shots_on_target', 0)),
                                    corners_local=int(row.get('home_corners', 0)),
                                    corners_visitante=int(row.get('away_corners', 0)),
                                    posesion_local=int(row.get('home_ball_possession', 0)),
                                    posesion_visitante=int(row.get('away_ball_possession', 0)),
                                ))
                                session.commit()

                if df_players is not None and not df_players.empty:
                    with Session(engine) as session:
                        for _, p_row in df_players.iterrows():
                            player_id = int(p_row.get('id_jugador', 0))
                            player_name = str(p_row.get('nombre_jugador', ''))
                            team_id = int(p_row.get('team_id', 0))
                            team_name = str(p_row.get('team_name', ''))

                            if not player_id or not player_name:
                                continue

                            existing_player = session.query(Player).filter(Player.id_jugador == player_id).first()
                            if not existing_player:
                                team_fk = resolve_team(session, team_name)
                                session.add(Player(
                                    id_jugador=player_id,
                                    id_equipo=team_fk or team_id,
                                    nombre=player_name,
                                ))

                            existing_prop = session.query(PlayerStatsFutbol).filter_by(
                                id_partido=game_id, id_jugador=player_id
                            ).first()
                            if not existing_prop:
                                session.add(PlayerStatsFutbol(
                                    id_partido=game_id,
                                    id_jugador=player_id,
                                    minutos=int(p_row.get('minutos', 0)),
                                    goles=int(p_row.get('goles', 0)),
                                    asistencias=int(p_row.get('asistencias', 0)),
                                    tiros_totales=int(p_row.get('tiros_totales', 0)),
                                    tiros_puerta=int(p_row.get('tiros_puerta', 0)),
                                    pases_precisos=int(p_row.get('pases_precisos', 0)),
                                    faltas_cometidas=int(p_row.get('faltas_cometidas', 0)),
                                    amarillas=int(p_row.get('amarillas', 0)),
                                    rojas=int(p_row.get('rojas', 0)),
                                ))
                                total_props += 1

                        session.commit()

            except Exception as e:
                logger.warning(f"  Error procesando game {game_id}: {e}")
                continue

            time.sleep(2)

    logger.info(f"[FUTBOL] {total_props} player props insertados.")


# ──────────────────────────────────────────────────────────────────────────────
# ORQUESTADOR
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ingesta Futbol — It's Coming")
    parser.add_argument('--ligas', nargs='+', default=None)
    parser.add_argument('--temporadas', nargs='+', default=None)
    parser.add_argument('--todo', action='store_true')
    parser.add_argument('--solo-csv', action='store_true')
    parser.add_argument('--solo-fbref', action='store_true')
    parser.add_argument('--solo-365scores', action='store_true')
    parser.add_argument('--solo-equipos', action='store_true')
    parser.add_argument('--solo-promedios', action='store_true', help="Solo calcular promedios de equipos")
    parser.add_argument('--dias-atras', type=int, default=7)

    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info(" INGESTA FUTBOL")
    logger.info("=" * 50)

    if args.todo or args.solo_equipos:
        cargar_equipos_espn()

    if args.todo or args.solo_csv:
        cargar_partidos_csv(ligas=args.ligas, temporadas=args.temporadas)
        calcular_promedios_equipos()

    if args.solo_promedios:
        calcular_promedios_equipos()

    if args.todo or args.solo_fbref:
        cargar_fbref_player_stats(ligas=args.ligas, temporadas=args.temporadas)

    if args.todo or args.solo_365scores:
        cargar_365scores_player_props(dias_atras=args.dias_atras)

    logger.info("=" * 50)
    logger.info(" INGESTA FUTBOL COMPLETADA")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
