import torch
from torch.utils.data import Dataset
import pandas as pd
import numpy as np

import sys
import os
import django

# Inicializar Django
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from predicciones.models import Partido

class MatchDataset(Dataset):
    """
    Dataset paramétrico de Pytorch que une Equipos y Partidos.
    Alimenta una red neuronal para predecir Moneyline basado en la sinergia de métricas de ambos lados.
    """
    def __init__(self):
        self.features = []
        self.targets = []
        self.metadata = None

        self._load_and_process_data()

    def _load_and_process_data(self):
        try:
            # Query the database
            partidos = Partido.objects.filter(
                jugado=True, 
                goles_local__isnull=False, 
                goles_visitante__isnull=False
            ).select_related('local', 'visitante')
            
            data = []
            for p in partidos:
                data.append({
                    'l_goles': float(p.local.prom_goles),
                    'l_tiros': float(p.local.prom_tiros_puerta),
                    'l_corners': float(p.local.prom_corners),
                    'v_goles': float(p.visitante.prom_goles),
                    'v_tiros': float(p.visitante.prom_tiros_puerta),
                    'v_corners': float(p.visitante.prom_corners),
                    'goles_local': p.goles_local,
                    'goles_visitante': p.goles_visitante,
                    'local_nombre': p.local.nombre,
                    'visita_nombre': p.visitante.nombre
                })
            df = pd.DataFrame(data)
            
            # Fallback a Dummy Data si no hay partidos jugados
            if df.empty:
                raise ValueError("ADVERTENCIA: No se encontraron partidos jugados en la base de datos. El Pipeline requiere datos reales.")
                
            self.metadata = df[['local_nombre', 'visita_nombre']].copy()
            
            # Codificación del Target (Moneyline: 0=Empate, 1=Local, 2=Visita)
            conditions = [
                (df['goles_local'] > df['goles_visitante']),
                (df['goles_local'] < df['goles_visitante'])
            ]
            choices = [1, 2]
            df['target'] = np.select(conditions, choices, default=0)
            
            # Normalización Min-Max de los Features Vector (6 Dimensiones)
            feature_cols = ['l_goles', 'l_tiros', 'l_corners', 'v_goles', 'v_tiros', 'v_corners']
            
            x_data = df[feature_cols].copy()
            for col in feature_cols:
                min_val = x_data[col].min()
                max_val = x_data[col].max()
                if max_val > min_val:
                    x_data[col] = (x_data[col] - min_val) / (max_val - min_val)
                else:
                    x_data[col] = 0.0

            # Convertir a Tensores PyTorch
            self.features = torch.tensor(x_data.values, dtype=torch.float32)
            self.targets = torch.tensor(df['target'].values, dtype=torch.long)
            
            print(f"MatchDataset construido exitosamente con {len(self.targets)} partidos.")
            
        except Exception as e:
            print(f"Error critico extrayendo tensores de partidos: {e}")

    def __len__(self):
        return len(self.targets)

    def __getitem__(self, idx):
        return self.features[idx], self.targets[idx]

if __name__ == "__main__":
    dataset = MatchDataset()
    if len(dataset) > 0:
        x, y = dataset[0]
        print(f"Dimensiones de X (Características): {x.shape} (Esperado: 6)")
        print(f"Dimensión de Objetivo (Target): {y} (Clase Moneyline)")
