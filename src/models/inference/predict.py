import torch
import pandas as pd
from typing import Tuple, Optional

# Ajustamos la ruta correcta basada en las importaciones comprobadas anteriormente
from src.models.networks.player_prop_net import PlayerPropNet
from src.models.datasets.fbref_player_dataset import FBrefPlayerDataset

def load_model(model_path: str, input_dim: int = 3) -> PlayerPropNet:
    """
    Instancia la red neuronal, carga los pesos guardados y ajusta el modelo 
    en modo de evaluación para inferencia.
    """
    model = PlayerPropNet(input_dim=input_dim)
    # Cargar pesos asegurando compatibilidad con CPU si no hay GPU disponible
    model.load_state_dict(torch.load(model_path, map_location=torch.device('cpu')))
    model.eval()
    return model

def predict_player_goals(player_name: str, model: PlayerPropNet, dataset: FBrefPlayerDataset) -> Optional[Tuple[str, str, float]]:
    """
    Busca al jugador en la base de datos (ignorando mayúsculas y minúsculas),
    extrae sus características y genera una predicción basada en la red entrenada.
    """
    # Buscamos coincidencias (parciales o exactas) en la columna 'nombre_jugador'
    metadata = dataset.metadata
    
    # Nos aseguramos de ignorar NaNs en la métrica de texto
    mask = metadata['nombre_jugador'].str.contains(player_name, case=False, na=False)
    matches = metadata[mask]
    
    if matches.empty:
        return None
        
    # Extraemos el índice del primer partido/jugador encontrado
    idx = matches.index[0]
    
    # Información real del jugador encontrado
    real_name = matches.loc[idx, 'nombre_jugador']
    team_name = matches.loc[idx, 'team_name']
    
    # Extraemos el tensor de features normalizadas
    features_tensor, _ = dataset[idx]
    
    # Hacemos la predicción agregando la dimensión de batch (unsqueeze)
    with torch.no_grad():
        prediction_tensor = model(features_tensor.unsqueeze(0))
        # Extraemos el valor real escalar
        predicted_goals = prediction_tensor.item()
        
    return real_name, team_name, round(predicted_goals, 2)

if __name__ == "__main__":
    print("-" * 50)
    print("INICIANDO MOTOR DE INFERENCIA PREDICTIVA")
    print("-" * 50)

    # 1. Configuración y Carga del Dataset Híbrido
    DB_URL = "postgresql://postgres:Jk9oe@localhost:5432/itscoming_db"
    
    # Especificamos las características alineadas a input_dim=3
    feature_cols = ['Playing Time_Min', 'Total_Shots', 'Standard_SoT']
    
    try:
        print("[1/3] Cargando FBrefPlayerDataset Híbrido desde DataWarehouse...")
        dataset = FBrefPlayerDataset(db_url=DB_URL, feature_cols=feature_cols)
        print(f"      -> Dataset instanciado con {len(dataset)} registros.\n")
        
        # 2. Carga del Modelo
        print("[2/3] Levantando modelo pre-entrenado (modelo_base.pth)...")
        model = load_model('modelo_base.pth', input_dim=3)
        print("      -> Modelo en modo Evaluación (eval). Listo para predicciones.\n")
        
        # 3. Predicciones con datos Reales
        print("[3/3] Ejecutando predicciones de prueba...")
        print("-" * 50)
        
        test_players = ['Erling Haaland', 'Henry Martín', 'Kylian Mbappé', 'Lionel Messi', 'Vinicius']
        
        for name in test_players:
            result = predict_player_goals(name, model, dataset)
            
            if result is None:
                print(f"[!] Búsqueda: '{name}' -> No encontrado en los registros de la BBDD activa.")
            else:
                real_name, team, proj_goals = result
                print(f"[✓] {real_name} ({team}) -> Proyección de Rendimiento: {proj_goals} Goles ESP")
            
        print("-" * 50)
        
    except FileNotFoundError as e:
        print(f"\n[ERROR CRÍTICO] Archivo no encontrado: {e}")
        print("Asegúrate de haber corrido trainer.py para generar 'modelo_base.pth' primero.")
    except Exception as e:
        print(f"\n[ERROR DE SISTEMA] {e}")
