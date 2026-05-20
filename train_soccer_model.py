"""
train_soccer_model.py -- Entrena MatchPredictionNet con datos históricos de la BD.

Pipeline:
1. Lee match_history_stats (5,223 filas, 3 temporadas)
2. Construye vectores de features de 12 dimensiones
3. Entrena MatchPredictionNet con CrossEntropyLoss
4. Guarda checkpoint en checkpoints/soccer_best_model.pth
"""

import sys
import os
import logging
from pathlib import Path

# Añadir proyecto al path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import numpy as np
import pandas as pd

from database import SessionLocal
from src.data.models import MatchHistoryStats, Team
from src.models.networks.match_prediction_net import MatchPredictionNet

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
CHECKPOINT_DIR = project_root / 'checkpoints'
CHECKPOINT_DIR.mkdir(exist_ok=True)


def load_training_data() -> pd.DataFrame:
    """Carga datos de match_history_stats y construye features."""
    session = SessionLocal()
    try:
        records = session.query(MatchHistoryStats).all()
        logger.info(f"Registros en match_history_stats: {len(records)}")

        if not records:
            logger.error("No hay datos en match_history_stats. Ejecuta repoblar_bd.py primero.")
            return pd.DataFrame()

        # Extraer datos
        data = []
        for r in records:
            if r.result is None or r.home_team is None or r.away_team is None:
                continue

            # Obtener stats de equipos
            home_team = session.query(Team).filter(Team.nombre == r.home_team).first()
            away_team = session.query(Team).filter(Team.nombre == r.away_team).first()

            if not home_team or not away_team:
                continue

            home_stats = {
                'prom_goles': float(home_team.prom_goles or 1.2),
                'prom_tiros_puerta': float(home_team.prom_tiros_puerta or 4.0),
                'prom_corners': float(home_team.prom_corners or 5.0),
                'forma': 0.6,  # Placeholder - se puede mejorar con datos reales
            }
            away_stats = {
                'prom_goles': float(away_team.prom_goles or 1.0),
                'prom_tiros_puerta': float(away_team.prom_tiros_puerta or 3.5),
                'prom_corners': float(away_team.prom_corners or 4.5),
                'forma': 0.5,  # Placeholder
            }

            # Construir feature vector (12 dimensiones)
            features = [
                home_stats['prom_goles'],
                away_stats['prom_goles'],
                home_stats['prom_tiros_puerta'],
                away_stats['prom_tiros_puerta'],
                home_stats['prom_corners'],
                away_stats['prom_corners'],
                home_stats['forma'],
                away_stats['forma'],
                1.0,  # elo_home / 1500.0 (placeholder)
                1.0,  # elo_away / 1500.0 (placeholder)
                0.5,  # h2h_win_rate_home (placeholder)
                0.0,  # is_neutral
            ]

            data.append({
                'features': features,
                'result': int(r.result),  # 0=away, 1=draw, 2=home
                'home_team': r.home_team,
                'away_team': r.away_team,
                'home_score': r.home_score,
                'away_score': r.away_score,
            })

        df = pd.DataFrame(data)
        logger.info(f"Registros válidos para entrenamiento: {len(df)}")
        return df

    finally:
        session.close()


def prepare_datasets(df: pd.DataFrame):
    """Prepara datasets de entrenamiento y validación."""
    X = np.array(df['features'].tolist(), dtype=np.float32)
    y = np.array(df['result'].tolist(), dtype=np.int64)

    # Split train/val
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Normalizar features
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_val = scaler.transform(X_val)

    # Convertir a tensores
    X_train_t = torch.FloatTensor(X_train)
    y_train_t = torch.LongTensor(y_train)
    X_val_t = torch.FloatTensor(X_val)
    y_val_t = torch.LongTensor(y_val)

    logger.info(f"Train: {X_train.shape}, Val: {X_val.shape}")
    logger.info(f"Class distribution - Train: {np.bincount(y_train)}, Val: {np.bincount(y_val)}")

    return X_train_t, y_train_t, X_val_t, y_val_t, scaler


