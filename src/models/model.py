import logging
import torch
import torch.nn as nn
from ..config.config import ModelConfig

logger = logging.getLogger(__name__)

class SportsPredictorMLP(nn.Module):
    """
    Multilayer Perceptron (MLP) dinámico y genérico para predicción deportiva.
    Soporta configuraciones variadas sin tocar la clase (Open/Closed Principle).
    """
    
    def __init__(self, config: ModelConfig):
        super().__init__()
        
        try:
            layers = []
            in_features = config.input_dim
            
            # Algoritmo de construcción dinámica de capas ocultas
            for hidden_dim in config.hidden_dims:
                layers.append(nn.Linear(in_features, hidden_dim))
                layers.append(nn.ReLU())
                layers.append(nn.Dropout(config.dropout_rate))
                in_features = hidden_dim
                
            # Agregamos la capa de salida adaptada para el target market
            layers.append(nn.Linear(in_features, config.output_dim))
            
            self.network = nn.Sequential(*layers)
            logger.info(f"Arquitectura MLP inicializada. Input: {config.input_dim} | Output: {config.output_dim}")
            
        except Exception as e:
            logger.error(f"Falla al construir la arquitectura SportsPredictorMLP: {e}")
            raise

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Paso progresivo (Forward Pass)."""
        return self.network(x)
