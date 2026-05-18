"""
inference_ready_dataset.py — Puente de Inyección de Datos para Modelos Predictivos (Poisson / Elo).

Este módulo conecta la tabla 'ml_inference_ready_player_data' de PostgreSQL
(que contiene vectores ya normalizados con RobustScaler) directamente con el
motor de entrenamiento e inferencia de PyTorch.

Flujo de Inyección:
    ┌──────────────┐     pd.read_sql      ┌───────────┐     torch.tensor     ┌──────────────┐
    │  PostgreSQL  │ ──────────────────► │  Pandas   │ ──────────────────► │   PyTorch    │
    │  (SQLAlchemy)│     (vectorizado)    │ DataFrame │     (float32)       │   Tensores   │
    └──────────────┘                      └───────────┘                     └──────────────┘

Decisiones de Diseño:
    - Se utiliza `pd.read_sql` en lugar de iterar con el ORM para aprovechar la
      lectura vectorizada columnar de Pandas, logrando O(N) de lectura bulk en
      lugar del O(N) iterativo del ORM (que además tiene overhead de instanciación).
    - Los tensores se pre-computan en `__init__` como `torch.float32`, por lo que
      cada llamada a `__getitem__` opera en O(1) con slicing directo de tensores,
      sin conversiones ni copias adicionales durante el loop de entrenamiento.
"""

import logging
from typing import List, Optional, Tuple

import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ==========================================
# CONSTANTES DE CONFIGURACIÓN DEL DATASET
# ==========================================

# Columnas de features normalizadas en la tabla InferenceReadyPlayerData
DEFAULT_FEATURE_COLUMNS: List[str] = [
    'playing_time_min_scaled',
    'total_shots_scaled',
    'standard_sot_scaled',
]

# Columna objetivo (target) para los modelos predictivos
DEFAULT_TARGET_COLUMN: str = 'performance_gls'

# Nombre de la tabla origen en PostgreSQL
TABLE_NAME: str = 'ml_inference_ready_player_data'


