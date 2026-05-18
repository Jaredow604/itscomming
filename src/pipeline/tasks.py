import logging
import pandas as pd
from typing import List, Optional
from sqlalchemy.orm import Session

# Importamos nuestros módulos de pipeline
from src.pipeline.normalizer import SportsDataNormalizer
from src.pipeline.validator import PipelineValidator

logger = logging.getLogger(__name__)

class PipelineOrchestrator:
    """
    Orquestador del pipeline de datos.
    Se puede integrar fácilmente como un servicio, comando de Django (management command) o Celery task.
    Coordina la extracción, validación, normalización y carga de datos.
    """
    def __init__(self, scaler_name: str = 'sports_scaler'):
        self.normalizer = SportsDataNormalizer()
        self.validator = PipelineValidator(drift_threshold=2.5) # Umbral de drift permisivo para deportes
        self.scaler_name = scaler_name

    def process_historical_batch(self, df_raw: pd.DataFrame, features: List[str]) -> pd.DataFrame:
        """
        Procesa el lote histórico:
        1. Limpia y valida (nulls, outliers severos).
        2. Guarda estadísticas históricas para futuro Data Drift.
        3. Entrena y guarda el escalador RobustScaler.
        4. Retorna el DataFrame normalizado listo para entrenar PyTorch.
        """
        logger.info("--- INICIANDO PROCESAMIENTO DE LOTE HISTÓRICO ---")
        
        # 1. Validación Básica
        df_clean = self.validator.check_nulls(df_raw, features)
        self.validator.detect_outliers_iqr(df_clean, features)
        
        # 2. Ajustar estadísticas para Data Drift futuro
        self.validator.fit_historical_stats(df_clean, features)
        
        # 3. Normalizar y guardar escalador
        df_normalized = self.normalizer.fit_and_save(df_clean, features, self.scaler_name)
        
        logger.info("--- PROCESAMIENTO HISTÓRICO COMPLETADO ---")
        return df_normalized

    def process_realtime_inference(self, df_raw: pd.DataFrame, features: List[str]) -> pd.DataFrame:
        """
        Procesa nuevos datos (scrapeados o vía API) para inferencia:
        1. Verifica integridad (nulls) y Data Drift (emite warnings si hay desvío).
        2. Carga el escalador pre-entrenado y transforma los datos.
        3. Retorna el DataFrame listo para inyectar en los tensores de PyTorch.
        """
        logger.info("--- INICIANDO PROCESAMIENTO PARA INFERENCIA ---")
        
        # 1. Validaciones
        df_clean = self.validator.validate_pipeline(df_raw, features)
        
        # 2. Cargar escalador y normalizar
        df_inference_ready = self.normalizer.load_and_transform(df_clean, features, self.scaler_name)
        
        logger.info("--- DATOS LISTOS PARA INFERENCIA ---")
        return df_inference_ready

# ==========================================
# EJEMPLO DE INTEGRACIÓN CON DJANGO ORM / SQLALCHEMY
# ==========================================
def example_django_integration_task(session: Session):
    """
    Ejemplo de cómo llamar a este pipeline desde un contexto de Django/SQLAlchemy.
    Supongamos que leemos datos de RawPlayerData y escribimos en InferenceReadyPlayerData.
    """
    from src.data.models import RawPlayerData, InferenceReadyPlayerData
    
    # 1. Extraer Raw Data
    raw_query = session.query(RawPlayerData).all()
    if not raw_query:
        logger.warning("No hay datos crudos para procesar.")
        return
        
    # Convertir a DataFrame
    data = [{
        'id': r.id,
        'playing_time_min': float(r.playing_time_min) if r.playing_time_min else 0.0,
        'total_shots': float(r.total_shots) if r.total_shots else 0.0,
        'standard_sot': float(r.standard_sot) if r.standard_sot else 0.0
    } for r in raw_query]
    
    df_raw = pd.DataFrame(data)
    features = ['playing_time_min', 'total_shots', 'standard_sot']
    
    # 2. Instanciar Orquestador
    orchestrator = PipelineOrchestrator(scaler_name='player_stats_scaler')
    
    # Aquí podríamos determinar si es primer run o no. Asumimos que es inferencia.
    try:
        df_ready = orchestrator.process_realtime_inference(df_raw, features)
    except FileNotFoundError:
        # Si no hay escalador, lo creamos con el histórico
        df_ready = orchestrator.process_historical_batch(df_raw, features)
    
    # 3. Guardar en Base de Datos listos para Inferencia
    # (En la vida real se puede hacer un bulk_insert)
    for idx, row in df_ready.iterrows():
        new_inference_record = InferenceReadyPlayerData(
            raw_data_id=int(row['id']),
            playing_time_min_scaled=row['playing_time_min'],
            total_shots_scaled=row['total_shots'],
            standard_sot_scaled=row['standard_sot']
        )
        session.add(new_inference_record)
        
    session.commit()
    logger.info("Datos procesados y guardados en InferenceReadyPlayerData exitosamente.")
