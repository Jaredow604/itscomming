"""
poblar_bd_normalizada.py — Script Maestro de Población de BD v2.0

Ejecuta las fases de población en orden correcto:
    1. Equipos (desde API-Football + football-data.org)
    2. Histórico de partidos (desde football-data.co.uk CSVs)
    3. Feature Engineering con shift(1) — SIN data leakage
    4. Entrenamiento y guardado del RobustScaler
    5. Generación de InferenceReadyPlayerData normalizado

USO:
    python poblar_bd_normalizada.py --deporte futbol --liga PL --temporada 2526
    python poblar_bd_normalizada.py --deporte nba --fecha 15/05/2025
    python poblar_bd_normalizada.py --todo
"""

import os
import sys
import logging
import argparse
from datetime import datetime

import pandas as pd
import numpy as np
import joblib
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sklearn.preprocessing import RobustScaler

# Ajustar sys.path para imports del proyecto
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.data.models import (
    Base, Team, Player, Match, AliasEquipo,
    MatchStatsFutbol, MatchStatsNBA, MatchStatsMLB,
    LeagueTable, TeamRollingStats, DailySchedule,
    ScalerRegistry, RawPlayerData, InferenceReadyPlayerData,
    MatchHistoryStats, MLMatchFeatures
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("Poblador_v2")

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ──────────────────────────────────────────────────────────────────────────────

DB_URL = os.getenv("DB_URL", "postgresql+psycopg2://postgres:Jk9oe@localhost:5432/itscoming_db")
SCALER_DIR = os.path.abspath("src/pipeline/scalers")
os.makedirs(SCALER_DIR, exist_ok=True)

# Ligas disponibles en football-data.co.uk
LIGAS_CSV = {
    "PL":  ("https://www.football-data.co.uk/mmz4281/2526/E0.csv", "Premier League"),
    "SP1": ("https://www.football-data.co.uk/mmz4281/2526/SP1.csv", "La Liga"),
    "D1":  ("https://www.football-data.co.uk/mmz4281/2526/D1.csv", "Bundesliga"),
    "I1":  ("https://www.football-data.co.uk/mmz4281/2526/I1.csv", "Serie A"),
    "F1":  ("https://www.football-data.co.uk/mmz4281/2526/F1.csv", "Ligue 1"),
}

# Features a normalizar para el modelo de jugadores
FEATURES_FUTBOL_JUGADOR = ['playing_time_min', 'total_shots', 'standard_sot', 'xg']
FEATURES_NBA_JUGADOR    = ['pts', 'reb', 'ast', 'fg3m', 'stl', 'blk']


# ──────────────────────────────────────────────────────────────────────────────
# FASE 1: CREAR/ACTUALIZAR EQUIPOS
# ──────────────────────────────────────────────────────────────────────────────

def fase1_poblar_equipos_desde_csv(engine, liga_key: str = "PL"):
    """
    Extrae equipos únicos del CSV histórico y los inserta en la tabla 'equipos'.
    Usa UPSERT para no crear duplicados en ejecuciones repetidas.
    """
    url_csv, nombre_liga = LIGAS_CSV[liga_key]
    logger.info(f"[FASE 1] Descargando equipos de {nombre_liga} desde {url_csv}")

    df = pd.read_csv(url_csv)
    equipos_unicos = sorted(
        set(df['HomeTeam'].dropna().unique()) | set(df['AwayTeam'].dropna().unique())
    )
    logger.info(f"[FASE 1] {len(equipos_unicos)} equipos únicos encontrados.")

    with Session(engine) as session:
        counter = 0
        for nombre in equipos_unicos:
            # Buscamos si ya existe por nombre
            existing = session.query(Team).filter(Team.nombre == nombre).first()
            if existing:
                if existing.liga is None:
                    existing.liga = nombre_liga
                    session.add(existing)
            else:
                # Generamos un ID autoincremental seguro para equipos sin ID de API
                max_id_result = session.execute(
                    text("SELECT COALESCE(MAX(id_equipo), 90000) + 1 FROM equipos")
                ).scalar()
                new_team = Team(
                    id_equipo=max_id_result,
                    nombre=nombre,
                    liga=nombre_liga
                )
                session.add(new_team)
                # Agregar alias inmediatamente
                alias = AliasEquipo(
                    nombre_fuente=nombre.lower().strip(),
                    id_equipo=max_id_result
                )
                session.add(alias)
                counter += 1

        session.commit()
    logger.info(f"[FASE 1] ✅ {counter} equipos nuevos insertados para {nombre_liga}.")


# ──────────────────────────────────────────────────────────────────────────────
# FASE 2: POBLAR HISTORIAL DE PARTIDOS
# ──────────────────────────────────────────────────────────────────────────────

def fase2_poblar_historial_futbol(engine, liga_key: str = "PL"):
    """
    Descarga el CSV histórico de la liga y lo inserta en match_history_stats.
    SOLO inserta resultados crudos — las columnas de forma (form_*) se calculan
    en la Fase 3 con shift(1).
    """
    url_csv, nombre_liga = LIGAS_CSV[liga_key]
    logger.info(f"[FASE 2] Descargando historial de partidos: {nombre_liga}")

    df = pd.read_csv(url_csv)
    logger.info(f"[FASE 2] {len(df)} partidos descargados del CSV.")

    # Mapeo estándar de columnas football-data.co.uk
    col_map = {
        'Date': 'date', 'HomeTeam': 'home_team', 'AwayTeam': 'away_team',
        'FTHG': 'home_score', 'FTAG': 'away_score'
    }
    df = df.rename(columns=col_map)

    # xG opcional (no todos los CSVs lo tienen)
    if 'AvgH' in df.columns:
        pass  # Odds presentes, no xG
    df['home_xg'] = pd.to_numeric(df.get('home_xg', np.nan), errors='coerce')
    df['away_xg'] = pd.to_numeric(df.get('away_xg', np.nan), errors='coerce')

    # Parsear fecha
    df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['date', 'home_team', 'away_team'])
    df['home_score'] = pd.to_numeric(df['home_score'], errors='coerce')
    df['away_score'] = pd.to_numeric(df['away_score'], errors='coerce')

    insertados = 0
    omitidos = 0

    with Session(engine) as session:
        for _, row in df.iterrows():
            # Verificar si ya existe (por uniqueconstraint)
            existing = session.query(MatchHistoryStats).filter_by(
                home_team=row['home_team'],
                away_team=row['away_team'],
                date=row['date']
            ).first()

            if existing:
                omitidos += 1
                continue

            record = MatchHistoryStats(
                league=nombre_liga,
                season="2025-26",
                date=row['date'],
                home_team=row['home_team'],
                away_team=row['away_team'],
                home_score=int(row['home_score']) if pd.notna(row['home_score']) else None,
                away_score=int(row['away_score']) if pd.notna(row['away_score']) else None,
                home_xg=float(row['home_xg']) if pd.notna(row.get('home_xg')) else None,
                away_xg=float(row['away_xg']) if pd.notna(row.get('away_xg')) else None,
            )
            session.add(record)
            insertados += 1

        session.commit()

    logger.info(f"[FASE 2] ✅ {insertados} partidos insertados, {omitidos} omitidos (ya existían).")


