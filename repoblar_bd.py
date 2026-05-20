"""
repoblar_bd.py — Script Maestro de Re-población de BD v3.0

Re-pobla toda la base de datos con datos historicos de 2+ temporadas.
Cubre Futbol (5 grandes ligas + Liga MX), NBA y MLB.

Uso:
    python repoblar_bd.py --todo
    python repoblar_bd.py --deporte futbol --liga PL --temporadas 2324,2425,2526
    python repoblar_bd.py --deporte nba --temporadas 2023-24,2024-25,2025-26
    python repoblar_bd.py --fase 1
    python repoblar_bd.py --solo-logos
    python repoblar_bd.py --reset-db
"""

import os
import sys
import logging
import argparse
import time
import json
from datetime import datetime, timedelta, timezone, timedelta
from pathlib import Path

import pandas as pd
import numpy as np
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sklearn.preprocessing import RobustScaler

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURACION DE RUTAS
# ──────────────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.models import (
    Base, Team, Player, Match, AliasEquipo,
    MatchStatsFutbol, MatchStatsNBA, MatchStatsMLB,
    PlayerStatsFutbol, PlayerStatsNBA, PlayerStatsMLB,
    LeagueTable, MatchHistoryStats, MLMatchFeatures,
    TeamRollingStats, ScalerRegistry, DailySchedule,
    RawPlayerData, InferenceReadyPlayerData,
    FBrefTeamStats, FBrefPlayerStats,
    NBAPlayerHistory, NBAPlayerStatsClean,
    MLMatchFeatures as MLMatchFeaturesModel,
    MatchHistoryStats as MatchHistoryStatsModel,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / "repoblar.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("RepoblarBD")

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURACION GLOBAL
# ──────────────────────────────────────────────────────────────────────────────

DB_URL = os.getenv(
    "DB_URL",
    "postgresql+psycopg2://postgres:Jk9oe@localhost:5432/itscoming_db"
)

engine = create_engine(DB_URL)

SCALER_DIR = PROJECT_ROOT / "src" / "pipeline" / "scalers"
SCALER_DIR.mkdir(parents=True, exist_ok=True)

LOGOS_DIR = PROJECT_ROOT / "media" / "logos"
LOGOS_DIR.mkdir(parents=True, exist_ok=True)

# Ligas football-data.co.uk (CSVs historicos gratuitos)
FOOTBALL_DATA_UK = {
    "PL":  {"url_template": "https://www.football-data.co.uk/mmz4281/{season}/E0.csv", "nombre": "Premier League"},
    "SP1": {"url_template": "https://www.football-data.co.uk/mmz4281/{season}/SP1.csv", "nombre": "La Liga"},
    "D1":  {"url_template": "https://www.football-data.co.uk/mmz4281/{season}/D1.csv", "nombre": "Bundesliga"},
    "I1":  {"url_template": "https://www.football-data.co.uk/mmz4281/{season}/I1.csv", "nombre": "Serie A"},
    "F1":  {"url_template": "https://www.football-data.co.uk/mmz4281/{season}/F1.csv", "nombre": "Ligue 1"},
}

# Temporadas disponibles en football-data.co.uk
TEMPORADAS_FUTBOL = ["2324", "2425", "2526"]