def train_model(X_train, y_train, X_val, y_val, epochs=100, lr=0.001, batch_size=64):
    """Entrena MatchPredictionNet."""
    model = MatchPredictionNet(input_dim=12, hidden_dim=128, output_dim=3).to(DEVICE)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', patience=10, factor=0.5)

    # DataLoaders
    train_dataset = TensorDataset(X_train, y_train)
    val_dataset = TensorDataset(X_val, y_val)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    best_val_loss = float('inf')
    best_model_state = None
    patience = 20
    patience_counter = 0

    for epoch in range(epochs):
        # Training
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0

        for X_batch, y_batch in train_loader:
            X_batch, y_batch = X_batch.to(DEVICE), y_batch.to(DEVICE)

            optimizer.zero_grad()
            outputs = model(X_batch)
            loss = criterion(outputs, y_batch)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * X_batch.size(0)
            _, predicted = torch.max(outputs, 1)
            train_total += y_batch.size(0)
            train_correct += (predicted == y_batch).sum().item()

        train_loss /= train_total
        train_acc = train_correct / train_total

        # Validation
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0

        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                X_batch, y_batch = X_batch.to(DEVICE), y_batch.to(DEVICE)
                outputs = model(X_batch)
                loss = criterion(outputs, y_batch)

                val_loss += loss.item() * X_batch.size(0)
                _, predicted = torch.max(outputs, 1)
                val_total += y_batch.size(0)
                val_correct += (predicted == y_batch).sum().item()

        val_loss /= val_total
        val_acc = val_correct / val_total

        scheduler.step(val_loss)

        if (epoch + 1) % 10 == 0 or epoch == 0:
            logger.info(
                f"Epoch {epoch+1}/{epochs} | "
                f"Train Loss: {train_loss:.4f} Acc: {train_acc:.3f} | "
                f"Val Loss: {val_loss:.4f} Acc: {val_acc:.3f}"
            )

        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_model_state = model.state_dict().copy()
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                logger.info(f"Early stopping at epoch {epoch+1}")
                break

    # Cargar mejor modelo
    if best_model_state:
        model.load_state_dict(best_model_state)

    return model, best_val_loss, val_acc


def main():
    logger.info("=" * 60)
    logger.info("Entrenando MatchPredictionNet para Soccer")
    logger.info("=" * 60)

    # 1. Cargar datos
    df = load_training_data()
    if df.empty:
        logger.error("No hay datos para entrenar. Saliendo.")
        return

    # 2. Preparar datasets
    X_train, y_train, X_val, y_val, scaler = prepare_datasets(df)

    # 3. Entrenar
    model, val_loss, val_acc = train_model(X_train, y_train, X_val, y_val)

    # 4. Guardar checkpoint
    checkpoint_path = CHECKPOINT_DIR / 'soccer_best_model.pth'
    torch.save({
        'model_state_dict': model.state_dict(),
        'val_loss': val_loss,
        'val_acc': val_acc,
        'scaler_mean': scaler.mean_.tolist(),
        'scaler_scale': scaler.scale_.tolist(),
    }, checkpoint_path)

    logger.info(f"Modelo guardado en: {checkpoint_path}")
    logger.info(f"Mejor Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.3f}")

    # 5. Probar inferencia
    model.eval()
    with torch.no_grad():
        # Ejemplo: Arsenal vs Burnley
        test_features = torch.FloatTensor([[
            2.03, 0.68,  # prom_goles
            4.89, 2.92,  # prom_tiros_puerta
            5.81, 4.0,   # prom_corners
            0.8, 0.3,    # forma
            1.08, 0.92,  # elo normalizado
            0.6, 0.0     # h2h, neutral
        ]]).to(DEVICE)

        # Normalizar
        test_features_np = test_features.cpu().numpy()
        test_features_np = scaler.transform(test_features_np)
        test_features = torch.FloatTensor(test_features_np).to(DEVICE)

        logits = model(test_features)
        probs = torch.softmax(logits, dim=1)
        logger.info(f"Test inference - Arsenal vs Burnley:")
        logger.info(f"  Probs [Draw, Home, Away]: {probs.cpu().numpy()[0]}")
        logger.info(f"  Favored: {['Draw', 'Home', 'Away'][torch.argmax(probs, dim=1).item()]}")


if __name__ == '__main__':
    main()
