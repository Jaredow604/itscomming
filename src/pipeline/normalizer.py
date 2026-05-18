import os
import joblib
import pandas as pd
import logging
from typing import List, Optional
from sklearn.preprocessing import RobustScaler

logger = logging.getLogger(__name__)

class SportsDataNormalizer:
    """
    Sistema de normalización para métricas deportivas.
    Utiliza RobustScaler para mitigar el impacto de superestrellas (outliers) 
    sin aplastar la varianza del resto de la distribución.
    """
    
    def __init__(self, scaler_dir: str = 'src/pipeline/scalers'):
        self.scaler_dir = os.path.abspath(scaler_dir)
        os.makedirs(self.scaler_dir, exist_ok=True)
        self.scaler = RobustScaler()
        self.is_fitted = False

    def _get_scaler_path(self, filename: str) -> str:
        """Construye y devuelve la ruta absoluta del archivo del escalador."""
        if not filename.endswith('.joblib'):
            filename += '.joblib'
        return os.path.join(self.scaler_dir, filename)

    def fit_and_save(self, df: pd.DataFrame, features: List[str], filename: str) -> pd.DataFrame:
        """
        Ajusta el escalador con los datos históricos y lo guarda en disco.
        Retorna el DataFrame con las características transformadas.
        
        Args:
            df: DataFrame con datos históricos.
            features: Lista de columnas a normalizar.
            filename: Nombre del archivo para guardar el escalador (ej. 'soccer_player_stats').
        """
        logger.info(f"Iniciando ajuste del escalador para {len(features)} características.")
        
        # Validar que las features existen
        missing_feats = [f for f in features if f not in df.columns]
        if missing_feats:
            raise ValueError(f"Las siguientes características no están en el DataFrame: {missing_feats}")

        df_scaled = df.copy()
        
        # Ajustar y transformar
        scaled_values = self.scaler.fit_transform(df[features])
        df_scaled[features] = scaled_values
        self.is_fitted = True
        
        # Guardar en disco
        scaler_path = self._get_scaler_path(filename)
        joblib.dump(self.scaler, scaler_path)
        logger.info(f"Escalador RobustScaler guardado exitosamente en: {scaler_path}")
        
        return df_scaled

    def load_and_transform(self, df: pd.DataFrame, features: List[str], filename: str) -> pd.DataFrame:
        """
        Carga un escalador previamente guardado y transforma datos en tiempo real (o de prueba).
        
        Args:
            df: DataFrame con nuevos datos (tiempo real).
            features: Lista de columnas a normalizar.
            filename: Nombre del archivo del escalador guardado previamente.
        """
        scaler_path = self._get_scaler_path(filename)
        
        if not os.path.exists(scaler_path):
            raise FileNotFoundError(f"No se encontró el escalador en la ruta: {scaler_path}. Ejecuta fit_and_save primero.")
            
        logger.debug(f"Cargando escalador desde: {scaler_path}")
        loaded_scaler = joblib.load(scaler_path)
        
        missing_feats = [f for f in features if f not in df.columns]
        if missing_feats:
            raise ValueError(f"Las características esperadas no se encuentran en los nuevos datos: {missing_feats}")
            
        df_scaled = df.copy()
        
        # Transformar manteniendo la escala original
        scaled_values = loaded_scaler.transform(df[features])
        df_scaled[features] = scaled_values
        logger.info(f"Transformación completada para {len(df)} registros usando escala histórica.")
        
        return df_scaled
