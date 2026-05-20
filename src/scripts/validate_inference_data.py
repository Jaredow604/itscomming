import os
import sys
import pandas as pd
import numpy as np
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.data.models import InferenceReadyPlayerData
from database import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("InferenceValidator")

def validate_inference_data():
    """
    Script de validación rápida para asegurar que la tabla ml_inference_ready_player_data 
    está lista para inyección en tensores sin errores ni NaNs.
    """
    logger.info("Conectando a la base de datos PostgreSQL...")
    session = SessionLocal()
    
    try:
        # Extraer usando chunking simulado (limit para la auditoría)
        query = session.query(InferenceReadyPlayerData).limit(50000).statement
        df = pd.read_sql(query, session.bind)
        
        if df.empty:
            logger.error("❌ La tabla está vacía.")
            return

        logger.info(f"✅ Extraídos {len(df)} registros para validación.")
        
        # 1. Validación de Tipos de Datos (Deben ser numericos para float32)
        expected_features = ['playing_time_min_scaled', 'total_shots_scaled', 'standard_sot_scaled']
        for col in expected_features:
            if col not in df.columns:
                logger.error(f"❌ Columna faltante: {col}")
                continue
                
            # Checkear el tipo real
            if not pd.api.types.is_numeric_dtype(df[col]):
                logger.error(f"❌ Tipo inválido en {col}: {df[col].dtype} (Se requiere numérico/float)")
            else:
                logger.info(f"✅ Tipo correcto en {col} ({df[col].dtype})")
        
        # 2. Validación de NaNs y Nulls
        null_counts = df[expected_features].isnull().sum()
        total_nulls = null_counts.sum()
        if total_nulls > 0:
            logger.error(f"❌ Se detectaron {total_nulls} NaNs en las features:")
            for col, count in null_counts.items():
                if count > 0:
                    logger.error(f"   - {col}: {count} nulos")
            logger.warning("⚠️ Acción recomendada: Ejecutar la rutina de imputación a nivel SQL o Pandas.")
        else:
            logger.info("✅ No se detectaron NaNs en las features críticas.")
        
        # 3. Validación de Inferencia (Target Nulls)
        target = 'performance_gls'
        if target in df.columns:
            target_nulls = df[target].isnull().sum()
            if target_nulls > 0:
                logger.warning(f"⚠️ Hay {target_nulls} registros sin Target ('{target}'). "
                               "Si es para entrenamiento, deben excluirse. Si es inferencia, es normal.")
        
        # 4. Chequeo de Outliers de Escalado (RobustScaler debería estar centrado en 0)
        logger.info("Estadísticas de distribución (Comprobando escalado RobustScaler):")
        for col in expected_features:
            if col in df.columns:
                median = df[col].median()
                logger.info(f"   - {col} -> Mediana: {median:.3f} | Min: {df[col].min():.3f} | Max: {df[col].max():.3f}")
                if abs(median) > 0.5:
                    logger.warning(f"⚠️ Alerta de Data Drift: La mediana de {col} se desvió de 0.0 ({median:.3f})")

        logger.info("Validación concluida. Los datos verificados pueden pasar a torch.float32.")

    except Exception as e:
        logger.error(f"Falla crítica en la validación: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    validate_inference_data()
