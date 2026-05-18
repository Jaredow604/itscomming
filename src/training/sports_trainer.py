"""
sports_trainer.py -- Bucle de Entrenamiento Profesional para Modelos Deportivos.

Este modulo implementa un SportsModelTrainer robusto y device-agnostic que
orquesta el entrenamiento de cualquier modelo de PyTorch de la plataforma
'It's Coming': NBAPredictor, MLBPredictor, PlayerPropNet, MatchPredictionNet, etc.

Caracteristicas Clave:
    - Device Agnostic: Detecta automaticamente CUDA, Apple MPS, o CPU.
    - AdamW + ReduceLROnPlateau: Optimizador con weight decay y LR scheduler
      adaptativo que reduce el learning rate cuando la validacion se estanca.
    - Early Stopping: Detiene el entrenamiento si no hay mejora en N epocas.
    - Checkpointing: Guarda los mejores pesos automaticamente cuando la
      validation loss alcanza un nuevo minimo historico.
    - Loss Injection: Acepta cualquier funcion de perdida inyectada por
      dependencia (NBAGaussianLoss, NegativeBinomialLoss, MSELoss, etc).
    - Gradient Clipping: Evita explosion de gradientes en redes profundas.

Flujo de Entrenamiento:
    for epoch in epochs:
        1. model.train()  -> forward -> loss -> backward -> step (train)
        2. model.eval()   -> forward -> loss (val, sin gradientes)
        3. ReduceLROnPlateau.step(val_loss)
        4. if val_loss < best -> save checkpoint
        5. if no improvement for patience epochs -> early stop
"""

import copy
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

logger = logging.getLogger(__name__)


# ==========================================
# CONFIGURACION DEL ENTRENAMIENTO
# ==========================================

@dataclass
class TrainerConfig:
    """
    Configuracion completa del bucle de entrenamiento.

    Attributes:
        epochs: Numero maximo de epocas de entrenamiento.
        learning_rate: Tasa de aprendizaje inicial para AdamW.
        weight_decay: Regularizacion L2 de AdamW (penaliza pesos grandes).
        patience: Numero de epocas sin mejora antes de Early Stopping.
        min_delta: Mejora minima requerida para considerar progreso.
        grad_clip_norm: Norma maxima para gradient clipping (None = desactivado).
        checkpoint_dir: Directorio donde guardar los checkpoints.
        checkpoint_name: Nombre del archivo del mejor checkpoint.
        scheduler_factor: Factor de reduccion del LR (new_lr = old_lr * factor).
        scheduler_patience: Epocas sin mejora antes de reducir el LR.
        log_every_n: Frecuencia de logging (cada N epocas). 1 = cada epoca.
    """
    epochs: int = 100
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    patience: int = 15
    min_delta: float = 1e-5
    grad_clip_norm: Optional[float] = 1.0
    checkpoint_dir: str = 'checkpoints'
    checkpoint_name: str = 'best_model_weights.pth'
    scheduler_factor: float = 0.5
    scheduler_patience: int = 7
    log_every_n: int = 1


# ==========================================
# DETECCION AUTOMATICA DE DISPOSITIVO
# ==========================================

def detect_device() -> torch.device:
    """
    Detecta automaticamente el mejor dispositivo disponible.

    Prioridad: CUDA (NVIDIA GPU) > MPS (Apple Silicon) > CPU.

    Returns:
        torch.device configurado para el hardware detectado.
    """
    if torch.cuda.is_available():
        device = torch.device('cuda')
        gpu_name = torch.cuda.get_device_name(0)
        logger.info("GPU detectada: %s (CUDA)", gpu_name)
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        device = torch.device('mps')
        logger.info("Apple Silicon detectado (MPS)")
    else:
        device = torch.device('cpu')
        logger.info("No se detecto GPU. Usando CPU.")

    return device


# ==========================================
# TRAINER PRINCIPAL
# ==========================================