class InferenceReadyDataset(Dataset):
    """
    Dataset de PyTorch que extrae datos pre-normalizados desde PostgreSQL.

    Lee la tabla `ml_inference_ready_player_data` a través de una sesión de
    SQLAlchemy, vectoriza la extracción con Pandas y almacena los tensores
    resultantes en memoria para garantizar acceso O(1) durante el entrenamiento.

    Attributes:
        features (torch.Tensor): Tensor 2D [N, num_features] con las métricas
                                 normalizadas. Dtype: torch.float32.
        targets (torch.Tensor):  Tensor 1D [N] con los valores objetivo.
                                 Dtype: torch.float32.
        metadata (pd.DataFrame): DataFrame auxiliar con columnas de identidad
                                 (player_name, team_name) para trazabilidad.

    Example:
        >>> from database import SessionLocal
        >>> session = SessionLocal()
        >>> dataset = InferenceReadyDataset(db_session=session)
        >>> x, y = dataset[0]
        >>> print(x.shape, y.shape)
        torch.Size([3]) torch.Size([])
    """

    def __init__(
        self,
        db_session: Session,
        feature_columns: Optional[List[str]] = None,
        target_column: Optional[str] = None,
    ) -> None:
        """
        Inicializa el Dataset extrayendo datos de PostgreSQL y convirtiéndolos
        a tensores de PyTorch en una sola pasada vectorizada.

        Args:
            db_session: Sesión activa de SQLAlchemy conectada a PostgreSQL.
            feature_columns: Lista de nombres de columnas a usar como features.
                             Si es None, usa DEFAULT_FEATURE_COLUMNS.
            target_column: Nombre de la columna objetivo. Si es None, usa
                           DEFAULT_TARGET_COLUMN.

        Raises:
            ValueError: Si la tabla está vacía o faltan columnas requeridas.
            RuntimeError: Si la conexión a la base de datos falla.
        """
        super().__init__()

        self._feature_columns = feature_columns or DEFAULT_FEATURE_COLUMNS
        self._target_column = target_column or DEFAULT_TARGET_COLUMN

        # --- PASO 1: Extracción Vectorizada desde PostgreSQL ---
        logger.info(
            "Extrayendo datos de '%s' vía pd.read_sql (lectura vectorizada)...",
            TABLE_NAME,
        )

        try:
            # Seleccionar solo las columnas necesarias para minimizar I/O
            columns_needed = (
                ['player_name', 'team_name']
                + self._feature_columns
                + [self._target_column]
            )
            query = text(
                f"SELECT {', '.join(columns_needed)} FROM {TABLE_NAME}"
            )

            # pd.read_sql aprovecha el cursor de dbapi para leer en bloques
            # columnar, mucho más eficiente que iterar instancias ORM.
            df = pd.read_sql(query, db_session.bind)

        except Exception as exc:
            logger.error("Error crítico al leer la tabla '%s': %s", TABLE_NAME, exc)
            raise RuntimeError(
                f"No se pudo extraer datos de '{TABLE_NAME}'. "
                f"Verifica la conexión y que la tabla exista."
            ) from exc

        # --- PASO 2: Validación de Integridad ---
        if df.empty:
            raise ValueError(
                f"La tabla '{TABLE_NAME}' está vacía. "
                "Ejecuta el pipeline de normalización (tasks.py) primero."
            )

        missing_features = [c for c in self._feature_columns if c not in df.columns]
        if missing_features:
            raise ValueError(
                f"Columnas de features faltantes en '{TABLE_NAME}': {missing_features}"
            )

        if self._target_column not in df.columns:
            raise ValueError(
                f"Columna target '{self._target_column}' no encontrada en '{TABLE_NAME}'."
            )

        # Eliminar filas con target nulo (no podemos entrenar sin ground truth)
        rows_before = len(df)
        df = df.dropna(subset=[self._target_column])
        rows_dropped = rows_before - len(df)
        if rows_dropped > 0:
            logger.warning(
                "Se eliminaron %d registros con target nulo (de %d totales).",
                rows_dropped,
                rows_before,
            )

        # Rellenar features nulos con 0.0 (fallback seguro post-normalización)
        null_counts = df[self._feature_columns].isnull().sum()
        total_nulls = null_counts.sum()
        if total_nulls > 0:
            logger.warning(
                "Se detectaron %d valores nulos en features. Imputando con 0.0.",
                total_nulls,
            )
            df[self._feature_columns] = df[self._feature_columns].fillna(0.0)

        # --- PASO 3: Metadata de Trazabilidad ---
        self.metadata: pd.DataFrame = df[['player_name', 'team_name']].reset_index(
            drop=True
        )

        # --- PASO 4: Conversión a Tensores (O(1) en __getitem__) ---
        # .values retorna un ndarray contiguo en C-order, ideal para torch.from_numpy
        features_array = df[self._feature_columns].values.astype('float32')
        targets_array = df[self._target_column].values.astype('float32')

        self.features: torch.Tensor = torch.from_numpy(features_array)
        self.targets: torch.Tensor = torch.from_numpy(targets_array)

        logger.info(
            "InferenceReadyDataset construido: %d registros | "
            "Features shape: %s | Target shape: %s",
            len(self.features),
            list(self.features.shape),
            list(self.targets.shape),
        )

    def __len__(self) -> int:
        """Retorna el número total de muestras en el dataset."""
        return self.features.shape[0]

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Retorna la muestra en la posición `idx`.

        Como los tensores ya están pre-computados en __init__, esta operación
        es un slicing O(1) sin copias de memoria adicionales.

        Args:
            idx: Índice de la muestra (0-indexed).

        Returns:
            Tupla (features_tensor, target_tensor) ambos en torch.float32.
        """
        return self.features[idx], self.targets[idx]

    def __repr__(self) -> str:
        return (
            f"InferenceReadyDataset("
            f"samples={len(self)}, "
            f"features={self._feature_columns}, "
            f"target='{self._target_column}')"
        )


# ==========================================
# FUNCIÓN AUXILIAR DE DATALOADER
# ==========================================

def prepare_dataloaders(
    db_session: Session,
    batch_size: int = 32,
    shuffle: bool = True,
    num_workers: int = 0,
    feature_columns: Optional[List[str]] = None,
    target_column: Optional[str] = None,
) -> Tuple[InferenceReadyDataset, DataLoader]:
    """
    Función de conveniencia que instancia el Dataset y retorna un DataLoader
    configurado y listo para inyectar en el loop de entrenamiento de PyTorch.

    Args:
        db_session: Sesión activa de SQLAlchemy.
        batch_size: Tamaño de cada mini-batch. Default: 32.
        shuffle: Si True, aleatoriza el orden de las muestras en cada epoch.
                 Esencial para entrenamiento; False para inferencia.
        num_workers: Número de subprocesos para carga paralela de datos.
                     En Windows, se recomienda 0 para evitar problemas con
                     multiprocessing y fork().
        feature_columns: Override de columnas de features. None usa las default.
        target_column: Override de columna target. None usa la default.

    Returns:
        Tupla (dataset, dataloader):
            - dataset: Instancia de InferenceReadyDataset (útil para inspección).
            - dataloader: DataLoader de PyTorch configurado.

    Example:
        >>> from database import SessionLocal
        >>> session = SessionLocal()
        >>> dataset, loader = prepare_dataloaders(session, batch_size=64)
        >>> for x_batch, y_batch in loader:
        ...     predictions = model(x_batch)
        ...     loss = criterion(predictions, y_batch)
    """
    logger.info(
        "Preparando DataLoader (batch_size=%d, shuffle=%s, num_workers=%d)...",
        batch_size,
        shuffle,
        num_workers,
    )

    dataset = InferenceReadyDataset(
        db_session=db_session,
        feature_columns=feature_columns,
        target_column=target_column,
    )

    dataloader = DataLoader(
        dataset=dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available(),  # Acelera transfers GPU si disponible
        drop_last=False,  # No descartar el último batch incompleto
    )

    logger.info(
        "DataLoader listo: %d batches de tamaño %d.",
        len(dataloader),
        batch_size,
    )

    return dataset, dataloader


# ==========================================
# PRUEBA UNITARIA STANDALONE
# ==========================================
if __name__ == "__main__":
    import sys
    import os

    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
    from database import SessionLocal

    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')

    print("=" * 60)
    print("  PRUEBA: InferenceReadyDataset + DataLoader")
    print("=" * 60)

    session = SessionLocal()

    try:
        dataset, loader = prepare_dataloaders(
            db_session=session,
            batch_size=16,
            shuffle=True,
            num_workers=0,
        )

        print(f"\n{dataset}")
        print(f"Total de muestras: {len(dataset)}")

        if len(dataset) > 0:
            # Inspección del primer registro
            x, y = dataset[0]
            print(f"\n--- Inspección del Índice 0 ---")
            print(f"Metadata: {dataset.metadata.iloc[0].to_dict()}")
            print(f"Features (tensor): {x}")
            print(f"Target   (tensor): {y}")
            print(f"Features dtype:    {x.dtype}")
            print(f"Target dtype:      {y.dtype}")

            # Simular un mini-batch de entrenamiento
            print(f"\n--- Simulación de 1 Mini-Batch ---")
            for batch_x, batch_y in loader:
                print(f"Batch X shape: {batch_x.shape}")
                print(f"Batch Y shape: {batch_y.shape}")
                break  # Solo el primer batch

    except Exception as e:
        print(f"\nError en prueba: {e}")
    finally:
        session.close()
        print("\nSesión de SQLAlchemy cerrada correctamente.")
