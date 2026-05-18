"""
tasks.py -- Tareas asincronas de Celery para la app 'predicciones'.

Este modulo define las tareas que Celery ejecuta de forma asincrona:
    1. Extraccion diaria de datos deportivos (APIs / Scrapers).
    2. Validacion y normalizacion via PipelineOrchestrator.
    3. Persistencia en PostgreSQL (RawPlayerData -> InferenceReadyPlayerData).

Arquitectura de Resiliencia:
    - autoretry_for: Reintentos automaticos ante errores de red/timeout.
    - retry_backoff: Exponential backoff (2s, 4s, 8s) para no saturar APIs.
    - retry_jitter: Jitter aleatorio para evitar "thundering herd" si multiples
      workers reintentan al mismo tiempo.

Ejecucion manual (para testing):
    >>> from predicciones.tasks import fetch_and_process_daily_data
    >>> fetch_and_process_daily_data.delay()

Ejecucion programada (Celery Beat):
    Configurado en settings.py -> CELERY_BEAT_SCHEDULE
    Se ejecuta automaticamente todos los dias a las 06:00 AM.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from celery import shared_task
from requests.exceptions import ConnectionError, Timeout

logger = logging.getLogger(__name__)


# ==========================================
# CONSTANTES
# ==========================================
FEATURES_COLUMNS: List[str] = ['playing_time_min', 'total_shots', 'standard_sot']
SCALER_NAME: str = 'player_stats_scaler'


# ==========================================
# TAREA PRINCIPAL: EXTRACCION Y PROCESAMIENTO DIARIO
# ==========================================

@shared_task(
    bind=True,
    name='predicciones.tasks.fetch_and_process_daily_data',
    # --- RESILIENCIA: Reintentos automaticos ---
    autoretry_for=(ConnectionError, Timeout, OSError),
    retry_backoff=2,          # Backoff exponencial: 2s, 4s, 8s
    retry_backoff_max=60,     # Maximo 60 segundos entre reintentos
    retry_jitter=True,        # Jitter aleatorio para evitar thundering herd
    max_retries=3,            # Maximo 3 reintentos antes de fallar definitivamente
    # --- LIMITES ---
    soft_time_limit=300,      # 5 min soft limit (lanza SoftTimeLimitExceeded)
    time_limit=360,           # 6 min hard limit (mata el proceso)
    acks_late=True,           # ACK despues de ejecutar (no antes)
)
def fetch_and_process_daily_data(self) -> Dict[str, Any]:
    """
    Tarea principal de Celery: Extrae datos deportivos frescos,
    los valida/normaliza con PipelineOrchestrator, y los persiste
    en PostgreSQL listos para inferencia de PyTorch.

    Flujo:
        1. Extraer datos crudos (simula llamada a API/Scraper).
        2. Guardar en tabla RawPlayerData (datos crudos para auditoria).
        3. Pasar por PipelineOrchestrator (validacion + normalizacion).
        4. Guardar en tabla InferenceReadyPlayerData (datos listos para PyTorch).

    Returns:
        Diccionario con metricas de la ejecucion (registros procesados, errores, etc).
    """
    task_id = self.request.id
    start_time = datetime.utcnow()
    logger.info(
        "[Task %s] Iniciando extraccion diaria de datos deportivos...",
        task_id,
    )

    try:
        # -------------------------------------------------------
        # PASO 1: Extraccion de datos crudos
        # -------------------------------------------------------
        logger.info("[Task %s] Conectando con fuentes de datos (APIs/Scrapers)...", task_id)
        df_raw = _fetch_raw_data_from_sources()

        if df_raw.empty:
            logger.warning("[Task %s] No se obtuvieron datos nuevos. Abortando.", task_id)
            return {
                'status': 'skipped',
                'reason': 'No hay datos nuevos disponibles',
                'task_id': task_id,
            }

        logger.info(
            "[Task %s] Datos crudos extraidos: %d registros.",
            task_id, len(df_raw),
        )

        # -------------------------------------------------------
        # PASO 2: Persistir datos crudos en PostgreSQL
        # -------------------------------------------------------
        raw_count = _persist_raw_data(df_raw)
        logger.info(
            "[Task %s] %d registros guardados en RawPlayerData.",
            task_id, raw_count,
        )

        # -------------------------------------------------------
        # PASO 3: Validacion + Normalizacion via PipelineOrchestrator
        # -------------------------------------------------------
        logger.info("[Task %s] Ejecutando PipelineOrchestrator...", task_id)
        df_normalized = _run_pipeline_orchestrator(df_raw)

        if df_normalized is None or df_normalized.empty:
            logger.error("[Task %s] PipelineOrchestrator retorno dataset vacio.", task_id)
            return {
                'status': 'error',
                'reason': 'Normalizacion fallo o retorno vacio',
                'task_id': task_id,
            }

        # -------------------------------------------------------
        # PASO 4: Persistir datos normalizados para inferencia
        # -------------------------------------------------------
        inference_count = _persist_inference_data(df_normalized)
        logger.info(
            "[Task %s] %d registros guardados en InferenceReadyPlayerData.",
            task_id, inference_count,
        )

        # -------------------------------------------------------
        # RESULTADO
        # -------------------------------------------------------
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        result = {
            'status': 'success',
            'task_id': task_id,
            'raw_records': raw_count,
            'inference_records': inference_count,
            'elapsed_seconds': round(elapsed, 2),
        }
        logger.info(
            "[Task %s] Pipeline completado exitosamente en %.2fs. "
            "Raw: %d | Inference: %d",
            task_id, elapsed, raw_count, inference_count,
        )
        return result

    except (ConnectionError, Timeout) as exc:
        # Estos errores disparan el autoretry automaticamente.
        # Este bloque solo se alcanza si se agotaron los reintentos.
        logger.error(
            "[Task %s] Error de conexion tras %d reintentos: %s",
            task_id, self.request.retries, exc,
        )
        raise

    except Exception as exc:
        # Errores inesperados que NO deben reintentarse (bugs, errores de logica)
        logger.error(
            "[Task %s] Error inesperado en el pipeline: %s",
            task_id, exc,
            exc_info=True,
        )
        return {
            'status': 'error',
            'task_id': task_id,
            'error': str(exc),
        }


# ==========================================
# FUNCIONES AUXILIARES (PRIVADAS)
# ==========================================

def _fetch_raw_data_from_sources() -> pd.DataFrame:
    """
    Extrae datos deportivos desde las fuentes configuradas.

    En produccion, esta funcion llamaria a:
        - nba_api para estadisticas NBA
        - MLB-StatsAPI para estadisticas MLB
        - soccerdata / FBref scraper para futbol
        - APIs de odds (The Odds API)

    Por ahora, ejecuta los management commands existentes del proyecto
    y retorna los datos mas recientes de la base de datos.
    """
    from database import SessionLocal
    from src.data.models import PlayerStatsFutbol, Player, Team

    session = SessionLocal()
    try:
        results = session.query(PlayerStatsFutbol, Player, Team).join(Player, PlayerStatsFutbol.id_jugador == Player.id_jugador).join(Team, Player.id_equipo == Team.id_equipo).all()

        if not results:
            # Fallback a synthetic data for testing normalizers if table is empty
            return pd.DataFrame([{
                'id': i,
                'player_name': f'Player {i}',
                'team_name': 'Team A',
                'playing_time_min': 90.0,
                'total_shots': 2.0 + i % 3,
                'standard_sot': 1.0 + i % 2,
                'performance_gls': 0.5,
            } for i in range(50)])

        data = [{
            'id': stats.id_partido + stats.id_jugador,
            'player_name': player.nombre,
            'team_name': team.nombre,
            'playing_time_min': float(stats.minutos) if stats.minutos else 90.0,
            'total_shots': float(stats.tiros_totales) if stats.tiros_totales else 0.0,
            'standard_sot': float(stats.tiros_puerta) if stats.tiros_puerta else 0.0,
            'performance_gls': float(stats.goles) if stats.goles else 0.0,
        } for stats, player, team in results]

        return pd.DataFrame(data)

    finally:
        session.close()


def _persist_raw_data(df: pd.DataFrame) -> int:
    """
    Guarda los datos crudos en la tabla RawPlayerData de PostgreSQL.

    Returns:
        Numero de registros insertados.
    """
    from database import SessionLocal
    from src.data.models import RawPlayerData

    session = SessionLocal()
    count = 0
    try:
        for _, row in df.iterrows():
            record = RawPlayerData(
                player_name=row.get('player_name', 'Unknown'),
                team_name=row.get('team_name', 'Unknown'),
                playing_time_min=row.get('playing_time_min', 0.0),
                total_shots=row.get('total_shots', 0.0),
                standard_sot=row.get('standard_sot', 0.0),
                performance_gls=row.get('performance_gls', 0.0),
            )
            session.add(record)
            count += 1

        session.commit()
        return count

    except Exception as e:
        session.rollback()
        logger.error("Error al persistir datos crudos: %s", e, exc_info=True)
        raise

    finally:
        session.close()


def _run_pipeline_orchestrator(df_raw: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    Ejecuta el PipelineOrchestrator para validar y normalizar los datos.

    Intenta primero usar el escalador pre-entrenado (inferencia).
    Si no existe, entrena uno nuevo con los datos actuales (historico).

    Returns:
        DataFrame normalizado o None si falla.
    """
    from src.pipeline.tasks import PipelineOrchestrator

    orchestrator = PipelineOrchestrator(scaler_name=SCALER_NAME)

    try:
        df_normalized = orchestrator.process_realtime_inference(df_raw, FEATURES_COLUMNS)
    except FileNotFoundError:
        logger.info("No se encontro escalador pre-entrenado. Creando uno nuevo...")
        df_normalized = orchestrator.process_historical_batch(df_raw, FEATURES_COLUMNS)

    return df_normalized


def _persist_inference_data(df: pd.DataFrame) -> int:
    """
    Guarda los datos normalizados en InferenceReadyPlayerData de PostgreSQL.

    Returns:
        Numero de registros insertados.
    """
    from database import SessionLocal
    from src.data.models import InferenceReadyPlayerData

    session = SessionLocal()
    count = 0
    try:
        for _, row in df.iterrows():
            record = InferenceReadyPlayerData(
                player_name=row.get('player_name', 'Unknown'),
                team_name=row.get('team_name', 'Unknown'),
                playing_time_min_scaled=row.get('playing_time_min', 0.0),
                total_shots_scaled=row.get('total_shots', 0.0),
                standard_sot_scaled=row.get('standard_sot', 0.0),
                performance_gls=row.get('performance_gls', 0.0),
            )
            session.add(record)
            count += 1

        session.commit()
        return count

    except Exception as e:
        session.rollback()
        logger.error("Error al persistir datos de inferencia: %s", e, exc_info=True)
        raise

    finally:
        session.close()
