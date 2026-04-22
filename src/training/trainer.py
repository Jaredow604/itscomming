import logging
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from typing import Optional

logger = logging.getLogger(__name__)

class Trainer:
    """
    Bucle de entrenamiento orquestado e independiente.
    Inyección de Dependencias de: modelo, optimizador, criterio y dispositivo.
    """
    
    def __init__(
        self,
        model: nn.Module,
        optimizer: optim.Optimizer,
        criterion: nn.Module,
        device: torch.device
    ):
        self.model = model.to(device)
        self.optimizer = optimizer
        self.criterion = criterion
        self.device = device

    def train_epoch(self, dataloader: DataLoader) -> float:
        self.model.train()
        running_loss = 0.0
        
        for batch_idx, (inputs, targets) in enumerate(dataloader):
            try:
                inputs, targets = inputs.to(self.device), targets.to(self.device)
                
                self.optimizer.zero_grad()
                outputs = self.model(inputs)
                
                loss = self.criterion(outputs, targets)
                
                loss.backward()
                self.optimizer.step()
                
                running_loss += loss.item()
                
            except Exception as e:
                logger.error(f"Error mortal en Batch {batch_idx}: {e}")
                raise
                
        return running_loss / len(dataloader)

    def evaluate(self, dataloader: DataLoader) -> float:
        self.model.eval()
        running_loss = 0.0
        
        with torch.no_grad():
            for inputs, targets in dataloader:
                inputs, targets = inputs.to(self.device), targets.to(self.device)
                outputs = self.model(inputs)
                loss = self.criterion(outputs, targets)
                running_loss += loss.item()
                
        return running_loss / len(dataloader)

    def fit(self, train_loader: DataLoader, val_loader: Optional[DataLoader], epochs: int) -> None:
        logger.info(f"Inicializando rutina de entrenamiento... [{epochs} epochs | Dispositivo: {self.device}]")
        
        try:
            for epoch in range(1, epochs + 1):
                train_loss = self.train_epoch(train_loader)
                
                if val_loader:
                    val_loss = self.evaluate(val_loader)
                    logger.info(
                        f"Epoch {epoch:03d}/{epochs} | "
                        f"Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f}"
                    )
                else:
                    logger.info(f"Epoch {epoch:03d}/{epochs} | Train Loss: {train_loss:.4f}")
                    
        except KeyboardInterrupt:
            logger.warning("Entrenamiento interrumpido manualmente por el analista.")
        except Exception as e:
            logger.error(f"Rotura inesperada durante el bucle de entrenamiento: {e}")
            raise
            
        logger.info("Fase de modelado en Trainer concluida de manera exitosa.")