# ──────────────────────────────────────────────────────────────────────────────
# FASE 3: FEATURE ENGINEERING SIN DATA LEAKAGE
# ──────────────────────────────────────────────────────────────────────────────

def fase3_feature_engineering_sin_leakage(engine, liga: str = None, ventana: int = 5):
    """
    *** FASE CRÍTICA ANTI-DATA LEAKAGE ***

    Calcula promedios móviles usando shift(1) para garantizar que cada partido
    solo use información de partidos ANTERIORES. Nunca usa el partido actual
    ni futuros.

    shift(1).rolling(ventana) = "los últimos N partidos ANTES de este"

    Guarda el resultado en:
        - match_history_stats (columnas form_*)
        - ml_match_features (tabla de features final para entrenamiento)
        - team_rolling_stats (lookup por equipo+fecha para inferencia)
    """
    logger.info(f"[FASE 3] Calculando features con ventana={ventana}, shift(1) — SIN data leakage")

    with engine.connect() as conn:
        query = "SELECT * FROM match_history_stats WHERE home_score IS NOT NULL AND away_score IS NOT NULL"
        if liga:
            query += f" AND league = '{liga}'"
        df = pd.read_sql(query, conn)

    if df.empty:
        logger.warning("[FASE 3] No hay datos en match_history_stats. Ejecuta Fase 2 primero.")
        return

    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    # Detectar si hay xG disponible
    has_xg = (
        'home_xg' in df.columns and 'away_xg' in df.columns and
        df['home_xg'].notna().any()
    )
    logger.info(f"[FASE 3] xG disponible: {has_xg}")

    # ── Construir Ledger (perspectiva de cada equipo) ──
    if has_xg:
        home_ledger = df[['date', 'home_team', 'home_score', 'away_score', 'home_xg', 'away_xg']].copy()
        home_ledger.columns = ['date', 'team', 'gf', 'ga', 'xgf', 'xga']
        away_ledger = df[['date', 'away_team', 'away_score', 'home_score', 'away_xg', 'home_xg']].copy()
        away_ledger.columns = ['date', 'team', 'gf', 'ga', 'xgf', 'xga']
        metric_cols = ['gf', 'ga', 'xgf', 'xga']
        form_cols   = ['form_gf', 'form_ga', 'form_xgf', 'form_xga']
    else:
        home_ledger = df[['date', 'home_team', 'home_score', 'away_score']].copy()
        home_ledger.columns = ['date', 'team', 'gf', 'ga']
        away_ledger = df[['date', 'away_team', 'away_score', 'home_score']].copy()
        away_ledger.columns = ['date', 'team', 'gf', 'ga']
        metric_cols = ['gf', 'ga']
        form_cols   = ['form_gf', 'form_ga']

    ledger = (
        pd.concat([home_ledger, away_ledger])
        .sort_values(['team', 'date'])
        .reset_index(drop=True)
    )

    # ── shift(1) + rolling(ventana) — CLAVE ANTI-LEAKAGE ──
    form_values = ledger.groupby('team')[metric_cols].transform(
        lambda x: x.shift(1).rolling(ventana, min_periods=ventana).mean()
    )
    for i, col in enumerate(form_cols):
        ledger[col] = form_values.iloc[:, i]

    ledger_final = ledger[['date', 'team'] + form_cols]

    # ── Merge de vuelta al DataFrame principal ──
    df = pd.merge(df, ledger_final, left_on=['date', 'home_team'],
                  right_on=['date', 'team'], how='left').drop('team', axis=1)
    rename_home = {c: f'home_{c}' for c in form_cols}
    df = df.rename(columns=rename_home)

    df = pd.merge(df, ledger_final, left_on=['date', 'away_team'],
                  right_on=['date', 'team'], how='left').drop('team', axis=1)
    rename_away = {c: f'away_{c}' for c in form_cols}
    df = df.rename(columns=rename_away)

    # ── Calcular targets ──
    df['total_goals'] = df['home_score'] + df['away_score']
    def calc_result(row):
        if row['home_score'] > row['away_score']:   return 1
        elif row['home_score'] == row['away_score']: return 0
        else:                                        return 2
    df['result'] = df.apply(calc_result, axis=1)

    # ── Limpiar filas con NaN en features de forma (spin-up histórico) ──
    form_home_cols = [f'home_{c}' for c in form_cols]
    form_away_cols = [f'away_{c}' for c in form_cols]
    df_clean = df.dropna(subset=form_home_cols + form_away_cols).reset_index(drop=True)

    logger.info(f"[FASE 3] {len(df_clean)}/{len(df)} partidos con historial suficiente (≥{ventana} partidos previos).")

    # ── Guardar en ml_match_features ──
    with Session(engine) as session:
        # Limpiar tabla y repoblar
        session.execute(text("DELETE FROM ml_match_features WHERE 1=1"))
        for _, row in df_clean.iterrows():
            feat = MLMatchFeatures(
                league=row.get('league'),
                season=row.get('season'),
                date=row['date'],
                home_team=row['home_team'],
                away_team=row['away_team'],
                home_score=int(row['home_score']) if pd.notna(row.get('home_score')) else None,
                away_score=int(row['away_score']) if pd.notna(row.get('away_score')) else None,
                home_form_gf=row.get('home_form_gf'),
                home_form_ga=row.get('home_form_ga'),
                away_form_gf=row.get('away_form_gf'),
                away_form_ga=row.get('away_form_ga'),
                home_form_xgf=row.get('home_form_xgf') if has_xg else None,
                home_form_xga=row.get('home_form_xga') if has_xg else None,
                away_form_xgf=row.get('away_form_xgf') if has_xg else None,
                away_form_xga=row.get('away_form_xga') if has_xg else None,
                total_goals=int(row['total_goals']),
                result=int(row['result']),
            )
            session.add(feat)
        session.commit()

    logger.info(f"[FASE 3] ✅ {len(df_clean)} registros guardados en ml_match_features.")

    # ── Actualizar columnas form_* en match_history_stats ──
    with Session(engine) as session:
        for _, row in df.iterrows():
            existing = session.query(MatchHistoryStats).filter_by(
                home_team=row['home_team'],
                away_team=row['away_team'],
                date=row['date']
            ).first()
            if existing:
                existing.home_form_gf = row.get('home_form_gf')
                existing.home_form_ga = row.get('home_form_ga')
                existing.away_form_gf = row.get('away_form_gf')
                existing.away_form_ga = row.get('away_form_ga')
                existing.total_goals = int(row['total_goals']) if pd.notna(row.get('total_goals')) else None
                existing.result = int(row['result']) if pd.notna(row.get('result')) else None
                session.add(existing)
        session.commit()

    logger.info("[FASE 3] ✅ match_history_stats actualizado con columnas form_*.")
    return df_clean


