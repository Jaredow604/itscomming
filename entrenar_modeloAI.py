import os 
import django
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
import logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings')
django.setup()
from predicciones.models import Partido

# Importar la nueva arquitectura desde src
from src.config.config import ModelConfig, TrainingConfig
from src.data.dataset import SportsMetricsDataset
from src.models.model import SportsPredictorMLP
from src.training.trainer import Trainer

# Configuración básica de logging para ver los prints del Trainer y de este script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("entrenar_modelo_pipeline")

def preparar_datos_dataframe() -> pd.DataFrame:
    logger.info("Extrayendo datos de la base de datos (Django ORM)...")
    partidos = Partido.objects.filter(jugado=True)
    
    data = []
    for p in partidos:
        # Calcular target: 1 = Gana Local, 0 = Empate, 2 = Gana Visitante
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
    # 1. Obtener y preparar datos
    df = preparar_datos_dataframe()
    if df.empty:
        logger.warning("No hay partidos jugados en la base de datos. Abortando entrenamiento.")
        return
        
    feature_cols = ["local_goles", "visitante_goles"]
    target_col = "resultado"

    # 2. Configuraciones
    # Adaptado un poco a la red ligera que ya tenías
    model_config = ModelConfig(
        input_dim=len(feature_cols),
        output_dim=3, # 3 clases: Local(1), Empate(0), Visitante(2)
        hidden_dims=[16, 8], 
        dropout_rate=0.0 # Red pequeña, evitamos underfitting excesivo
    )
    
    training_config = TrainingConfig(
        batch_size=32 if len(df) >= 32 else (len(df) if len(df) > 0 else 1),
        learning_rate=0.01,
        epochs=500,
        device="cuda" if torch.cuda.is_available() else "cpu"
    )

    # 3. Preparar Dataset y DataLoader
    dataset = SportsMetricsDataset(df, feature_cols=feature_cols, target_col=target_col)
    dataloader = DataLoader(dataset, batch_size=training_config.batch_size, shuffle=True)

    # 4. Construir Componentes (Inyección de Dependencias)
    modelo = SportsPredictorMLP(model_config)
    criterio = nn.CrossEntropyLoss()
    optimizador = optim.Adam(modelo.parameters(), lr=training_config.learning_rate)
    dispositivo = torch.device(training_config.device)

    # 5. Instanciar Trainer y Entrenar
    entrenador = Trainer(modelo, optimizador, criterio, dispositivo)
    entrenador.fit(train_loader=dataloader, val_loader=None, epochs=training_config.epochs)
    
    # 6. Guardar los pesos del modelo
    torch.save(modelo.state_dict(), 'oracle_brain.pth')
    logger.info("Entrenamiento completado y pesos guardados en 'oracle_brain.pth'.")

if __name__ == '__main__':
    entrenar_modelo()
