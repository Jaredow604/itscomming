import logging
import torch
import pandas as pd
from torch.utils.data import Dataset
from typing import Tuple

logger = logging.getLogger(__name__)

class SportsMetricsDataset(Dataset):
    """
    Dataset personalizado para métricas deportivas.
    Implementa Single Responsibility Principle (SRP) aislándose de la red.
    """
    
    def __init__(self, data: pd.DataFrame, feature_cols: list[str], target_col: str):
        """
        Inicializa el dataset transformando features de DataFrame a Tensores.
        """
        try:
            self.features = torch.tensor(data[feature_cols].values, dtype=torch.float32)
            
            # Autodetect if targets are integer (for classification) or float (for regression)
            target_values = data[target_col].values
            if pd.api.types.is_integer_dtype(target_values):
                self.targets = torch.tensor(target_values, dtype=torch.long)
            else:
                self.targets = torch.tensor(target_values, dtype=torch.float32)
                
            logger.info(f"SportsMetricsDataset inicializado exitosamente | {len(self.features)} registros cargados.")
            
        except KeyError as e:
            logger.error(f"Error crítico: Columna no encontrada en el DataFrame: {e}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado al inicializar el dataset: {e}")
            raise

    def __len__(self) -> int:
        return len(self.features)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        return self.features[idx], self.targets[idx]
