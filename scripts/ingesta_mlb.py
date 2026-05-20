"""
ingesta_mlb.py — Ingesta completa de MLB (2+ temporadas)

Fuentes:
  - MLB statsapi: Datos oficiales de juegos y jugadores
  - ESPN API: Equipos y logos

Uso:
    python scripts/ingesta_mlb.py --todo
    python scripts/ingesta_mlb.py --temporadas 2023 2024 2025
    python scripts/ingesta_mlb.py --solo-equipos
    python scripts/ingesta_mlb.py --solo-backfill
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
    MatchStatsMLB, PlayerStatsMLB,
    RawPlayerData,
)
from database import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("IngestaMLB")

ESPN_MLB = {
    "league_name": "MLB",
    "prefix": 300000,
    "url": "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/teams?limit=100",
}

TEMPORADAS_MLB = [2023, 2024, 2025]


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
# PASO 1: EQUIPOS MLB DESDE ESPN
# ──────────────────────────────────────────────────────────────────────────────

def cargar_equipos_mlb():
    logger.info("[MLB] Cargando equipos desde ESPN API...")

    with Session(engine) as session:
        try:
            resp = requests.get(ESPN_MLB["url"], timeout=15)
            if resp.status_code != 200:
                logger.error(f"  Error HTTP: {resp.status_code}")
                return

            data = resp.json()
            teams = data.get('sports', [{}])[0].get('leagues', [{}])[0].get('teams', [])

            total = 0
            for item in teams:
                t = item.get('team', {})
                espn_id = int(t.get('id', 0))
                canonical_id = ESPN_MLB["prefix"] + espn_id
                nombre = t.get('displayName', t.get('name', ''))
                corto = t.get('shortDisplayName', '')
                logos = t.get('logos', [])
                logo = logos[0].get('href', '') if logos else ''

                existing = session.query(Team).filter(Team.id_equipo == canonical_id).first()
                if existing:
                    if not existing.logo_url and logo:
                        existing.logo_url = logo
                        existing.liga = "MLB"
                    continue

                session.add(Team(
                    id_equipo=canonical_id,
                    nombre=nombre,
                    liga="MLB",
                    logo_url=logo,
                ))
                session.flush()
                add_alias(session, nombre, canonical_id)
                if corto and corto != nombre:
                    add_alias(session, corto, canonical_id)
                total += 1

            session.commit()
            logger.info(f"[MLB] {total} equipos nuevos.")

        except Exception as e:
            logger.error(f"  Error: {e}")
            session.rollback()


# ──────────────────────────────────────────────────────────────────────────────
# PASO 2: BACKFILL HISTORICO MLB (statsapi)
# ──────────────────────────────────────────────────────────────────────────────

def cargar_historico_mlb(temporadas=None):
    """Backfill historico de MLB usando statsapi."""
    temporadas = temporadas or TEMPORADAS_MLB
    logger.info(f"[MLB] Backfill historico: {temporadas}")

    try:
        import statsapi
    except ImportError:
        logger.error("statsapi no instalado. pip install MLB-StatsAPI")
        return

    total_juegos = 0
    total_player_stats = 0

    for year in temporadas:
        start_date = f"{year}-03-01"
        end_date = f"{year}-11-30"

        fechas = pd.date_range(start=start_date, end=end_date, freq='7D')
        logger.info(f"  Temporada {year}: procesando por semanas...")

        for fecha in fechas:
            fmt_date = fecha.strftime("%Y-%m-%d")

            try:
                schedule = statsapi.schedule(date=fmt_date)
            except Exception as e:
                logger.warning(f"  Error schedule {fmt_date}: {e}")
                time.sleep(5)
                continue

            if not schedule:
                continue

            for game in schedule:
                game_id = game.get('game_id', 0)
                home_name = game.get('home_name', '')
                away_name = game.get('away_name', '')
                game_date = game.get('game_date', '')

                if not game_id:
                    continue

                try:
                    box = statsapi.boxscore_data(game_id)
                except Exception as e:
                    logger.warning(f"  Error boxscore {game_id}: {e}")
                    continue

                if not box:
                    continue

                with Session(engine) as session:
                    home_id = resolve_team(session, home_name)
                    away_id = resolve_team(session, away_name)

                    if home_id and away_id:
                        existing_match = session.query(Match).filter(Match.id_partido == game_id).first()
                        if not existing_match:
                            try:
                                game_dt = datetime.strptime(game_date, "%Y-%m-%dT%H:%M:%SZ") if game_date else datetime.now()
                            except:
                                game_dt = datetime.now()

                            session.add(Match(
                                id_partido=game_id,
                                id_local=home_id,
                                id_visitante=away_id,
                                fecha=game_dt,
                                fstatus='Ended',
                            ))

                            linescore = box.get('linescore', {})
                            innings = linescore.get('innings', [])

                            runs_home = sum(inn.get('home', 0) or 0 for inn in innings)
                            runs_away = sum(inn.get('away', 0) or 0 for inn in innings)
                            hits_home = linescore.get('hits', {}).get('home', 0)
                            hits_away = linescore.get('hits', {}).get('away', 0)
                            errors_home = linescore.get('errors', {}).get('home', 0)
                            errors_away = linescore.get('errors', {}).get('away', 0)

                            session.add(MatchStatsMLB(
                                id_partido=game_id,
                                carreras_local=runs_home,
                                carreras_visitante=runs_away,
                                hits_local=hits_home,
                                hits_visitante=hits_away,
                                errores_local=errors_home,
                                errores_visitante=errors_away,
                            ))
                            total_juegos += 1

                    for side in ['home', 'away']:
                        team_name = home_name if side == 'home' else away_name
                        players = box.get(side, {}).get('players', {})

                        for p_id, p_stats in players.items():
                            b_stats = p_stats.get('stats', {}).get('batting', {})
                            if not b_stats:
                                continue

                            player_name = p_stats.get('person', {}).get('fullName', '')
                            if not player_name:
                                continue

                            at_bats = int(b_stats.get('atBats', 0))
                            hits = int(b_stats.get('hits', 0))
                            runs = int(b_stats.get('runs', 0))
                            home_runs = int(b_stats.get('homeRuns', 0))
                            rbi = int(b_stats.get('rbi', 0))
                            bb = int(b_stats.get('baseOnBalls', 0))
                            so = int(b_stats.get('strikeOuts', 0))

                            player_id = int(p_id) if str(p_id).isdigit() else (hash(player_name) % 900000 + 300000)

                            existing_player = session.query(Player).filter(Player.id_jugador == player_id).first()
                            if not existing_player:
                                team_fk = resolve_team(session, team_name)
                                session.add(Player(
                                    id_jugador=player_id,
                                    id_equipo=team_fk or 300000,
                                    nombre=player_name,
                                ))

                            existing_prop = session.query(PlayerStatsMLB).filter_by(
                                id_partido=game_id, id_jugador=player_id
                            ).first()
                            if not existing_prop:
                                session.add(PlayerStatsMLB(
                                    id_partido=game_id,
                                    id_jugador=player_id,
                                    turnos_al_bate=at_bats,
                                    hits=hits,
                                    carreras=runs,
                                    home_runs=home_runs,
                                    carreras_impulsadas=rbi,
                                    bases_por_bolas=bb,
                                    ponches=so,
                                ))
                                total_player_stats += 1

                    session.commit()

            time.sleep(2)

    logger.info(f"[MLB] {total_juegos} juegos, {total_player_stats} player stats.")


# ──────────────────────────────────────────────────────────────────────────────
# ORQUESTADOR
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ingesta MLB — It's Coming")
    parser.add_argument('--temporadas', nargs='+', type=int, default=None)
    parser.add_argument('--todo', action='store_true')
    parser.add_argument('--solo-equipos', action='store_true')
    parser.add_argument('--solo-backfill', action='store_true')

    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info(" INGESTA MLB")
    logger.info("=" * 50)

    if args.todo or args.solo_equipos:
        cargar_equipos_mlb()

    if args.todo or args.solo_backfill:
        cargar_historico_mlb(temporadas=args.temporadas)

    logger.info("=" * 50)
    logger.info(" INGESTA MLB COMPLETADA")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
