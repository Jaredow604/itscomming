import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class PipelineValidator:
    """
    Validador de pipelines de datos para la plataforma deportiva.
    Garantiza la integridad de los datos antes de inyectarlos a los modelos PyTorch.
    Detecta nulos, outliers severos, y cambios de distribución (Data Drift).
    """

    def __init__(self, drift_threshold: float = 2.0):
        """
        Args:
            drift_threshold: Número de desviaciones estándar para considerar que
                             la media de un nuevo batch ha "derivado" demasiado (Data Drift).
        """
        self.drift_threshold = drift_threshold
        self.historical_stats: Dict[str, Dict[str, float]] = {}

    def fit_historical_stats(self, df: pd.DataFrame, features: List[str]):
        """
        Calcula y guarda la media y desviación estándar de los datos históricos.
        Se usa como "Ground Truth" para evaluar el Data Drift en el futuro.
        """
        for feature in features:
            if feature in df.columns:
                self.historical_stats[feature] = {
                    'mean': df[feature].mean(),
                    'std': df[feature].std()
                }
        logger.info("Estadísticas históricas ajustadas para detección de Data Drift.")

    def check_nulls(self, df: pd.DataFrame, features: List[str]) -> pd.DataFrame:
        """
        Verifica la existencia de nulos en las características críticas.
        Retorna el DataFrame limpio (o levanta excepción si es inaceptable, 
        aunque aquí usamos imputación segura o drop para pipelines robustos).
        """
        null_counts = df[features].isnull().sum()
        total_nulls = null_counts.sum()
        
        if total_nulls > 0:
            logger.warning(f"Se detectaron {total_nulls} valores nulos en el batch de datos.")
            for feature in features:
                if null_counts[feature] > 0:
                    logger.warning(f"Feature '{feature}' tiene {null_counts[feature]} nulos.")
            
            # En plataformas deportivas en tiempo real, es mejor rellenar con 0 
            # (ej. si no hay tiros a puerta reportados) o eliminar si es imprescindible.
            # Aquí aplicamos fillna(0) como mecanismo de fallback para que el pipeline no se detenga.
            df = df.copy()
            df[features] = df[features].fillna(0)
            logger.warning("Valores nulos imputados con 0 para mantener flujo de inferencia.")
        else:
            logger.debug("Comprobación de nulos superada exitosamente.")
            
        return df

    def detect_outliers_iqr(self, df: pd.DataFrame, features: List[str]) -> None:
        """
        Detecta valores atípicos severos usando el método del rango intercuartílico (IQR).
        Solo emite warnings, ya que en deportes los outliers pueden ser actuaciones récord.
        """
        for feature in features:
            if feature not in df.columns:
                continue
                
            Q1 = df[feature].quantile(0.25)
            Q3 = df[feature].quantile(0.75)
            IQR = Q3 - Q1
            
            # Usamos 3.0 en lugar de 1.5 para detectar solo outliers muy extremos
            lower_bound = Q1 - 3.0 * IQR
            upper_bound = Q3 + 3.0 * IQR
            
            outliers = df[(df[feature] < lower_bound) | (df[feature] > upper_bound)]
            if not outliers.empty:
                logger.warning(
                    f"Outliers extremos detectados en '{feature}': "
                    f"{len(outliers)} registros fuera del rango [{lower_bound:.2f}, {upper_bound:.2f}]."
                )

    def check_data_drift(self, df: pd.DataFrame, features: List[str]) -> None:
        """
        Compara la distribución del batch actual con la distribución histórica.
        No bloquea el pipeline, solo registra advertencias si detecta desvíos significativos.
        """
        if not self.historical_stats:
            logger.info("No hay estadísticas históricas cargadas. Omitiendo validación de Data Drift.")
            return

        for feature in features:
            if feature not in df.columns or feature not in self.historical_stats:
                continue

            current_mean = df[feature].mean()
            hist_mean = self.historical_stats[feature]['mean']
            hist_std = self.historical_stats[feature]['std']

            if hist_std == 0:
                continue  # Evitar división por cero
                
            # Z-Score de la media actual respecto a la distribución histórica
            drift_score = abs(current_mean - hist_mean) / hist_std
            
            if drift_score > self.drift_threshold:
                logger.warning(
                    f"[DATA DRIFT DETECTADO] Feature '{feature}': "
                    f"Media actual ({current_mean:.4f}) difiere significativamente "
                    f"de la histórica ({hist_mean:.4f}). Drift Score: {drift_score:.2f} > {self.drift_threshold}"
                )

    def validate_pipeline(self, df: pd.DataFrame, features: List[str]) -> pd.DataFrame:
        """
        Ejecuta todas las validaciones en cadena.
        """
        logger.info("Iniciando validación del pipeline de datos...")
        df_clean = self.check_nulls(df, features)
        self.detect_outliers_iqr(df_clean, features)
        self.check_data_drift(df_clean, features)
        logger.info("Validación de pipeline completada.")
        
        return df_clean
