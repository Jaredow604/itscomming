import sys
import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

# Modificación estructural del path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.models.datasets.match_dataset import MatchDataset
from src.models.networks.match_prediction_net import MatchPredictionNet

def train_match_model(epochs=150, batch_size=32, lr=0.001):
    print("Iniciando Pipeline Critico de Entrenamiento (Match ML)...")
    
    # 1. Cargar Dataset Paramétrico
    dataset = MatchDataset()
    
    if len(dataset) == 0:
        print("Operacion abortada: No hay datos disponibles para entrenar.")
        return
        
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    
    # 2. Instanciar Red (Input=6, Output=3 Clases)
    model = MatchPredictionNet(input_dim=6)
    
    # Usamos CrossEntropyLoss porque el problema es Multiclase (Empate, Local, Visita)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)
    
    print("\nComienza Backpropagation")
    model.train()
    
    for epoch in range(epochs):
        epoch_loss = 0.0
        for features, targets in dataloader:
            optimizer.zero_grad()
            
            # Forward pass
            outputs = model(features)
            
            # Cálculo de la pérdida
            loss = criterion(outputs, targets)
            
            # Backward pass 
            loss.backward()
            optimizer.step()
            
            epoch_loss += loss.item()
            
        if (epoch + 1) % 10 == 0:
            print(f"Epoch [{epoch+1}/{epochs}], Loss: {epoch_loss/len(dataloader):.4f}")
            
    # Guardar modelo a disco. 
    # Usaremos un path relativo hacia la raíz para que el dashboard lo lea
    ruta_guardado = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'oracle_h2h_brain.pth'))
    torch.save(model.state_dict(), ruta_guardado)
    print(f"\nEntrenamiento Exitoso. Pesos exportados a: {ruta_guardado}")


if __name__ == "__main__":
    train_match_model()
