import os
import glob
import torch
import pandas as pd
import numpy as np
from torch.utils.data import Dataset
from sqlalchemy import create_engine

class FBrefPlayerDataset(Dataset):
    """
    Clase Dataset de PyTorch Híbrida:
    Lee datos base desde PostgreSQL y datos avanzados de tiro desde CSVs locales.
    Fusiona las fuentes y prepara tensores normalizados para el entrenamiento.
    """
    def __init__(self, db_url, data_dir='src/data', feature_cols=None, target_col='Performance_Gls'):
        if feature_cols is None:
            feature_cols = ['Playing Time_Min', 'Total_Shots', 'Standard_SoT']
            
        # 1. Carga de BD
        engine = create_engine(db_url)
        df_db = pd.read_sql_table('fbref_player_stats', engine)
        
        # 2. Carga de CSVs (Robusta)
        csv_pattern = os.path.join(data_dir, 'shooting_*.csv')
        csv_files = glob.glob(csv_pattern)
        
        if not csv_files:
            raise FileNotFoundError(f"No se encontraron archivos CSV con el patrón {csv_pattern}")
            
        # Itera sobre los archivos y lee saltando la primera fila basura (header=1)
        df_csv_list = [pd.read_csv(f, header=1) for f in csv_files]
        df_csv = pd.concat(df_csv_list, ignore_index=True)
        
        # Elimina las filas donde el nombre del jugador sea literalmente "Player"
        df_csv = df_csv[df_csv['Player'] != 'Player']
        
        # Quita nulos en la columna Player
        df_csv = df_csv.dropna(subset=['Player'])
        
        # Renombra las columnas
        df_csv = df_csv.rename(columns={
            'Player': 'nombre_jugador',
            'Squad': 'team_name',
            'Sh': 'Total_Shots',
            'SoT': 'Standard_SoT'
        })
        
        # Convierte métricas a formato numérico y rellena nulos con 0
        df_csv['Total_Shots'] = pd.to_numeric(df_csv['Total_Shots'], errors='coerce').fillna(0)
        df_csv['Standard_SoT'] = pd.to_numeric(df_csv['Standard_SoT'], errors='coerce').fillna(0)
        
        # 3. Fusión (Merge)
        # Inner join sobre ['nombre_jugador', 'team_name']
        df = pd.merge(df_db, df_csv, on=['nombre_jugador', 'team_name'], how='inner')
        
        # 4. Limpieza Final
        # Convierte los minutos a numérico por seguridad y rellena posibles nulos adicionales
        if "Playing Time_Min" in df.columns:
            df['Playing Time_Min'] = pd.to_numeric(df['Playing Time_Min'], errors='coerce')
            df = df.fillna(0)
            # Filtra solo jugadores activos
            df = df[df['Playing Time_Min'] > 0]
        else:
            df = df.fillna(0)
            print("Advertencia: No se detectó 'Playing Time_Min' en la tabla. Ignorando filtro principal.")
            
        df = df.reset_index(drop=True)
        
        # Atributos: Metadata
        self.metadata = df[['nombre_jugador', 'team_name']].copy()
        
        # Validación de columnas
        missing_feats = [c for c in feature_cols if c not in df.columns]
        if missing_feats:
            raise ValueError(f"Las características requeridas no se encontraron en la fusión: {missing_feats}")
        if target_col not in df.columns:
            raise ValueError(f"Falta la columna dependiente Target '{target_col}'.")

        # 5. Normalización Min-Max Vectorizada y Tensores
        features_raw = df[feature_cols].values.astype(np.float32)
        X_min = features_raw.min(axis=0)
        X_max = features_raw.max(axis=0)
        
        # Normalización vectorizada manteniéndolo entre 0 y 1 (previene división por cero)
        self.features = (features_raw - X_min) / (X_max - X_min + 1e-8)
        self.targets = df[target_col].values.astype(np.float32)
        
    def __len__(self):
        """Retorna el tamaño total del dataset"""
        return len(self.features)

    def __getitem__(self, idx):
        """Retorna a cada iteración el tensor de X (características) y Y (target)"""
        return torch.tensor(self.features[idx]), torch.tensor(self.targets[idx])


if __name__ == "__main__":
    # Prueba Unitaria del Bloque Main
    DB_URL = "postgresql://postgres:Jk9oe@localhost:5432/itscoming_db"
    
    # Entradas del modelo
    feature_cols = ['Playing Time_Min', 'Total_Shots', 'Standard_SoT']
    
    # Objetivo
    target_col = 'Performance_Gls'
    
    print("Iniciando instanciación del Dataset Híbrido Pytorch...")
    try:
        dataset = FBrefPlayerDataset(db_url=DB_URL, target_col=target_col, feature_cols=feature_cols)
        
        print("\n=== RESUMEN TENSOR DATASET ===")
        print(f"Total de Registros Válidos: {len(dataset)}")
        
        if len(dataset) > 0:
            print("\n=== INSPECCIÓN DEL ÍNDICE 0 ===")
            if not dataset.metadata.empty:
                print(f"Metadatos Identitarios (Index 0):\n{dataset.metadata.iloc[0].to_dict()}")
            
            x, y = dataset[0]
            print(f"\n[X] Tensor de Variables (Features Normalizadas de 0-1):")
            print(f"[{', '.join(feature_cols)}]")
            print(x)
            print(f"\n[Y] Tensor Predictivo Target (Goles):")
            print(y)
    except Exception as e:
        print(f"\nError en prueba unitaria del Layer Machine Learning: {e}")