class SportsModelTrainer:
    """
    Motor de entrenamiento profesional para modelos deportivos de PyTorch.

    Soporta cualquier combinacion de modelo + loss function mediante inyeccion
    de dependencias. Para loss functions con firmas no estandar (como
    NBAGaussianLoss o NegativeBinomialLoss que reciben diccionarios), se
    utiliza un callable `loss_fn` que encapsula la logica de desempaquetado.

    Example (Standard Loss - MSELoss, CrossEntropyLoss):
        >>> model = PlayerPropNet(input_dim=3)
        >>> criterion = nn.MSELoss()
        >>> trainer = SportsModelTrainer(model, criterion)
        >>> history = trainer.fit(train_loader, val_loader)

    Example (Custom Loss - NBAGaussianLoss):
        >>> model = NBAPredictor()
        >>> criterion = NBAGaussianLoss()
        >>> def nba_loss_fn(preds, targets):
        ...     spread = targets[:, 0:1]
        ...     total = targets[:, 1:2]
        ...     return criterion(preds, spread, total)
        >>> trainer = SportsModelTrainer(model, nba_loss_fn)
        >>> history = trainer.fit(train_loader, val_loader)

    Attributes:
        model: Modelo nn.Module ya movido al dispositivo.
        criterion: Funcion de perdida (nn.Module o callable).
        optimizer: AdamW configurado con weight decay.
        scheduler: ReduceLROnPlateau vinculado al optimizador.
        device: Dispositivo de computo (cuda/mps/cpu).
        config: Dataclass con todos los hiperparametros.
    """

    def __init__(
        self,
        model: nn.Module,
        criterion: Any,
        config: Optional[TrainerConfig] = None,
        device: Optional[torch.device] = None,
    ) -> None:
        """
        Inicializa el trainer, mueve el modelo al dispositivo y configura
        el optimizador y el scheduler.

        Args:
            model: Instancia de nn.Module (NBAPredictor, MLBPredictor, etc).
            criterion: Funcion de perdida. Puede ser nn.Module o un callable
                       con firma (predictions, targets) -> loss_tensor.
            config: Configuracion del entrenamiento. None usa defaults.
            device: Dispositivo de computo. None = auto-detectar.
        """
        self.config = config or TrainerConfig()
        self.device = device or detect_device()

        # Mover modelo al dispositivo
        self.model = model.to(self.device)
        self.criterion = criterion
        if isinstance(criterion, nn.Module):
            self.criterion = criterion.to(self.device)

        # Optimizador: AdamW (Adam con weight decay desacoplado)
        # Weight decay penaliza pesos grandes, actuando como regularizacion L2
        # pero correctamente desacoplada del gradiente (a diferencia de L2 en Adam).
        self.optimizer = optim.AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )

        # Scheduler: Reduce el LR cuando la val_loss se estanca
        # Esto permite convergencia fina en las ultimas epocas.
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer,
            mode='min',
            factor=self.config.scheduler_factor,
            patience=self.config.scheduler_patience,
        )

        # Estado interno
        self._best_val_loss: float = float('inf')
        self._best_model_state: Optional[Dict] = None
        self._epochs_without_improvement: int = 0
        self._history: Dict[str, List[float]] = {
            'train_loss': [],
            'val_loss': [],
            'lr': [],
        }

        # Crear directorio de checkpoints
        os.makedirs(self.config.checkpoint_dir, exist_ok=True)

        logger.info(
            "SportsModelTrainer inicializado | Device: %s | LR: %.1e | "
            "Weight Decay: %.1e | Patience: %d | Epochs: %d",
            self.device, self.config.learning_rate, self.config.weight_decay,
            self.config.patience, self.config.epochs,
        )

    def _get_current_lr(self) -> float:
        """Retorna el learning rate actual del optimizador."""
        return self.optimizer.param_groups[0]['lr']

    def _compute_loss(
        self, predictions: Any, targets: torch.Tensor
    ) -> torch.Tensor:
        """
        Calcula la perdida de manera flexible.

        Soporta tanto loss functions estandar (MSELoss, CrossEntropy)
        como las custom de la plataforma (NBAGaussianLoss, NegBinLoss).
        El criterion puede ser un nn.Module o un callable arbitrario.

        Args:
            predictions: Salida del modelo (tensor o dict de tensores).
            targets: Tensor de targets del DataLoader.

        Returns:
            Tensor escalar con la perdida.
        """
        return self.criterion(predictions, targets)

    def _train_one_epoch(self, train_loader: DataLoader) -> float:
        """
        Ejecuta una epoca completa de entrenamiento.

        Args:
            train_loader: DataLoader con datos de entrenamiento.

        Returns:
            Perdida promedio de la epoca.
        """
        self.model.train()
        running_loss = 0.0
        num_batches = 0

        for inputs, targets in train_loader:
            inputs = inputs.to(self.device)
            targets = targets.to(self.device)

            # Zero gradients
            self.optimizer.zero_grad(set_to_none=True)

            # Forward pass
            predictions = self.model(inputs)

            # Loss
            loss = self._compute_loss(predictions, targets)

            # Backward pass
            loss.backward()

            # Gradient clipping (previene explosion de gradientes)
            if self.config.grad_clip_norm is not None:
                nn.utils.clip_grad_norm_(
                    self.model.parameters(),
                    max_norm=self.config.grad_clip_norm,
                )

            # Optimizer step
            self.optimizer.step()

            running_loss += loss.item()
            num_batches += 1

        return running_loss / max(num_batches, 1)

    @torch.no_grad()
    def _validate_one_epoch(self, val_loader: DataLoader) -> float:
        """
        Ejecuta una epoca completa de validacion (sin gradientes).

        Args:
            val_loader: DataLoader con datos de validacion.

        Returns:
            Perdida promedio de validacion.
        """
        self.model.eval()
        running_loss = 0.0
        num_batches = 0

        for inputs, targets in val_loader:
            inputs = inputs.to(self.device)
            targets = targets.to(self.device)

            predictions = self.model(inputs)
            loss = self._compute_loss(predictions, targets)

            running_loss += loss.item()
            num_batches += 1

        return running_loss / max(num_batches, 1)

    def _save_checkpoint(self, epoch: int, val_loss: float) -> None:
        """
        Guarda los pesos del modelo cuando se alcanza un nuevo minimo de val_loss.

        Args:
            epoch: Numero de epoca actual.
            val_loss: Perdida de validacion actual.
        """
        checkpoint_path = os.path.join(
            self.config.checkpoint_dir,
            self.config.checkpoint_name,
        )

        checkpoint = {
            'epoch': epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'scheduler_state_dict': self.scheduler.state_dict(),
            'val_loss': val_loss,
            'config': self.config,
        }

        torch.save(checkpoint, checkpoint_path)
        logger.info(
            "  [CHECKPOINT] Nuevo mejor modelo guardado (val_loss=%.6f) -> %s",
            val_loss, checkpoint_path,
        )

    def _check_early_stopping(self, val_loss: float) -> bool:
        """
        Verifica si se debe activar Early Stopping.

        Args:
            val_loss: Perdida de validacion de la epoca actual.

        Returns:
            True si se debe detener el entrenamiento.
        """
        if val_loss < (self._best_val_loss - self.config.min_delta):
            # Mejora significativa detectada
            self._best_val_loss = val_loss
            self._best_model_state = copy.deepcopy(self.model.state_dict())
            self._epochs_without_improvement = 0
            return False
        else:
            # Sin mejora
            self._epochs_without_improvement += 1
            if self._epochs_without_improvement >= self.config.patience:
                logger.info(
                    "  [EARLY STOP] Sin mejora en %d epocas. Deteniendo entrenamiento.",
                    self.config.patience,
                )
                return True
            return False

    def fit(
        self,
        train_loader: DataLoader,
        val_loader: Optional[DataLoader] = None,
    ) -> Dict[str, List[float]]:
        """
        Ejecuta el bucle completo de entrenamiento.

        Args:
            train_loader: DataLoader con datos de entrenamiento.
            val_loader: DataLoader con datos de validacion (opcional pero
                        recomendado para Early Stopping y checkpointing).

        Returns:
            Diccionario con el historial de metricas:
                'train_loss': Lista de perdidas de entrenamiento por epoca.
                'val_loss': Lista de perdidas de validacion por epoca.
                'lr': Lista de learning rates por epoca.
        """
        total_start = time.time()
        logger.info(
            "=" * 60 + "\n"
            "  INICIANDO ENTRENAMIENTO\n"
            "  Modelo: %s | Epochs: %d | Device: %s\n" +
            "=" * 60,
            self.model.__class__.__name__,
            self.config.epochs,
            self.device,
        )

        try:
            for epoch in range(1, self.config.epochs + 1):
                epoch_start = time.time()

                # --- Fase 1: Entrenamiento ---
                train_loss = self._train_one_epoch(train_loader)
                self._history['train_loss'].append(train_loss)

                # --- Fase 2: Validacion ---
                val_loss = float('inf')
                if val_loader is not None:
                    val_loss = self._validate_one_epoch(val_loader)
                    self._history['val_loss'].append(val_loss)

                    # Scheduler step (basado en val_loss)
                    self.scheduler.step(val_loss)
                else:
                    # Sin validacion, usamos train_loss para el scheduler
                    self.scheduler.step(train_loss)

                # Registrar LR actual
                current_lr = self._get_current_lr()
                self._history['lr'].append(current_lr)

                # --- Logging ---
                epoch_time = time.time() - epoch_start
                if epoch % self.config.log_every_n == 0 or epoch == 1:
                    if val_loader is not None:
                        logger.info(
                            "Epoch %03d/%d | Train: %.6f | Val: %.6f | "
                            "LR: %.2e | %.1fs",
                            epoch, self.config.epochs,
                            train_loss, val_loss,
                            current_lr, epoch_time,
                        )
                    else:
                        logger.info(
                            "Epoch %03d/%d | Train: %.6f | LR: %.2e | %.1fs",
                            epoch, self.config.epochs,
                            train_loss, current_lr, epoch_time,
                        )

                # --- Fase 3: Checkpointing + Early Stopping ---
                if val_loader is not None:
                    should_stop = self._check_early_stopping(val_loss)
                    if val_loss <= self._best_val_loss:
                        self._save_checkpoint(epoch, val_loss)
                    if should_stop:
                        break

        except KeyboardInterrupt:
            logger.warning("Entrenamiento interrumpido manualmente (Ctrl+C).")

        except Exception as exc:
            logger.error(
                "Error critico durante el entrenamiento: %s",
                exc, exc_info=True,
            )
            raise

        # --- Resultado Final ---
        total_time = time.time() - total_start
        epochs_ran = len(self._history['train_loss'])

        logger.info(
            "\n" + "=" * 60 + "\n"
            "  ENTRENAMIENTO FINALIZADO\n"
            "  Epocas completadas: %d | Tiempo total: %.1fs\n"
            "  Mejor Val Loss: %.6f\n" +
            "=" * 60,
            epochs_ran, total_time, self._best_val_loss,
        )

        # Restaurar los mejores pesos al modelo
        if self._best_model_state is not None:
            self.model.load_state_dict(self._best_model_state)
            logger.info("Mejores pesos restaurados al modelo en memoria.")

        return self._history

    def load_checkpoint(self, path: Optional[str] = None) -> None:
        """
        Carga un checkpoint guardado previamente.

        Args:
            path: Ruta al archivo .pth. None usa el path default.
        """
        if path is None:
            path = os.path.join(
                self.config.checkpoint_dir,
                self.config.checkpoint_name,
            )

        if not os.path.exists(path):
            raise FileNotFoundError(f"Checkpoint no encontrado: {path}")

        checkpoint = torch.load(path, map_location=self.device, weights_only=False)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.scheduler.load_state_dict(checkpoint['scheduler_state_dict'])
        self._best_val_loss = checkpoint.get('val_loss', float('inf'))

        logger.info(
            "Checkpoint cargado desde '%s' (epoch %d, val_loss=%.6f)",
            path, checkpoint.get('epoch', -1), self._best_val_loss,
        )


