"""
train_player_props.py -- Entrena PlayerPropNet con datos de inference_ready_player_data.

Pipeline:
1. Lee ml_inference_ready_player_data (datos ya escalados)
2. Entrena PlayerPropNet con features scaled
3. Guarda checkpoint en checkpoints/player_prop_model.pth
"""

import sys
import os
import logging
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np

from database import SessionLocal
from src.data.models import InferenceReadyPlayerData
from src.models.networks.player_prop_net import PlayerPropNet

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
CHECKPOINT_DIR = project_root / 'checkpoints'
CHECKPOINT_DIR.mkdir(exist_ok=True)


def load_player_data():
    """Carga datos de jugadores ya escalados."""
    session = SessionLocal()
    try:
        players = session.query(InferenceReadyPlayerData).all()
        logger.info(f"Jugadores en inference_ready_player_data: {len(players)}")

        if not players:
            logger.error("No hay datos en ml_inference_ready_player_data.")
            return None, None

        features = []
        targets = []

        for p in players:
            pt_min = float(p.playing_time_min_scaled or 0.0)
            t_shots = float(p.total_shots_scaled or 0.0)
            s_sot = float(p.standard_sot_scaled or 0.0)

            # Skip invalid data
            if pt_min == 0.0 and t_shots == 0.0 and s_sot == 0.0:
                continue

            features.append([pt_min, t_shots, s_sot])
            # Target: performance_gls (goles esperados)
            targets.append(float(p.performance_gls or 0.0))

        X = np.array(features, dtype=np.float32)
        y = np.array(targets, dtype=np.float32)

        logger.info(f"Datos válidos: {X.shape[0]} jugadores")
        return X, y

    finally:
        session.close()


def train_model(X, y, epochs=100, lr=0.001, batch_size=32):
    """Entrena PlayerPropNet."""
    model = PlayerPropNet(input_dim=3).to(DEVICE)
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', patience=10, factor=0.5)

    # Split
    n = len(X)
    split = int(n * 0.8)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    train_dataset = TensorDataset(torch.FloatTensor(X_train), torch.FloatTensor(y_train))
    val_dataset = TensorDataset(torch.FloatTensor(X_val), torch.FloatTensor(y_val))
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    best_val_loss = float('inf')
    best_model_state = None
    patience = 20
    patience_counter = 0

    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        for X_batch, y_batch in train_loader:
            X_batch, y_batch = X_batch.to(DEVICE), y_batch.to(DEVICE)
            optimizer.zero_grad()
            pred = model(X_batch).squeeze()
            loss = criterion(pred, y_batch)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * X_batch.size(0)

        train_loss /= len(X_train)

        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                X_batch, y_batch = X_batch.to(DEVICE), y_batch.to(DEVICE)
                pred = model(X_batch).squeeze()
                loss = criterion(pred, y_batch)
                val_loss += loss.item() * X_batch.size(0)

        val_loss /= len(X_val)
        scheduler.step(val_loss)

        if (epoch + 1) % 10 == 0 or epoch == 0:
            logger.info(f"Epoch {epoch+1}/{epochs} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_model_state = model.state_dict().copy()
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                logger.info(f"Early stopping at epoch {epoch+1}")
                break

    if best_model_state:
        model.load_state_dict(best_model_state)

    return model, best_val_loss


def main():
    logger.info("=" * 60)
    logger.info("Entrenando PlayerPropNet")
    logger.info("=" * 60)

    X, y = load_player_data()
    if X is None:
        return

    model, val_loss = train_model(X, y)

    checkpoint_path = CHECKPOINT_DIR / 'player_prop_model.pth'
    torch.save({
        'model_state_dict': model.state_dict(),
        'val_loss': val_loss,
    }, checkpoint_path)

    logger.info(f"Modelo guardado en: {checkpoint_path}")
    logger.info(f"Mejor Val Loss: {val_loss:.4f}")

    # Test inference
    model.eval()
    with torch.no_grad():
        test_feat = torch.FloatTensor([[0.5, 0.3, 0.4]]).to(DEVICE)
        pred = model(test_feat).item()
        logger.info(f"Test inference: {pred:.2f} goles esperados")


if __name__ == '__main__':
    main()