# ──────────────────────────────────────────────────────────────────────────────
# FASE 4: POBLAR TeamRollingStats POR EQUIPO (para inferencia en tiempo real)
# ──────────────────────────────────────────────────────────────────────────────

def fase4_calcular_team_rolling_stats(engine, ventana: int = 5, deporte: str = 'futbol'):
    """
    Para cada equipo y cada partido jugado, calcula y almacena en TeamRollingStats
    los promedios móviles (shift=1) que corresponden a ESA fecha.
    Esto permite que en inferencia se haga un simple SELECT por equipo+fecha,
    sin recalcular rolling en tiempo real.
    """
    logger.info(f"[FASE 4] Calculando TeamRollingStats para deporte={deporte}, ventana={ventana}")

    with engine.connect() as conn:
        query = """
            SELECT mh.id, mh.date, mh.home_team, mh.away_team,
                   mh.home_score, mh.away_score, mh.home_xg, mh.away_xg,
                   mh.local_fk, mh.visitante_fk
            FROM match_history_stats mh
            WHERE mh.home_score IS NOT NULL
            ORDER BY mh.date
        """
        df = pd.read_sql(query, conn)

    if df.empty:
        logger.warning("[FASE 4] Sin datos en match_history_stats.")
        return

    df['date'] = pd.to_datetime(df['date'])

    # Ledger por equipo
    home_l = df[['date', 'home_team', 'home_score', 'away_score', 'home_xg', 'away_xg', 'local_fk']].copy()
    home_l.columns = ['date', 'team', 'gf', 'ga', 'xgf', 'xga', 'equipo_id']
    away_l = df[['date', 'away_team', 'away_score', 'home_score', 'away_xg', 'home_xg', 'visitante_fk']].copy()
    away_l.columns = ['date', 'team', 'gf', 'ga', 'xgf', 'xga', 'equipo_id']

    ledger = pd.concat([home_l, away_l]).sort_values(['team', 'date']).reset_index(drop=True)

    for col in ['gf', 'ga', 'xgf', 'xga']:
        ledger[col] = pd.to_numeric(ledger[col], errors='coerce')

    # Calcular rolling con shift(1)
    for col in ['gf', 'ga', 'xgf', 'xga']:
        ledger[f'rolling_{col}'] = ledger.groupby('team')[col].transform(
            lambda x: x.shift(1).rolling(ventana, min_periods=1).mean()
        )

    with Session(engine) as session:
        inserted = 0
        for _, row in ledger.iterrows():
            equipo_id = int(row['equipo_id']) if pd.notna(row.get('equipo_id')) else None
            if equipo_id is None:
                continue

            # UPSERT via merge
            existing = session.query(TeamRollingStats).filter_by(
                id_equipo=equipo_id,
                fecha_calculo=row['date'],
                ventana=ventana,
                deporte=deporte
            ).first()

            if existing:
                existing.prom_goles_favor = row.get('rolling_gf')
                existing.prom_goles_contra = row.get('rolling_ga')
                existing.prom_xg_favor = row.get('rolling_xgf')
                existing.prom_xg_contra = row.get('rolling_xga')
                session.add(existing)
            else:
                rs = TeamRollingStats(
                    id_equipo=equipo_id,
                    fecha_calculo=row['date'],
                    ventana=ventana,
                    deporte=deporte,
                    prom_goles_favor=row.get('rolling_gf'),
                    prom_goles_contra=row.get('rolling_ga'),
                    prom_xg_favor=row.get('rolling_xgf'),
                    prom_xg_contra=row.get('rolling_xga'),
                )
                session.add(rs)
                inserted += 1

        session.commit()

    logger.info(f"[FASE 4] ✅ {inserted} registros en team_rolling_stats.")


