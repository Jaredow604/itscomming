import os
from django.apps import AppConfig


class PrediccionesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'predicciones'

    def ready(self):
        """
        Hook que Django ejecuta una vez al iniciar la app.

        1. Registra los modelos PyTorch en el Singleton ModelRegistry
           para lazy-loading eficiente.
        2. MatchPredictionNet usa __init__(input_dim, hidden_dim, output_dim)
           sin dataclass config — se registra con un wrapper.
        """
        from predicciones.model_registry import ModelRegistry
        from src.models.networks.nba_predictor import NBAPredictor, NBAConfig
        from src.models.networks.mlb_predictor import MLBPredictor, MLBConfig
        from src.models.networks.match_prediction_net import MatchPredictionNet

        registry = ModelRegistry.get_instance()

        if 'nba' not in registry.list_registered():
            registry.register(
                sport_key='nba',
                model_class=NBAPredictor,
                config=NBAConfig(input_dim=8),
                weights_path='checkpoints/nba_best_model_weights.pth',
            )

        if 'mlb' not in registry.list_registered():
            registry.register(
                sport_key='mlb',
                model_class=MLBPredictor,
                config=MLBConfig(input_dim=10),
                weights_path='checkpoints/mlb_best_model_weights.pth',
            )

        if 'soccer' not in registry.list_registered():
            # MatchPredictionNet no usa dataclass config — wrapper inline
            class _SoccerConfig:
                pass

            class _SoccerModelWrapper:
                """Factory que instancia MatchPredictionNet ignorando config dataclass."""
                def __new__(cls, config=None):
                    return MatchPredictionNet(input_dim=12, hidden_dim=128, output_dim=3)

            registry.register(
                sport_key='soccer',
                model_class=_SoccerModelWrapper,
                config=None,
                weights_path='checkpoints/soccer_best_model.pth',
            )
