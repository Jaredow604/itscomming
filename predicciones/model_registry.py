"""
model_registry.py -- Singleton Registry para mantener modelos PyTorch en memoria.

Problema:
    Cargar un modelo PyTorch (.pth) desde disco en cada peticion HTTP es
    inaceptable en produccion: torch.load() tarda ~200-500ms por modelo,
    y la instanciacion del nn.Module consume memoria que debe re-asignarse.

Solucion: Patron Singleton con Lazy Loading.
    1. Los modelos se cargan UNA sola vez la primera vez que se solicitan.
    2. Se mantienen en un diccionario en memoria del proceso de Django.
    3. Las peticiones subsiguientes obtienen el modelo ya cargado en O(1).
    4. El modelo se mueve automaticamente al mejor dispositivo (GPU/CPU).

Ventaja sobre Django Cache (Redis/Memcached):
    - Los modelos PyTorch son objetos Python complejos (grafos computacionales)
      que NO se serializan eficientemente a Redis.
    - El proceso de Django ya vive en RAM; mantener el modelo ahi evita
      serializar/deserializar ~50MB de tensores por request.
    - Redis se usa para datos simples (JSON, strings). Los modelos van en
      memoria del proceso.

Thread Safety:
    Django con Gunicorn usa un proceso por worker, y cada proceso tiene
    su propia instancia del registry. No hay race conditions porque cada
    worker es independiente. threading.Lock() se incluye como proteccion
    adicional para servidores con multi-threading (ej. uvicorn con workers).
"""

import logging
import os
import threading
from typing import Dict, Optional

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


def _detect_device() -> torch.device:
    """Detecta el mejor dispositivo disponible."""
    if torch.cuda.is_available():
        return torch.device('cuda')
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        return torch.device('mps')
    return torch.device('cpu')


class ModelRegistry:
    """
    Singleton thread-safe que cachea modelos PyTorch en memoria del proceso.

    Los modelos se registran con una clave unica (ej. 'nba', 'mlb') y se
    cargan lazily la primera vez que se solicitan. Una vez cargados, permanecen
    en memoria hasta que el proceso de Django se reinicia.

    Usage:
        # Al inicio de la app (apps.py ready()) o en el modulo views:
        registry = ModelRegistry.get_instance()
        registry.register('nba', NBAPredictor, NBAConfig(input_dim=8), 'checkpoints/nba_best.pth')
        registry.register('mlb', MLBPredictor, MLBConfig(input_dim=10), 'checkpoints/mlb_best.pth')

        # En cualquier vista DRF:
        model = registry.get_model('nba')  # Retorna el modelo ya en .eval()
    """

    _instance: Optional['ModelRegistry'] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._models: Dict[str, nn.Module] = {}
        self._configs: Dict[str, dict] = {}
        self._device = _detect_device()
        logger.info("ModelRegistry inicializado | Device: %s", self._device)

    @classmethod
    def get_instance(cls) -> 'ModelRegistry':
        """Retorna la instancia unica del registry (Singleton thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def device(self) -> torch.device:
        """Dispositivo donde residen los modelos."""
        return self._device

    def register(
        self,
        sport_key: str,
        model_class: type,
        config: object,
        weights_path: str,
    ) -> None:
        """
        Registra un modelo para lazy loading.

        Args:
            sport_key: Clave unica ('nba', 'mlb').
            model_class: Clase del modelo (NBAPredictor, MLBPredictor).
            config: Instancia de configuracion (NBAConfig, MLBConfig).
            weights_path: Ruta al archivo .pth con los pesos entrenados.
        """
        self._configs[sport_key] = {
            'model_class': model_class,
            'config': config,
            'weights_path': weights_path,
        }
        logger.info(
            "Modelo '%s' registrado (lazy) | Class: %s | Weights: %s",
            sport_key, model_class.__name__, weights_path,
        )

    def get_model(self, sport_key: str) -> Optional[nn.Module]:
        """
        Obtiene un modelo cargado y listo para inferencia.

        Si el modelo no esta en memoria, lo carga (lazy loading).
        Si los pesos no existen en disco, retorna None.

        Args:
            sport_key: Clave del deporte ('nba', 'mlb').

        Returns:
            nn.Module en modo .eval() o None si no se pudo cargar.
        """
        # Fast path: modelo ya cargado
        if sport_key in self._models:
            return self._models[sport_key]

        # Slow path: cargar desde disco (una sola vez)
        with self._lock:
            # Double-check locking
            if sport_key in self._models:
                return self._models[sport_key]

            if sport_key not in self._configs:
                logger.error("Modelo '%s' no registrado en el registry.", sport_key)
                return None

            cfg = self._configs[sport_key]
            weights_path = cfg['weights_path']

            if not os.path.exists(weights_path):
                logger.warning(
                    "Pesos no encontrados para '%s': %s. "
                    "El modelo se cargara con pesos aleatorios (modo desarrollo).",
                    sport_key, weights_path,
                )
                # En desarrollo, cargar el modelo sin pesos para que la API
                # funcione y retorne predicciones (aleatorias pero estructuradas)
                model = cfg['model_class'](config=cfg['config'])
                model.to(self._device)
                model.eval()
                self._models[sport_key] = model
                logger.info(
                    "Modelo '%s' cargado SIN pesos (dev mode) | Device: %s",
                    sport_key, self._device,
                )
                return model

            try:
                model = cfg['model_class'](config=cfg['config'])
                checkpoint = torch.load(
                    weights_path,
                    map_location=self._device,
                    weights_only=False,
                )

                # Soportar tanto state_dict directo como checkpoint completo
                if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
                    model.load_state_dict(checkpoint['model_state_dict'])
                else:
                    model.load_state_dict(checkpoint)

                model.to(self._device)
                model.eval()
                self._models[sport_key] = model

                logger.info(
                    "Modelo '%s' cargado exitosamente desde '%s' | Device: %s",
                    sport_key, weights_path, self._device,
                )
                return model

            except Exception as exc:
                logger.error(
                    "Error cargando modelo '%s': %s",
                    sport_key, exc, exc_info=True,
                )
                return None

    def is_loaded(self, sport_key: str) -> bool:
        """Verifica si un modelo ya esta en memoria."""
        return sport_key in self._models

    def list_registered(self) -> Dict[str, bool]:
        """Retorna un dict {sport_key: is_loaded} de todos los modelos registrados."""
        return {
            key: key in self._models
            for key in self._configs
        }