# ──────────────────────────────────────────────────────────────────────────────
# FASE 5: ENTRENAR ESCALADOR Y NORMALIZAR (SIN LEAKAGE)
# ──────────────────────────────────────────────────────────────────────────────

def fase5_entrenar_scaler_y_normalizar(engine, deporte: str = 'futbol'):
    """
    Entrena el RobustScaler SOLO con datos históricos (no con datos de partidos
    del futuro o del periodo de evaluación).

    Flujo correcto:
        1. Lee ml_raw_player_data (datos crudos ya insertados)
        2. Entrena RobustScaler
        3. Guarda el scaler en disco y registra en scaler_registry
        4. Transforma los datos y los guarda en ml_inference_ready_player_data

    NUNCA usa transform() con datos que estuvieron en fit() — si es para
    evaluación, usa solo el scaler entrenado con datos históricos pasados.
    """
    logger.info(f"[FASE 5] Entrenando RobustScaler para deporte={deporte}")

    with engine.connect() as conn:
        df_raw = pd.read_sql(
            f"SELECT * FROM ml_raw_player_data WHERE deporte = '{deporte}'",
            conn
        )

    if df_raw.empty:
        logger.warning(f"[FASE 5] No hay datos crudos para deporte={deporte}. Carga datos primero.")
        return

    features = FEATURES_FUTBOL_JUGADOR if deporte == 'futbol' else FEATURES_NBA_JUGADOR

    # Filtrar columnas disponibles
    features_disponibles = [f for f in features if f in df_raw.columns]
    if not features_disponibles:
        logger.error(f"[FASE 5] Ninguna feature disponible. Features esperadas: {features}")
        return

    # Rellenar nulos con mediana (más robusto que 0 para RobustScaler)
    df_train = df_raw[features_disponibles].copy()
    df_train = df_train.fillna(df_train.median())

    # Entrenar escalador
    scaler = RobustScaler()
    df_scaled = scaler.fit_transform(df_train)

    # Guardar scaler en disco
    scaler_filename = f"player_stats_{deporte}_v2.joblib"
    scaler_path = os.path.join(SCALER_DIR, scaler_filename)
    joblib.dump(scaler, scaler_path)
    logger.info(f"[FASE 5] Scaler guardado en {scaler_path}")

    # Registrar en scaler_registry
    with Session(engine) as session:
        existing_reg = session.query(ScalerRegistry).filter_by(nombre=scaler_filename).first()
        if existing_reg:
            existing_reg.ruta_archivo = scaler_path
            existing_reg.features_entrenadas = ",".join(features_disponibles)
            existing_reg.n_samples_entrenamiento = len(df_train)
            existing_reg.fecha_entrenamiento = datetime.utcnow()
            session.add(existing_reg)
            scaler_id = existing_reg.id
        else:
            reg = ScalerRegistry(
                nombre=scaler_filename,
                ruta_archivo=scaler_path,
                deporte=deporte,
                features_entrenadas=",".join(features_disponibles),
                n_samples_entrenamiento=len(df_train),
                fecha_entrenamiento=datetime.utcnow(),
                activo=True
            )
            session.add(reg)
            session.flush()
            scaler_id = reg.id
        session.commit()

    # Generar InferenceReadyPlayerData
    df_raw_copy = df_raw.copy()
    df_raw_copy[features_disponibles] = df_scaled

    with Session(engine) as session:
        inserted = 0
        for idx, row in df_raw_copy.iterrows():
            # Evitar duplicados por raw_data_id
            existing = session.query(InferenceReadyPlayerData).filter_by(
                raw_data_id=int(row['id'])
            ).first()
            if existing:
                continue

            ready = InferenceReadyPlayerData(
                player_name=row['player_name'],
                team_name=row['team_name'],
                deporte=deporte,
                playing_time_min_scaled=row.get('playing_time_min'),
                total_shots_scaled=row.get('total_shots'),
                standard_sot_scaled=row.get('standard_sot'),
                xg_scaled=row.get('xg'),
                pts_scaled=row.get('pts'),
                reb_scaled=row.get('reb'),
                ast_scaled=row.get('ast'),
                performance_gls=row.get('performance_gls'),
                raw_data_id=int(row['id']),
                scaler_id=scaler_id,
                jugador_fk=int(row['jugador_fk']) if pd.notna(row.get('jugador_fk')) else None,
                equipo_fk=int(row['equipo_fk']) if pd.notna(row.get('equipo_fk')) else None,
            )
            session.add(ready)
            inserted += 1

        session.commit()

    logger.info(f"[FASE 5] ✅ {inserted} registros normalizados en ml_inference_ready_player_data.")