# ==========================================
# PRUEBA UNITARIA STANDALONE
# ==========================================
if __name__ == "__main__":
    import numpy as np
    from torch.utils.data import TensorDataset

    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

    print("=" * 60)
    print("  PRUEBA: SportsModelTrainer")
    print("=" * 60)

    # --- Crear datos sinteticos ---
    np.random.seed(42)
    torch.manual_seed(42)

    N = 200
    X = torch.randn(N, 3)
    # Target = combinacion lineal + ruido (regression simple)
    y = (X[:, 0] * 2.0 + X[:, 1] * 0.5 - X[:, 2] * 1.5 + torch.randn(N) * 0.3)
    y = y.unsqueeze(1)  # [N, 1]

    # Split 80/20
    split = int(N * 0.8)
    train_ds = TensorDataset(X[:split], y[:split])
    val_ds = TensorDataset(X[split:], y[split:])

    train_loader = DataLoader(train_ds, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=32)

    # --- Modelo simple para test ---
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from src.models.networks.player_prop_net import PlayerPropNet

    model = PlayerPropNet(input_dim=3)
    criterion = nn.MSELoss()

    # --- Entrenar ---
    config = TrainerConfig(
        epochs=30,
        learning_rate=1e-3,
        patience=10,
        checkpoint_dir='checkpoints',
        checkpoint_name='test_trainer_best.pth',
        log_every_n=5,
    )

    trainer = SportsModelTrainer(model, criterion, config=config)
    history = trainer.fit(train_loader, val_loader)

    print(f"\nHistorial: {len(history['train_loss'])} epocas registradas.")
    print(f"Mejor Val Loss: {min(history['val_loss']):.6f}")
    print(f"LR final: {history['lr'][-1]:.2e}")
