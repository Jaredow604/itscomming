import os
import django
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
import logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from predicciones.models import Partido

from src.config.config import ModelConfig, TrainingConfig
from src.models.model import SportsPredictorMLP
from src.training.sports_trainer import SportsModelTrainer, TrainerConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("entrenar_modelo_pipeline")

def preparar_datos_dataframe() -> pd.DataFrame:
    logger.info("Extrayendo datos de la base de datos (Django ORM)...")
    partidos = Partido.objects.filter(jugado=True)

    data = []
    for p in partidos:
        if p.goles_local > p.goles_visitante:
            y = 1
        elif p.goles_local == p.goles_visitante:
            y = 0
        else:
            y = 2

        data.append({
            "local_goles": float(p.local.prom_goles) if p.local and p.local.prom_goles else 0.0,
            "visitante_goles": float(p.visitante.prom_goles) if p.visitante and p.visitante.prom_goles else 0.0,
            "resultado": int(y)
        })

    df = pd.DataFrame(data)
    logger.info(f"Se extrajeron {len(df)} partidos exitosamente.")
    return df

def entrenar_modelo():
    df = preparar_datos_dataframe()
    if df.empty:
        logger.warning("No hay partidos jugados en la base de datos. Abortando entrenamiento.")
        return

    feature_cols = ["local_goles", "visitante_goles"]
    target_col = "resultado"

    model_config = ModelConfig(
        input_dim=len(feature_cols),
        output_dim=3,
        hidden_dims=[16, 8],
        dropout_rate=0.0
    )

    trainer_config = TrainerConfig(
        epochs=500,
        learning_rate=0.01,
        weight_decay=0.0,
        patience=30,
        checkpoint_name='oracle_brain.pth',
        log_every_n=10,
    )

    X = torch.tensor(df[feature_cols].values, dtype=torch.float32)
    y = torch.tensor(df[target_col].values, dtype=torch.long)
    dataset = TensorDataset(X, y)

    split = int(len(dataset) * 0.8)
    train_ds, val_ds = torch.utils.data.random_split(dataset, [split, len(dataset) - split])

    train_loader = DataLoader(train_ds, batch_size=min(32, len(train_ds)), shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=min(32, len(val_ds)))

    modelo = SportsPredictorMLP(model_config)
    criterio = nn.CrossEntropyLoss()

    trainer = SportsModelTrainer(modelo, criterio, config=trainer_config)
    history = trainer.fit(train_loader, val_loader)

    torch.save(modelo.state_dict(), 'oracle_brain.pth')
    logger.info("Entrenamiento completado y pesos guardados en 'oracle_brain.pth'.")

if __name__ == '__main__':
    entrenar_modelo()