# ──────────────────────────────────────────────────────────────────────────────
# FASE 6: POBLAR ESTADÍSTICAS DE EQUIPOS (PROMEDIOS POR TEMPORADA)
# ──────────────────────────────────────────────────────────────────────────────

def fase6_actualizar_promedios_equipos(engine, liga_key: str = "PL"):
    """
    Calcula promedios de goles, corners y tiros para la UI del dashboard.
    IMPORTANTE: Estos promedios son solo para visualización, NO para el modelo ML.
    Los promedios del modelo viven en TeamRollingStats con shift(1).
    """
    url_csv, nombre_liga = LIGAS_CSV[liga_key]
    logger.info(f"[FASE 6] Calculando promedios de UI para {nombre_liga}")

    df = pd.read_csv(url_csv)

    # Columnas opcionales
    for col in ['HC', 'AC', 'HST', 'AST']:
        if col not in df.columns:
            df[col] = 0

    equipos_unicos = sorted(
        set(df['HomeTeam'].dropna().unique()) | set(df['AwayTeam'].dropna().unique())
    )

    stats = []
    for nombre in equipos_unicos:
        df_h = df[df['HomeTeam'] == nombre]
        df_a = df[df['AwayTeam'] == nombre]
        total = len(df_h) + len(df_a)
        if total == 0:
            continue

        prom_goles  = (df_h['FTHG'].sum() + df_a['FTAG'].sum()) / total
        prom_corners = (df_h['HC'].sum() + df_a['AC'].sum()) / total
        prom_tiros  = (df_h['HST'].sum() + df_a['AST'].sum()) / total
        stats.append((nombre, round(prom_goles, 2), round(prom_corners, 2), round(prom_tiros, 2)))

    # NOTE: Aquí actualizamos el modelo Django Equipos via SQL directo
    # para no mezclar los dos ORM. Django sync.
    with engine.connect() as conn:
        updated = 0
        for nombre, pg, pc, pt in stats:
            result = conn.execute(
                text("""
                    UPDATE equipos SET
                        prom_goles = :pg,
                        prom_corners = :pc,
                        prom_tiros_puerta = :pt
                    WHERE nombre = :nombre
                """),
                {"pg": pg, "pc": pc, "pt": pt, "nombre": nombre}
            )
            if result.rowcount > 0:
                updated += 1
        conn.commit()

    logger.info(f"[FASE 6] ✅ {updated} equipos actualizados con promedios de UI.")


