from dataclasses import dataclass, field
from typing import List

@dataclass
class ModelConfig:
    """Configuración de la arquitectura del modelo predictivo."""
    input_dim: int
    output_dim: int
    # Capas por defecto configurables
    hidden_dims: List[int] = field(default_factory=lambda: [128, 64, 32])
    dropout_rate: float = 0.2

@dataclass
class TrainingConfig:
    """Configuración del bucle de entrenamiento."""
    batch_size: int = 32
    learning_rate: float = 1e-3
    epochs: int = 50
    device: str = "cuda" # o "cpu"
