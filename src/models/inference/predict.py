import torch
import pandas as pd
from typing import Tuple, Optional, List

from src.models.networks.player_prop_net import PlayerPropNet
from src.models.datasets.fbref_player_dataset import FBrefPlayerDataset


def load_model(model_path: str, input_dim: int = 3) -> PlayerPropNet:
    model = PlayerPropNet(input_dim=input_dim)
    model.load_state_dict(torch.load(model_path, map_location=torch.device('cpu')))
    model.eval()
    return model


def predict_player_goals(player_name: str, model: PlayerPropNet, dataset: FBrefPlayerDataset) -> Optional[Tuple[str, str, float]]:
    metadata = dataset.metadata
    mask = metadata['nombre_jugador'].str.contains(player_name, case=False, na=False)
    matches = metadata[mask]

    if matches.empty:
        return None

    idx = matches.index[0]
    real_name = matches.loc[idx, 'nombre_jugador']
    team_name = matches.loc[idx, 'team_name']

    features_tensor, _ = dataset[idx]

    with torch.no_grad():
        prediction_tensor = model(features_tensor.unsqueeze(0))
        predicted_goals = prediction_tensor.item()

    return real_name, team_name, round(predicted_goals, 2)


def predict_players(player_names_list: List[str], db_url: str, feature_cols: Optional[List[str]] = None, target_col: str = 'Performance_Gls'):
    if feature_cols is None:
        feature_cols = ['Playing Time_Min', 'Total_Shots', 'Standard_SoT']

    dataset = FBrefPlayerDataset(db_url=db_url, feature_cols=feature_cols, target_col=target_col)
    model = PlayerPropNet(input_dim=len(feature_cols))

    try:
        model.load_state_dict(torch.load('modelo_base.pth', map_location=torch.device('cpu'), weights_only=True))
        model.eval()
    except FileNotFoundError:
        print("Error: 'modelo_base.pth' no encontrado.")
        return

    metadata = dataset.metadata
    col_player = 'nombre_jugador' if 'nombre_jugador' in metadata.columns else 'player'
    col_team = 'team_name' if 'team_name' in metadata.columns else 'team'

    print("\n" + "=" * 70)
    print(f"| {'NOMBRE JUGADOR':<22} | {'EQUIPO':<15} | {'PRED IA':<9} | {'REAL':<6} |")
    print("=" * 70)

    for player in player_names_list:
        player_mask = metadata[col_player].str.lower() == player.lower()

        if player_mask.any():
            idx = player_mask[player_mask].index[0]
            team_name = str(metadata.loc[idx, col_team])[:15] if col_team else "N/A"
            features, real_goals = dataset[idx]

            with torch.no_grad():
                pred_goals = model(features.unsqueeze(0)).item()

            print(f"| {player:<22} | {team_name:<15} | {pred_goals:>6.2f}    | {int(real_goals.item()):>4}   |")
        else:
            print(f"| {player:<22} | {'N/A':<15} | {'--':>9} | {'--':>6} | (No Encontrado)")

    print("=" * 70 + "\n")
