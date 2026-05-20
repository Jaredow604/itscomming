"""
ingesta_nba.py — Ingesta completa de NBA (2+ temporadas)

Fuentes:
  - NBA API (nba_api): Player game logs historicos
  - ESPN API: Equipos y logos
  - 365Scores: Stats de partidos

Uso:
    python scripts/ingesta_nba.py --todo
    python scripts/ingesta_nba.py --temporadas 2023-24 2024-25 2025-26
    python scripts/ingesta_nba.py --solo-equipos
    python scripts/ingesta_nba.py --solo-backfill
"""

import os
import sys
import logging
import argparse
import time
from datetime import datetime, timedelta
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
    MatchStatsNBA, PlayerStatsNBA,
    NBAPlayerHistory, NBAPlayerStatsClean,
    RawPlayerData,
)
from database import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("IngestaNBA")

ESPN_NBA = {
    "league_name": "NBA",
    "prefix": 200000,
    "url": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams?limit=100",
}

TEMPORADAS_NBA = ["2023-24", "2024-25", "2025-26"]


def resolve_team(session, nombre: str) -> int | None:
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

    result = session.execute(
        text("SELECT id_equipo FROM equipos WHERE LOWER(nombre) LIKE :p LIMIT 1"),
        {"p": f"%{nombre_lower}%"}
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
# PASO 1: EQUIPOS NBA DESDE ESPN
# ──────────────────────────────────────────────────────────────────────────────

def cargar_equipos_nba():
    logger.info("[NBA] Cargando equipos desde ESPN API...")

    with Session(engine) as session:
        try:
            resp = requests.get(ESPN_NBA["url"], timeout=15)
            if resp.status_code != 200:
                logger.error(f"  Error HTTP: {resp.status_code}")
                return

            data = resp.json()
            teams = data.get('sports', [{}])[0].get('leagues', [{}])[0].get('teams', [])

            total = 0
            for item in teams:
                t = item.get('team', {})
                espn_id = int(t.get('id', 0))
                canonical_id = ESPN_NBA["prefix"] + espn_id
                nombre = t.get('displayName', t.get('name', ''))
                corto = t.get('shortDisplayName', '')
                logos = t.get('logos', [])
                logo = logos[0].get('href', '') if logos else ''

                existing = session.query(Team).filter(Team.id_equipo == canonical_id).first()
                if existing:
                    if not existing.logo_url and logo:
                        existing.logo_url = logo
                        existing.liga = "NBA"
                    continue

                session.add(Team(
                    id_equipo=canonical_id,
                    nombre=nombre,
                    liga="NBA",
                    logo_url=logo,
                ))
                session.flush()
                add_alias(session, nombre, canonical_id)
                if corto and corto != nombre:
                    add_alias(session, corto, canonical_id)
                total += 1

            session.commit()
            logger.info(f"[NBA] {total} equipos nuevos.")

        except Exception as e:
            logger.error(f"  Error: {e}")
            session.rollback()


# ──────────────────────────────────────────────────────────────────────────────
# PASO 2: BACKFILL HISTORICO NBA (nba_api)
# ──────────────────────────────────────────────────────────────────────────────

def cargar_historico_nba(temporadas=None):
    """Backfill historico de NBA usando nba_api."""
    temporadas = temporadas or TEMPORADAS_NBA
    logger.info(f"[NBA] Backfill historico: {temporadas}")

    try:
        from nba_api.stats.endpoints import playergamelogs
    except ImportError:
        logger.error("nba_api no instalado. pip install nba_api")
        return

    total_logs = 0
    total_partidos = 0

    for temporada in temporadas:
        year_str = temporada.split('-')[0]
        start_date = f"{year_str}-10-01"
        end_year = int(year_str) + 1
        end_date = f"{end_year}-06-30"

        fechas = pd.date_range(start=start_date, end=end_date)
        logger.info(f"  Temporada {temporada}: {len(fechas)} dias")

        for idx, fecha in enumerate(fechas):
            fecha_nba = fecha.strftime("%m/%d/%Y")
            fecha_str = fecha.strftime("%d/%m/%Y")

            if idx % 30 == 0:
                logger.info(f"  Progreso: {idx}/{len(fechas)} dias...")

            for attempt in range(3):
                try:
                    time.sleep(1)
                    logs = playergamelogs.PlayerGameLogs(
                        date_from_nullable=fecha_nba,
                        date_to_nullable=fecha_nba,
                        season_nullable=temporada,
                    )
                    df = logs.get_data_frames()[0]
                    break
                except Exception as e:
                    if attempt == 2:
                        logger.warning(f"  Error {fecha_str}: {e}")
                        df = pd.DataFrame()
                    else:
                        time.sleep(3 ** attempt)

            if df is None or df.empty:
                continue

            with Session(engine) as session:
                for _, row in df.iterrows():
                    player_name = str(row.get('PLAYER_NAME', ''))
                    team_name = str(row.get('TEAM_NAME', ''))
                    game_id = str(row.get('Game_ID', ''))
                    game_date = str(row.get('GAME_DATE', ''))
                    matchup = str(row.get('MATCHUP', ''))

                    if not player_name or not game_id:
                        continue

                    pts = int(row.get('PTS', 0))
                    reb = int(row.get('REB', 0))
                    ast = int(row.get('AST', 0))
                    stl = int(row.get('STL', 0))
                    blk = int(row.get('BLK', 0))
                    tov = int(row.get('TOV', 0))
                    fg3m = int(row.get('FG3M', 0))
                    minutos = int(row.get('MIN', 0))

                    existing_hist = session.query(NBAPlayerHistory).filter_by(
                        game_id=game_id,
                        player_name=player_name,
                        game_date=game_date,
                    ).first()

                    if not existing_hist:
                        team_id = resolve_team(session, team_name)

                        session.add(NBAPlayerHistory(
                            season_year=temporada,
                            player_name=player_name,
                            team_name=team_name,
                            game_id=game_id,
                            game_date=game_date,
                            matchup=matchup,
                            equipo_fk=team_id,
                        ))
                        total_logs += 1

                    existing_clean = session.query(NBAPlayerStatsClean).filter_by(
                        player_name=player_name,
                        team_name=team_name,
                    ).first()

                    if not existing_clean:
                        team_id = resolve_team(session, team_name)
                        session.add(NBAPlayerStatsClean(
                            player_name=player_name,
                            team_name=team_name,
                            equipo_fk=team_id,
                        ))

                    player_id = hash(player_name) % 900000 + 100000
                    existing_player = session.query(Player).filter(Player.id_jugador == player_id).first()
                    if not existing_player:
                        team_fk = resolve_team(session, team_name)
                        session.add(Player(
                            id_jugador=player_id,
                            id_equipo=team_fk or 200000,
                            nombre=player_name,
                        ))

                    match_id = int(game_id) if game_id.isdigit() else hash(game_id) % 9000000 + 1000000
                    existing_match = session.query(Match).filter(Match.id_partido == match_id).first()
                    if not existing_match:
                        home_team = team_name if 'vs' in matchup else matchup.split('@')[-1] if '@' in matchup else team_name
                        away_team = matchup.split('@')[0] if '@' in matchup else (matchup.split('vs')[0] if 'vs' in matchup else team_name)

                        home_id = resolve_team(session, home_team)
                        away_id = resolve_team(session, away_team)

                        if home_id and away_id:
                            try:
                                game_dt = datetime.strptime(game_date, "%m/%d/%Y")
                            except:
                                game_dt = datetime.now()

                            session.add(Match(
                                id_partido=match_id,
                                id_local=home_id,
                                id_visitante=away_id,
                                fecha=game_dt,
                                fstatus='Ended',
                            ))

                            session.add(MatchStatsNBA(
                                id_partido=match_id,
                                puntos_local=0,
                                puntos_visitante=0,
                            ))
                            total_partidos += 1

                    existing_prop = session.query(PlayerStatsNBA).filter_by(
                        id_partido=match_id, id_jugador=player_id
                    ).first()
                    if not existing_prop:
                        session.add(PlayerStatsNBA(
                            id_partido=match_id,
                            id_jugador=player_id,
                            minutos=minutos,
                            puntos=pts,
                            rebotes=reb,
                            asistencias=ast,
                            robos=stl,
                            bloqueos=blk,
                            perdidas=tov,
                            triples=fg3m,
                        ))

                    session.add(RawPlayerData(
                        player_name=player_name,
                        team_name=team_name,
                        deporte='nba',
                        pts=pts,
                        reb=reb,
                        ast=ast,
                        playing_time_min=minutos,
                        performance_gls=pts,
                        jugador_fk=player_id,
                        created_at=datetime.utcnow(),
                    ))

                session.commit()

            time.sleep(1)

    logger.info(f"[NBA] {total_logs} game logs, {total_partidos} partidos core.")


# ──────────────────────────────────────────────────────────────────────────────
# ORQUESTADOR
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ingesta NBA — It's Coming")
    parser.add_argument('--temporadas', nargs='+', default=None)
    parser.add_argument('--todo', action='store_true')
    parser.add_argument('--solo-equipos', action='store_true')
    parser.add_argument('--solo-backfill', action='store_true')

    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info(" INGESTA NBA")
    logger.info("=" * 50)

    if args.todo or args.solo_equipos:
        cargar_equipos_nba()

    if args.todo or args.solo_backfill:
        cargar_historico_nba(temporadas=args.temporadas)

    logger.info("=" * 50)
    logger.info(" INGESTA NBA COMPLETADA")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
