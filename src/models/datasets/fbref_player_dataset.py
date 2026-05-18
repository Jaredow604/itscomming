import os
import glob
import torch
import pandas as pd
import numpy as np
from torch.utils.data import Dataset
from sqlalchemy import create_engine
from rapidfuzz import process, fuzz
import logging

import sys
import django

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
if not django.apps.apps.ready:
    django.setup()

from predicciones.entity_resolver import clean_team_name

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        logger.debug(f"Registros extraídos de DB (fbref_player_stats): {len(df_db)}")
        
        # 2. Carga de CSVs (Robusta)
        csv_pattern = os.path.join(data_dir, 'shooting_*.csv')
        csv_files = glob.glob(csv_pattern)
        
        if not csv_files:
            raise FileNotFoundError(f"No se encontraron archivos CSV con el patrón {csv_pattern}")
            
        df_csv_list = [pd.read_csv(f, header=1) for f in csv_files]
        df_csv = pd.concat(df_csv_list, ignore_index=True)
        
        df_csv = df_csv[df_csv['Player'] != 'Player']
        df_csv = df_csv.dropna(subset=['Player'])
        
        df_csv = df_csv.rename(columns={
            'Player': 'nombre_jugador',
            'Squad': 'team_name',
            'Sh': 'Total_Shots',
            'SoT': 'Standard_SoT'
        })
        
        df_csv['Total_Shots'] = pd.to_numeric(df_csv['Total_Shots'], errors='coerce').fillna(0)
        df_csv['Standard_SoT'] = pd.to_numeric(df_csv['Standard_SoT'], errors='coerce').fillna(0)
        
        logger.debug(f"Registros extraídos de CSV (shooting stats): {len(df_csv)}")
        
        # --- NUEVO: Resolución de Entidades con RapidFuzz ---
        logger.debug("Iniciando mapeo de entidades (Fuzzy Matching) con RapidFuzz...")
        db_names = df_db['nombre_jugador'].dropna().unique().tolist()
        csv_names = df_csv['nombre_jugador'].dropna().unique().tolist()
        
        mapping_dict = {}
        for csv_name in csv_names:
            # Buscamos la mejor coincidencia en la DB usando token_sort_ratio
            match = process.extractOne(
                csv_name, 
                db_names, 
                scorer=fuzz.token_sort_ratio, 
                score_cutoff=85.0
            )
            if match:
                mapping_dict[csv_name] = match[0]
                
        logger.debug(f"Matches exitosos con RapidFuzz (>85%): {len(mapping_dict)} de {len(csv_names)} jugadores únicos en CSV.")
        
        # Estandarizar la columna de nombres en el CSV
        df_csv['nombre_jugador'] = df_csv['nombre_jugador'].replace(mapping_dict)
        
        # --- NUEVO: Resolución de Entidades de Equipos con RapidFuzz + clean_team_name ---
        logger.debug("Iniciando mapeo de EQUIPOS (Fuzzy Matching + clean_team_name) con RapidFuzz...")
        db_teams = df_db['team_name'].dropna().unique().tolist()
        csv_teams = df_csv['team_name'].dropna().unique().tolist()
        df_csv['team_name'] = df_csv['team_name'].astype(str).apply(clean_team_name)
        df_db['team_name'] = df_db['team_name'].astype(str).apply(clean_team_name)
        
        # Pre-computar nombres limpios de la DB
        db_teams_clean = {clean_team_name(t): t for t in db_teams}
        db_cleaned_list = list(db_teams_clean.keys())
        
        team_mapping_dict = {}
        for csv_team in csv_teams:
            csv_team_clean = clean_team_name(csv_team)
            
            # Buscamos usando la versión limpia
            match = process.extractOne(
                csv_team_clean, 
                db_cleaned_list, 
                scorer=fuzz.token_sort_ratio, 
                score_cutoff=85.0
            )
            if match:
                clean_match = match[0]
                original_db_team = db_teams_clean[clean_match]
                team_mapping_dict[csv_team] = original_db_team
                
        logger.debug(f"Matches de equipos exitosos (>85% con limpieza): {len(team_mapping_dict)} de {len(csv_teams)} equipos únicos en CSV.")
        df_csv['team_name'] = df_csv['team_name'].replace(team_mapping_dict)
        
        # 3. Fusión (Merge) - Cambiado a LEFT JOIN
        df = pd.merge(df_db, df_csv, on=['nombre_jugador', 'team_name'], how='left')
        logger.debug(f"Registros tras el LEFT JOIN (DB + CSV): {len(df)}")
        
        # Manejo de Residuos: Eliminar aquellos que no cruzaron y tienen nulo en estadísticas clave
        # Ya que es LEFT JOIN, las stats que venían del CSV estarán nulas si no hizo match.
        nulos_tras_cruce = df['Total_Shots'].isna().sum()
        logger.debug(f"Residuos detectados tras el cruce (no superaron Fuzzy Match): {nulos_tras_cruce}")
        
        if nulos_tras_cruce > 0:
            df = df.dropna(subset=['Total_Shots', 'Standard_SoT'])
            logger.debug(f"Registros tras purgar residuos (dropna): {len(df)}")
            
        # 4. Limpieza Final
        if "Playing Time_Min" in df.columns:
            df['Playing Time_Min'] = pd.to_numeric(df['Playing Time_Min'], errors='coerce')
            
            # Count nulls before filling
            nulos_previos = df['Playing Time_Min'].isna().sum()
            logger.debug(f"Registros nulos detectados en 'Playing Time_Min': {nulos_previos}")
            
            # Instead of dropna, we fill with median or zero
            df = df.fillna(0)
            logger.debug(f"Registros tras limpieza de Nulos (fillna(0)): {len(df)}")
            
            # Filtro de jugadores activos (elimina los que tienen 0 min, o sea los nulos que rellenamos con 0)
            df = df[df['Playing Time_Min'] > 0]
            logger.debug(f"Registros efectivos (Playing Time > 0): {len(df)}")
        else:
            df = df.fillna(0)
            logger.debug("Advertencia: No se detectó 'Playing Time_Min' en la tabla. Ignorando filtro principal.")
            
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
