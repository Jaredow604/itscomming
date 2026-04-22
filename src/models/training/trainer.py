"""
Motor de entrenamiento para la red PlayerPropNet utilizando el FBrefPlayerDataset.
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

from src.models.datasets.fbref_player_dataset import FBrefPlayerDataset
from src.models.networks.player_prop_net import PlayerPropNet


def train_model(model, dataloader, epochs=50, lr=0.001):
    """
    Entrena el modelo PlayerPropNet para predecir goles (o cualquier métrica objetivo).
    
    Args:
        model (nn.Module): Instancia de PlayerPropNet.
        dataloader (DataLoader): DataLoader con los datos de entrenamiento.
        epochs (int): Número de épocas de entrenamiento.
        lr (float): Tasa de aprendizaje (learning rate).
    """
    # Define la función de pérdida para regresión (Mean Squared Error)
    criterion = nn.MSELoss()
    
    # Define el optimizador (Adam)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    
    for epoch in range(1, epochs + 1):
        # Pon el modelo en modo entrenamiento
        model.train()
        
        epoch_loss = 0.0
        
        for features, targets in dataloader:
            # Asegúrate de que los targets tengan la forma correcta: [batch_size, 1]
            targets = targets.view(-1, 1).float()
            
            # Limpia gradientes
            optimizer.zero_grad()
            
            # Forward pass
            predictions = model(features.float())
            
            # Calcula el error
            loss = criterion(predictions, targets)
            
            # Backward pass
            loss.backward()
            
            # Actualiza pesos
            optimizer.step()
            
            # Suma el loss.item() al epoch_loss total de la época
            epoch_loss += loss.item()
        
        # Calcular pérdida promedio de la época para mostrar
        avg_loss = epoch_loss / len(dataloader)
        
        # Imprime el progreso cada 10 epochs
        if epoch % 10 == 0:
            print(f"Epoch {epoch}/{epochs}, Loss: {avg_loss:.4f}")
    torch.save (model.state_dict(),'modelo_base.pth')
    print("Cerebro guardado exitosamente en modelo_base.pth")

if __name__ == "__main__":
    # Define la conexión DB_URL
    DB_URL = "postgresql://postgres:Jk9oe@localhost:5432/itscoming_db"
    
    # Instancia el dataset con las columnas especificadas (3 características)
    feature_cols = ['Playing Time_Min', 'Total_Shots', 'Standard_SoT']
    target_col = 'Performance_Gls'
    
    print("Inicializando dataset...")
    # Instancia el dataset
    dataset = FBrefPlayerDataset(
        db_url=DB_URL, 
        feature_cols=feature_cols, 
        target_col=target_col
    )
    
    if len(dataset) == 0:
        print("El dataset está vacío. Asegúrate de tener datos en la base de datos.")
    else:
        print(f"Dataset cargado con {len(dataset)} registros.")
        
        # Envuelve el dataset en un DataLoader con batch_size=32 y shuffle=True
        dataloader = DataLoader(dataset, batch_size=32, shuffle=True)
        
        # Instancia el modelo (input_dim=3) coincidiendo con feature_cols
        model = PlayerPropNet(input_dim=3)
        
        print("Iniciando entrenamiento...")
        # Llama a train_model
        train_model(model, dataloader, epochs=100)
        print("Entrenamiento finalizado.")