# ESPN API para logos y equipos
ESPN_LEAGUES = [
    {"league_name": "Premier League", "sport": "soccer", "prefix": 100000,
     "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/teams?limit=100"},
    {"league_name": "La Liga", "sport": "soccer", "prefix": 100000,
     "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/teams?limit=100"},
    {"league_name": "Liga MX", "sport": "soccer", "prefix": 100000,
     "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/mex.1/teams?limit=100"},
    {"league_name": "NBA", "sport": "basketball", "prefix": 200000,
     "url": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams?limit=100"},
    {"league_name": "MLB", "sport": "baseball", "prefix": 300000,
     "url": "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/teams?limit=100"},
]

# Logos de ligas (URLs publicas)
LEAGUE_LOGOS = {
    "Premier League": "https://logos-world.net/wp-content/uploads/2020/06/Premier-League-Logo.png",
    "La Liga": "https://logos-world.net/wp-content/uploads/2020/06/La-Liga-Logo.png",
    "Bundesliga": "https://logos-world.net/wp-content/uploads/2020/06/Bundesliga-Logo.png",
    "Serie A": "https://logos-world.net/wp-content/uploads/2020/06/Serie-A-Logo.png",
    "Ligue 1": "https://logos-world.net/wp-content/uploads/2020/06/Ligue-1-Logo.png",
    "Liga MX": "https://img.azscore.com/soccer/league/229.png",
    "NBA": "https://logos-world.net/wp-content/uploads/2020/11/NBA-Logo.png",
    "MLB": "https://logos-world.net/wp-content/uploads/2020/11/MLB-Logo.png",
    "Champions League": "https://logos-world.net/wp-content/uploads/2020/06/Champions-League-Logo.png",
}


# ──────────────────────────────────────────────────────────────────────────────
# UTILIDADES
# ──────────────────────────────────────────────────────────────────────────────

def descargar_logo(url: str, nombre_archivo: str) -> str:
    """Descarga un logo y lo guarda localmente. Retorna la ruta relativa."""
    if not url:
        return ""
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            ruta_local = LOGOS_DIR / nombre_archivo
            with open(ruta_local, "wb") as f:
                f.write(resp.content)
            return f"/media/logos/{nombre_archivo}"
    except Exception as e:
        logger.warning(f"Error descargando logo {url}: {e}")
    return url


def resolve_team_id(session, nombre: str, liga: str = None) -> int | None:
    """Resuelve un nombre de equipo a su id_equipo usando alias."""
    nombre_lower = nombre.lower().strip()

    result = session.execute(
        text("""
            SELECT a.id_equipo FROM alias_equipos a
            JOIN equipos e ON e.id_equipo = a.id_equipo
            WHERE a.nombre_fuente = :nombre
            LIMIT 1
        """),
        {"nombre": nombre_lower}
    ).fetchone()
    if result:
        return result[0]

    result = session.execute(
        text("""
            SELECT id_equipo FROM equipos
            WHERE LOWER(nombre) = :nombre
            LIMIT 1
        """),
        {"nombre": nombre_lower}
    ).fetchone()
    if result:
        return result[0]

    if liga:
        result = session.execute(
            text("""
                SELECT id_equipo FROM equipos
                WHERE LOWER(nombre) LIKE :pattern AND liga = :liga
                LIMIT 1
            """),
            {"pattern": f"%{nombre_lower}%", "liga": liga}
        ).fetchone()
        if result:
            return result[0]

    return None


def crear_alias(session, nombre_fuente: str, id_equipo: int):
    """Crea un alias para un equipo si no existe."""
    existing = session.execute(
        text("SELECT id FROM alias_equipos WHERE nombre_fuente = :nombre"),
        {"nombre": nombre_fuente.lower().strip()}
    ).fetchone()
    if not existing:
        session.execute(
            text("INSERT INTO alias_equipos (nombre_fuente, id_equipo) VALUES (:nombre, :id)"),
            {"nombre": nombre_fuente.lower().strip(), "id": id_equipo}
        )


# ──────────────────────────────────────────────────────────────────────────────
# FASE 0: RESET (opcional)
# ──────────────────────────────────────────────────────────────────────────────

def fase0_reset_db():
    """Elimina y recrea todas las tablas. DESTRUCTIVO."""
    logger.warning("RESET DB: Eliminando todas las tablas...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.info("RESET DB: Tablas recreadas.")


# ──────────────────────────────────────────────────────────────────────────────
# FASE 1: BOOTSTRAP EQUIPOS + LOGOS (ESPN API)
# ──────────────────────────────────────────────────────────────────────────────

def fase1_bootstrap_equipos():
    """Carga equipos desde ESPN API con logos y alias."""
    logger.info("[FASE 1] Bootstrap de equipos y logos desde ESPN API...")

    with Session(engine) as session:
        total_nuevos = 0

        for config in ESPN_LEAGUES:
            logger.info(f"  Extrayendo: {config['league_name']}...")
            try:
                resp = requests.get(config["url"], timeout=15)
                if resp.status_code != 200:
                    logger.warning(f"  Error HTTP con {config['league_name']}")
                    continue

                data = resp.json()
                teams_array = data.get('sports', [{}])[0].get('leagues', [{}])[0].get('teams', [])

                for item in teams_array:
                    t_data = item.get('team', {})
                    espn_id = int(t_data.get('id', 0))
                    id_canonical = config["prefix"] + espn_id

                    nombre = t_data.get('displayName', t_data.get('name', ''))
                    nombre_corto = t_data.get('shortDisplayName', '')

                    logos = t_data.get('logos', [])
                    logo_url = logos[0].get('href', '') if logos else ''

                    existing = session.query(Team).filter(Team.id_equipo == id_canonical).first()
                    if existing:
                        if not existing.logo_url and logo_url:
                            existing.logo_url = logo_url
                        continue

                    new_team = Team(
                        id_equipo=id_canonical,
                        nombre=nombre,
                        liga=config["league_name"],
                        logo_url=logo_url,
                    )
                    session.add(new_team)
                    session.flush()

                    crear_alias(session, nombre, id_canonical)
                    if nombre_corto and nombre_corto != nombre:
                        crear_alias(session, nombre_corto, id_canonical)

                    total_nuevos += 1

                session.commit()
                logger.info(f"  {len(teams_array)} equipos procesados para {config['league_name']}.")

            except Exception as e:
                logger.error(f"  Error con {config['league_name']}: {e}")
                session.rollback()

        logger.info(f"[FASE 1] {total_nuevos} equipos nuevos insertados.")


# ──────────────────────────────────────────────────────────────────────────────
# FASE 2: HISTORICO PARTIDOS FUTBOL (football-data.co.uk)
# ──────────────────────────────────────────────────────────────────────────────

def fase2_historico_futbol(ligas: list = None, temporadas: list = None):
    """Carga historico de partidos desde football-data.co.uk CSVs."""
    ligas = ligas or list(FOOTBALL_DATA_UK.keys())
    temporadas = temporadas or TEMPORADAS_FUTBOL

    logger.info(f"[FASE 2] Historico futbol: ligas={ligas}, temporadas={temporadas}")

    total_insertados = 0
    total_omitidos = 0

    for liga_key in ligas:
        liga_info = FOOTBALL_DATA_UK[liga_key]
        nombre_liga = liga_info["nombre"]

        for temporada in temporadas:
            url = liga_info["url_template"].format(season=temporada)
            logger.info(f"  Descargando {nombre_liga} temporada {temporada}...")

            try:
                df = pd.read_csv(url)
            except Exception as e:
                logger.warning(f"  No se pudo descargar {url}: {e}")
                continue

            if df.empty:
                continue

            col_map = {
                'Date': 'date', 'HomeTeam': 'home_team', 'AwayTeam': 'away_team',
                'FTHG': 'home_score', 'FTAG': 'away_score',
                'HS': 'home_shots', 'AS': 'away_shots',
                'HST': 'home_shots_on_target', 'AST': 'away_shots_on_target',
                'HC': 'home_corners', 'AC': 'away_corners',
                'HY': 'home_yellow_cards', 'AY': 'away_yellow_cards',
                'HR': 'home_red_cards', 'AR': 'away_red_cards',
                'B365H': 'odd_home', 'B365D': 'odd_draw', 'B365A': 'odd_away',
            }
            df = df.rename(columns=col_map)
            df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
            df = df.dropna(subset=['date', 'home_team', 'away_team'])

            season_label = f"{temporada[:2]}-{temporada[2:]}"

            with Session(engine) as session:
                for _, row in df.iterrows():
                    match_date = row['date']
                    home_name = row['home_team']
                    away_name = row['away_team']

                    existing = session.query(MatchHistoryStats).filter_by(
                        home_team=home_name,
                        away_team=away_name,
                        date=match_date,
                        league=nombre_liga,
                        season=season_label,
                    ).first()

                    if existing:
                        total_omitidos += 1
                        continue

                    home_score = int(row['home_score']) if pd.notna(row.get('home_score')) else None
                    away_score = int(row['away_score']) if pd.notna(row.get('away_score')) else None

                    record = MatchHistoryStats(
                        league=nombre_liga,
                        season=season_label,
                        date=match_date,
                        home_team=home_name,
                        away_team=away_name,
                        home_score=home_score,
                        away_score=away_score,
                    )
                    session.add(record)
                    total_insertados += 1

                session.commit()

            logger.info(f"  {nombre_liga} {temporada}: {len(df)} partidos procesados.")

    logger.info(f"[FASE 2] Total: {total_insertados} insertados, {total_omitidos} omitidos.")


# ──────────────────────────────────────────────────────────────────────────────
# FASE 3: RESOLVER FKs EN MATCH_HISTORY_STATS
# ──────────────────────────────────────────────────────────────────────────────

def fase3_resolver_fks():
    """Resuelve nombres de equipos a FKs en match_history_stats."""
    logger.info("[FASE 3] Resolviendo FKs en match_history_stats...")

    with Session(engine) as session:
        records = session.query(MatchHistoryStats).filter(
            MatchHistoryStats.local_fk.is_(None)
        ).all()

        resueltos = 0
        for record in records:
            local_id = resolve_team_id(session, record.home_team, record.league)
            visitante_id = resolve_team_id(session, record.away_team, record.league)

            if local_id:
                record.local_fk = local_id
            if visitante_id:
                record.visitante_fk = visitante_id

            resueltos += 1

        session.commit()
        logger.info(f"[FASE 3] {resueltos} registros procesados.")


# ──────────────────────────────────────────────────────────────────────────────
# FASE 4: FEATURE ENGINEERING (ANTI-DATA-LEAKAGE)
# ──────────────────────────────────────────────────────────────────────────────

def fase4_feature_engineering(ventana: int = 5):
    """Calcula features rolling con shift(1) para evitar data leakage."""
    logger.info(f"[FASE 4] Feature engineering con ventana={ventana}...")

    with engine.connect() as conn:
        df = pd.read_sql(
            text("SELECT * FROM match_history_stats WHERE home_score IS NOT NULL AND away_score IS NOT NULL"),
            conn
        )

    if df.empty:
        logger.warning("[FASE 4] Sin datos. Ejecuta Fase 2 primero.")
        return

    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(['league', 'date']).reset_index(drop=True)

    all_clean = []

    for liga_name, df_liga in df.groupby('league'):
        logger.info(f"  Procesando {liga_name} ({len(df_liga)} partidos)...")
        df_liga = df_liga.sort_values('date').reset_index(drop=True)

        home_ledger = df_liga[['date', 'home_team', 'home_score', 'away_score']].copy()
        home_ledger.columns = ['date', 'team', 'gf', 'ga']
        away_ledger = df_liga[['date', 'away_team', 'away_score', 'home_score']].copy()
        away_ledger.columns = ['date', 'team', 'gf', 'ga']

        ledger = pd.concat([home_ledger, away_ledger]).sort_values(['team', 'date']).reset_index(drop=True)

        for col in ['gf', 'ga']:
            ledger[f'rolling_{col}'] = ledger.groupby('team')[col].transform(
                lambda x: x.shift(1).rolling(ventana, min_periods=1).mean()
            )

        for _, lrow in ledger.iterrows():
            mask = (df_liga['date'] == lrow['date']) & (
                (df_liga['home_team'] == lrow['team']) | (df_liga['away_team'] == lrow['team'])
            )
            idxs = df_liga[mask].index
            for idx in idxs:
                if df_liga.at[idx, 'home_team'] == lrow['team']:
                    df_liga.at[idx, 'home_form_gf'] = lrow['rolling_gf']
                    df_liga.at[idx, 'home_form_ga'] = lrow['rolling_ga']
                else:
                    df_liga.at[idx, 'away_form_gf'] = lrow['rolling_gf']
                    df_liga.at[idx, 'away_form_ga'] = lrow['rolling_ga']

        df_liga['total_goals'] = df_liga['home_score'] + df_liga['away_score']
        df_liga['result'] = df_liga.apply(
            lambda r: 1 if r['home_score'] > r['away_score'] else (0 if r['home_score'] == r['away_score'] else 2),
            axis=1
        )

        all_clean.append(df_liga)

    df = pd.concat(all_clean, ignore_index=True)

    logger.info(f"[FASE 4] {len(df)} partidos con features calculadas.")

    with Session(engine) as session:
        session.execute(text("DELETE FROM ml_match_features"))

        for idx in range(len(df)):
            row = df.iloc[idx]
            feat = MLMatchFeatures(
                league=str(row.get('league', '')),
                season=str(row.get('season', '')),
                date=row['date'],
                home_team=str(row['home_team']),
                away_team=str(row['away_team']),
                home_score=int(row['home_score']) if pd.notna(row.get('home_score')) else None,
                away_score=int(row['away_score']) if pd.notna(row.get('away_score')) else None,
                home_form_gf=float(row['home_form_gf']) if pd.notna(row.get('home_form_gf')) else None,
                home_form_ga=float(row['home_form_ga']) if pd.notna(row.get('home_form_ga')) else None,
                away_form_gf=float(row['away_form_gf']) if pd.notna(row.get('away_form_gf')) else None,
                away_form_ga=float(row['away_form_ga']) if pd.notna(row.get('away_form_ga')) else None,
                total_goals=int(row['total_goals']) if pd.notna(row.get('total_goals')) else None,
                result=int(row['result']) if pd.notna(row.get('result')) else None,
            )
            session.add(feat)

        session.commit()

    logger.info("[FASE 4] ml_match_features guardado.")

    with Session(engine) as session:
        updated = 0
        for idx in range(len(df)):
            row = df.iloc[idx]
            existing = session.query(MatchHistoryStats).filter_by(
                home_team=str(row['home_team']),
                away_team=str(row['away_team']),
                date=row['date'],
            ).first()
            if existing:
                v = row.get('home_form_gf')
                existing.home_form_gf = float(v) if pd.notna(v) else None
                v = row.get('home_form_ga')
                existing.home_form_ga = float(v) if pd.notna(v) else None
                v = row.get('away_form_gf')
                existing.away_form_gf = float(v) if pd.notna(v) else None
                v = row.get('away_form_ga')
                existing.away_form_ga = float(v) if pd.notna(v) else None
                v = row.get('total_goals')
                existing.total_goals = int(v) if pd.notna(v) else None
                v = row.get('result')
                existing.result = int(v) if pd.notna(v) else None
                updated += 1

        session.commit()

    logger.info(f"[FASE 4] {updated} registros en match_history_stats actualizados.")


# ──────────────────────────────────────────────────────────────────────────────
# FASE 5: TEAM ROLLING STATS
# ──────────────────────────────────────────────────────────────────────────────

def fase5_team_rolling_stats(ventana: int = 5, deporte: str = 'futbol'):
    """Calcula y almacena TeamRollingStats por equipo y fecha."""
    logger.info(f"[FASE 5] TeamRollingStats ventana={ventana}, deporte={deporte}...")

    with engine.connect() as conn:
        df = pd.read_sql(text("""
            SELECT mh.date, mh.home_team, mh.away_team,
                   mh.home_score, mh.away_score, mh.home_xg, mh.away_xg,
                   mh.local_fk, mh.visitante_fk
            FROM match_history_stats mh
            WHERE mh.home_score IS NOT NULL
            ORDER BY mh.date
        """), conn)

    if df.empty:
        logger.warning("[FASE 5] Sin datos.")
        return

    df['date'] = pd.to_datetime(df['date'])

    home_l = df[['date', 'home_team', 'home_score', 'away_score', 'home_xg', 'away_xg', 'local_fk']].copy()
    home_l.columns = ['date', 'team', 'gf', 'ga', 'xgf', 'xga', 'equipo_id']
    away_l = df[['date', 'away_team', 'away_score', 'home_score', 'away_xg', 'home_xg', 'visitante_fk']].copy()
    away_l.columns = ['date', 'team', 'gf', 'ga', 'xgf', 'xga', 'equipo_id']

    ledger = pd.concat([home_l, away_l]).sort_values(['team', 'date']).reset_index(drop=True)

    for col in ['gf', 'ga', 'xgf', 'xga']:
        ledger[col] = pd.to_numeric(ledger[col], errors='coerce')
        ledger[f'rolling_{col}'] = ledger.groupby('team')[col].transform(
            lambda x: x.shift(1).rolling(ventana, min_periods=1).mean()
        )

    with engine.connect() as conn:
        inserted = 0
        for _, row in ledger.iterrows():
            equipo_id = int(row['equipo_id']) if pd.notna(row.get('equipo_id')) else None
            if not equipo_id:
                continue

            rgf = row.get('rolling_gf')
            rga = row.get('rolling_ga')
            rxgf = row.get('rolling_xgf')
            rxga = row.get('rolling_xga')

            conn.execute(text("""
                INSERT INTO team_rolling_stats
                (id_equipo, fecha_calculo, ventana, deporte,
                 prom_goles_favor, prom_goles_contra, prom_xg_favor, prom_xg_contra, creado_en)
                VALUES
                (:eq, :fc, :v, :dep, :gf, :ga, :xgf, :xga, NOW())
                ON CONFLICT DO NOTHING
            """), {
                "eq": equipo_id, "fc": row['date'], "v": ventana, "dep": deporte,
                "gf": float(rgf) if pd.notna(rgf) else None,
                "ga": float(rga) if pd.notna(rga) else None,
                "xgf": float(rxgf) if pd.notna(rxgf) else None,
                "xga": float(rxga) if pd.notna(rxga) else None,
            })
            inserted += 1

        conn.commit()

    logger.info(f"[FASE 5] {inserted} registros en team_rolling_stats.")


# ──────────────────────────────────────────────────────────────────────────────
# FASE 6: ACTUALIZAR PROMEDIOS UI
# ──────────────────────────────────────────────────────────────────────────────

def fase6_promedios_ui():
    """Actualiza prom_goles, prom_corners, prom_tiros_puerta en equipos."""
    logger.info("[FASE 6] Actualizando promedios UI...")

    with engine.connect() as conn:
        df = pd.read_sql(text("""
            SELECT home_team, away_team, home_score, away_score
            FROM match_history_stats
            WHERE home_score IS NOT NULL
        """), conn)

    if df.empty:
        logger.warning("[FASE 6] Sin datos de partidos.")
        return

    equipos_unicos = sorted(
        set(df['home_team'].dropna().unique()) | set(df['away_team'].dropna().unique())
    )

    with engine.connect() as conn:
        updated = 0
        for nombre in equipos_unicos:
            df_h = df[df['home_team'] == nombre]
            df_a = df[df['away_team'] == nombre]
            total = len(df_h) + len(df_a)
            if total == 0:
                continue

            prom_goles = float((df_h['home_score'].sum() + df_a['away_score'].sum()) / total)

            result = conn.execute(
                text("""
                    UPDATE equipos SET
                        prom_goles = :pg
                    WHERE LOWER(nombre) = :nombre
                """),
                {"pg": round(prom_goles, 2), "nombre": nombre.lower()}
            )
            if result.rowcount > 0:
                updated += 1

        conn.commit()

    logger.info(f"[FASE 6] {updated} equipos actualizados.")


# ──────────────────────────────────────────────────────────────────────────────
# FASE 7: ENTRENAR SCALER + INFERENCE DATA
# ──────────────────────────────────────────────────────────────────────────────

def fase7_entrenar_scaler(deporte: str = 'futbol'):
    """Entrena RobustScaler y genera InferenceReadyPlayerData."""
    logger.info(f"[FASE 7] Entrenando scaler para {deporte}...")

    features_map = {
        'futbol': ['playing_time_min', 'total_shots', 'standard_sot'],
        'nba': ['pts', 'reb', 'ast'],
    }

    features = features_map.get(deporte, features_map['futbol'])

    with engine.connect() as conn:
        df_raw = pd.read_sql(
            text(f"SELECT * FROM ml_raw_player_data WHERE deporte = '{deporte}'"),
            conn
        )

    if df_raw.empty:
        logger.warning(f"[FASE 7] Sin datos crudos para {deporte}.")
        return

    features_disp = [f for f in features if f in df_raw.columns]
    if not features_disp:
        logger.error(f"[FASE 7] Ninguna feature disponible para {deporte}.")
        return

    df_train = df_raw[features_disp].fillna(df_raw[features_disp].median())

    scaler = RobustScaler()
    df_scaled = scaler.fit_transform(df_train)

    scaler_filename = f"player_stats_{deporte}_v3.joblib"
    scaler_path = str(SCALER_DIR / scaler_filename)
    import joblib
    joblib.dump(scaler, scaler_path)
    logger.info(f"[FASE 7] Scaler guardado en {scaler_path}")

    with Session(engine) as session:
        existing = session.query(ScalerRegistry).filter_by(nombre=scaler_filename).first()
        if existing:
            existing.ruta_archivo = scaler_path
            existing.features_entrenadas = ",".join(features_disp)
            existing.n_samples_entrenamiento = len(df_train)
            existing.fecha_entrenamiento = datetime.now(timezone.utc)
            scaler_id = existing.id
        else:
            reg = ScalerRegistry(
                nombre=scaler_filename,
                ruta_archivo=scaler_path,
                deporte=deporte,
                features_entrenadas=",".join(features_disp),
                n_samples_entrenamiento=len(df_train),
                fecha_entrenamiento=datetime.now(timezone.utc),
                activo=True,
            )
            session.add(reg)
            session.flush()
            scaler_id = reg.id
        session.commit()

    df_raw_copy = df_raw.copy()
    df_raw_copy[features_disp] = df_scaled

    with Session(engine) as session:
        inserted = 0
        for _, row in df_raw_copy.iterrows():
            existing = session.query(InferenceReadyPlayerData).filter_by(
                raw_data_id=int(row['id'])
            ).first()
            if existing:
                continue

            ready = InferenceReadyPlayerData(
                player_name=row['player_name'],
                team_name=row['team_name'],
                deporte=deporte,
                playing_time_min_scaled=row.get(features_disp[0]) if len(features_disp) > 0 else None,
                total_shots_scaled=row.get(features_disp[1]) if len(features_disp) > 1 else None,
                standard_sot_scaled=row.get(features_disp[2]) if len(features_disp) > 2 else None,
                performance_gls=row.get('performance_gls'),
                raw_data_id=int(row['id']),
                scaler_id=scaler_id,
                jugador_fk=int(row['jugador_fk']) if pd.notna(row.get('jugador_fk')) else None,
                equipo_fk=int(row['equipo_fk']) if pd.notna(row.get('equipo_fk')) else None,
            )
            session.add(ready)
            inserted += 1

        session.commit()

    logger.info(f"[FASE 7] {inserted} registros normalizados.")


# ──────────────────────────────────────────────────────────────────────────────
# FASE 8: DESCARGAR LOGOS DE LIGAS
# ──────────────────────────────────────────────────────────────────────────────

def fase8_logos_ligas():
    """Descarga logos de ligas y guarda rutas en archivo de configuracion."""
    logger.info("[FASE 8] Descargando logos de ligas...")

    logos_guardados = {}
    for liga_name, url in LEAGUE_LOGOS.items():
        nombre_archivo = f"liga_{liga_name.lower().replace(' ', '_')}.png"
        ruta = descargar_logo(url, nombre_archivo)
        if ruta:
            logos_guardados[liga_name] = ruta
            logger.info(f"  Logo {liga_name}: {ruta}")

    config_path = LOGOS_DIR / "league_logos.json"
    with open(config_path, "w") as f:
        json.dump(logos_guardados, f, indent=2)

    logger.info(f"[FASE 8] {len(logos_guardados)} logos de ligas guardados.")


# ──────────────────────────────────────────────────────────────────────────────
# ORQUESTADOR PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Re-poblador de BD v3.0 — It's Coming")
    parser.add_argument('--deporte', choices=['futbol', 'nba', 'mlb'], default='futbol')
    parser.add_argument('--liga', nargs='+', default=None, help="Ligas a procesar (ej: PL SP1 D1)")
    parser.add_argument('--temporadas', nargs='+', default=None, help="Temporadas (ej: 2324 2425 2526)")
    parser.add_argument('--ventana', type=int, default=5, help="Ventana rolling stats")
    parser.add_argument('--todo', action='store_true', help="Ejecutar todas las fases")
    parser.add_argument('--fase', type=int, choices=range(0, 9), help="Ejecutar una fase especifica (0-8)")
    parser.add_argument('--solo-logos', action='store_true', help="Solo descargar logos")
    parser.add_argument('--reset-db', action='store_true', help="Reset destructivo de la BD")

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info(" REPLOBLAR BD v3.0 — It's Coming")
    logger.info("=" * 60)

    if args.reset_db:
        fase0_reset_db()

    Base.metadata.create_all(bind=engine)

    if args.solo_logos:
        fase1_bootstrap_equipos()
        fase8_logos_ligas()
        return

    if args.todo or args.fase == 0:
        if args.reset_db:
            fase0_reset_db()

    if args.todo or args.fase == 1:
        fase1_bootstrap_equipos()

    if args.todo or args.fase == 2:
        fase2_historico_futbol(ligas=args.liga, temporadas=args.temporadas)

    if args.todo or args.fase == 3:
        fase3_resolver_fks()

    if args.todo or args.fase == 4:
        fase4_feature_engineering(ventana=args.ventana)

    if args.todo or args.fase == 5:
        fase5_team_rolling_stats(ventana=args.ventana, deporte=args.deporte)

    if args.todo or args.fase == 6:
        fase6_promedios_ui()

    if args.todo or args.fase == 7:
        fase7_entrenar_scaler(deporte=args.deporte)

    if args.todo or args.fase == 8:
        fase8_logos_ligas()

    logger.info("=" * 60)
    logger.info(" PROCESO COMPLETADO")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
