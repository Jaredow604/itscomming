"""
Script de inferencia para interactuar con la red PlayerPropNet y ver predicciones reales.
"""

import torch
import pandas as pd
import sqlalchemy

from src.models.networks.player_prop_net import PlayerPropNet
from src.models.datasets.fbref_player_dataset import FBrefPlayerDataset


def predict_players(player_names_list, db_url):
    """
    Realiza inferencia sobre una lista de jugadores para predecir sus goles
    comparando las predicciones de la IA con la realidad.
    
    Args:
        player_names_list (list): Nombres de los jugadores a evaluar.
        db_url (str): String de conexión a la base de datos PostgreSQL.
    """
    
    feature_cols = ['Playing Time_Min', 'Playing Time_Starts', 'Performance_Ast', 'Performance_CrdY']
    target_col = 'Performance_Gls'
    
    print("🔧 Instanciando Dataset y aplicando normalizaciones...")
    # Instancia el dataset
    dataset = FBrefPlayerDataset(
        db_url=db_url, 
        feature_cols=feature_cols, 
        target_col=target_col
    )
    
    print("🧠 Cargando la Arquitectura y Pesos de la Red Neuronal...")
    # Instancia el modelo
    model = PlayerPropNet(input_dim=4)
    
    # Carga los pesos y ponlo en modo evaluación
    try:
        model.load_state_dict(torch.load('modelo_base.pth', map_location=torch.device('cpu'), weights_only=True))
        model.eval()
    except FileNotFoundError:
        print("❌ Error: 'modelo_base.pth' no encontrado. Asegúrate de haber entrenado el modelo antes.")
        return
        
    metadata = dataset.metadata
    
    # Verificación estricta de la estructura de metadatos
    col_player = 'nombre_jugador' if 'nombre_jugador' in metadata.columns else ('player' if 'player' in metadata.columns else None)
    col_team = 'team_name' if 'team_name' in metadata.columns else ('team' if 'team' in metadata.columns else None)
    
    if not col_player:
        print("❌ Error: No se pudo identificar la columna de jugadores en los metadatos extraídos.")
        return
        
    print("\n" + "="*70)
    print(f"| {'NOMBRE JUGADOR':<22} | {'EQUIPO':<15} | {'PRED IA':<9} | {'REAL':<6} |")
    print("="*70)
    
    for player in player_names_list:
        # Busca al jugador ignorando mayúsculas/minúsculas
        player_mask = metadata[col_player].str.lower() == player.lower()
        
        if player_mask.any():
            # Extrae el índice idx
            idx = metadata[player_mask].index[0]
            team_name = str(metadata.loc[idx, col_team])[:15] if col_team else "N/A"
            
            # Obtiene tensor de features normalizado y su target real
            features, real_goals = dataset[idx]
            
            # Lo pasa por el modelo
            with torch.no_grad():
                pred_goals = model(features.unsqueeze(0)).item()
                
            print(f"| {player:<22} | {team_name:<15} | {pred_goals:>6.2f}    | {int(real_goals.item()):>4}   |")
        else:
            print(f"| {player:<22} | {'N/A':<15} | {'--':>9} | {'--':>6} | (No Encontrado)")
            
    print("="*70 + "\n")


if __name__ == "__main__":
    # Define la variable DB_URL (INDICACIÓN: Reemplazar <TU_PASSWORD> con tu contraseña de PostgreSQL real)
    DB_URL = "postgresql://postgres:Jk9oe@localhost:5432/itscoming_db"
    
    # Define una lista de prueba con 4 jugadores estelares
    test_list = ['Erling Haaland', 'Henry Martín', 'Kylian Mbappé', 'Jude Bellingham']
    
    # Ejecuta la función
    predict_players(test_list, DB_URL)