# ──────────────────────────────────────────────────────────────────────────────
# ORQUESTADOR PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Poblador de BD Normalizada v2.0 — ItsComming")
    parser.add_argument('--deporte', choices=['futbol', 'nba', 'mlb'], default='futbol')
    parser.add_argument('--liga', choices=list(LIGAS_CSV.keys()), default='PL')
    parser.add_argument('--ventana', type=int, default=5, help="Ventana de partidos para rolling stats")
    parser.add_argument('--todo', action='store_true', help="Ejecutar todas las fases")
    parser.add_argument('--fase', type=int, choices=[1,2,3,4,5,6], help="Ejecutar una fase específica")
    args = parser.parse_args()

    engine = create_engine(DB_URL)

    # Crear todas las tablas si no existen
    logger.info("Verificando y creando esquema de BD...")
    Base.metadata.create_all(bind=engine)
    logger.info("Esquema verificado.")

    if args.todo or args.fase == 1:
        fase1_poblar_equipos_desde_csv(engine, args.liga)
    if args.todo or args.fase == 2:
        fase2_poblar_historial_futbol(engine, args.liga)
    if args.todo or args.fase == 3:
        fase3_feature_engineering_sin_leakage(engine, ventana=args.ventana)
    if args.todo or args.fase == 4:
        fase4_calcular_team_rolling_stats(engine, ventana=args.ventana, deporte=args.deporte)
    if args.todo or args.fase == 5:
        fase5_entrenar_scaler_y_normalizar(engine, deporte=args.deporte)
    if args.todo or args.fase == 6:
        fase6_actualizar_promedios_equipos(engine, args.liga)

    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("Proceso de población completado exitosamente.")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


if __name__ == "__main__":
    main()
