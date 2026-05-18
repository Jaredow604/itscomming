"""
management/commands/train_models.py
Comando Django para entrenar los modelos ML con datos reales de la BD.

Uso:
    python manage.py train_models --sport soccer
    python manage.py train_models --sport all
"""

import logging
import math
import os
import random

import torch
import torch.nn as nn
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Entrena los modelos predictivos con datos reales de la BD."

    def add_arguments(self, parser):
        parser.add_argument(
            '--sport',
            type=str,
            default='soccer',
            choices=['soccer', 'nba', 'mlb', 'all'],
            help='Deporte a entrenar (default: soccer)',
        )
        parser.add_argument(
            '--epochs',
            type=int,
            default=150,
            help='N\u00famero de \u00e9pocas de entrenamiento (default: 150)',
        )
        parser.add_argument(
            '--samples',
            type=int,
            default=5000,
            help='Muestras sint\u00e9ticas a generar (default: 5000)',
        )

    def handle(self, *args, **options):
        sport = options['sport']
        epochs = options['epochs']
        n_samples = options['samples']

        os.makedirs('checkpoints', exist_ok=True)

        if sport in ('soccer', 'all'):
            self.stdout.write(self.style.SUCCESS("\n=== ENTRENANDO MODELO SOCCER ==="))
            self._train_soccer(epochs=epochs, n_samples=n_samples)

        if sport in ('nba', 'all'):
            self.stdout.write(self.style.SUCCESS("\n=== ENTRENANDO MODELO NBA ==="))
            self._train_nba(epochs=epochs, n_samples=n_samples)

        if sport in ('mlb', 'all'):
            self.stdout.write(self.style.SUCCESS("\n=== ENTRENANDO MODELO MLB ==="))
            self._train_mlb(epochs=epochs, n_samples=n_samples)

    def _train_soccer(self, epochs: int = 150, n_samples: int = 5000):
        """
        Entrena MatchPredictionNet v2 con datos sinteticos calibrados en stats reales.

        Estrategia:
            1. Lee stats reales de Equipos (goles, tiros, corners) desde la BD.
            2. Genera N partidos sinteticos usando Poisson(lambda) para simular goles.
            3. La etiqueta Y es el resultado (Home=1, Draw=0, Away=2) segun los goles.
            4. Las features X son las 12 stats de ambos equipos.
            5. Entrena con CrossEntropyLoss + LR scheduling.
        """
        from predicciones.models import Equipos
        from src.models.networks.match_prediction_net import (
            MatchPredictionNet, build_soccer_feature_vector,
        )
        from src.training.sports_trainer import SportsModelTrainer, TrainerConfig
        from torch.utils.data import DataLoader, TensorDataset

        # --- Leer stats reales ---
        equipos = list(Equipos.objects.filter(prom_goles__gt=0))
        self.stdout.write(f"Equipos con stats reales: {len(equipos)}")

        if len(equipos) < 10:
            self.stdout.write(self.style.WARNING(
                "Pocos equipos con datos. Generando datos sint\u00e9ticos de liga promedio."
            ))
            equipos_data = self._default_soccer_teams()
        else:
            equipos_data = [
                {
                    'nombre': e.nombre,
                    'prom_goles': float(e.prom_goles),
                    'prom_tiros_puerta': float(e.prom_tiros_puerta),
                    'prom_corners': float(e.prom_corners),
                    'forma': random.uniform(0.3, 0.8),  # forma simulada
                }
                for e in equipos
            ]

        # --- Generar partidos sinteticos ---
        X_list, y_list = [], []
        random.seed(42)

        def poisson_sample(lam: float) -> int:
            import math
            L = math.exp(-lam)
            k, p = 0, 1.0
            while p > L:
                k += 1
                p *= random.random()
            return k - 1

        for _ in range(n_samples):
            home_team = random.choice(equipos_data)
            away_team = random.choice(equipos_data)
            if home_team['nombre'] == away_team['nombre']:
                continue

            # Ventaja local: lambda_home * 1.15 (factor empirico de home advantage en futbol)
            lambda_home = home_team['prom_goles'] * 1.15
            lambda_away = away_team['prom_goles'] * 0.95

            goals_home = poisson_sample(lambda_home)
            goals_away = poisson_sample(lambda_away)

            # Etiqueta: 1=Home, 0=Draw, 2=Away
            if goals_home > goals_away:
                label = 1
            elif goals_home < goals_away:
                label = 2
            else:
                label = 0

            feat = build_soccer_feature_vector(
                home_stats=home_team,
                away_stats=away_team,
                elo_home=1500.0 + random.gauss(0, 100),
                elo_away=1500.0 + random.gauss(0, 100),
                h2h_win_rate_home=random.uniform(0.3, 0.7),
                is_neutral=False,
            )
            X_list.append(feat.squeeze(0))
            y_list.append(label)

        if len(X_list) < 100:
            self.stdout.write(self.style.ERROR("No hay suficientes datos para entrenar."))
            return

        X = torch.stack(X_list)
        y = torch.tensor(y_list, dtype=torch.long)

        # --- Split 80/20 ---
        n = len(X)
        idx = torch.randperm(n)
        X, y = X[idx], y[idx]
        split = int(n * 0.8)
        X_train, y_train = X[:split], y[:split]
        X_val, y_val = X[split:], y[split:]

        train_loader = DataLoader(TensorDataset(X_train, y_train), batch_size=128, shuffle=True)
        val_loader = DataLoader(TensorDataset(X_val, y_val), batch_size=256)

        # Distribucion de clases
        counts = [(y_train == i).sum().item() for i in range(3)]
        self.stdout.write(f"Train: {split} muestras | Draw={counts[0]} Home={counts[1]} Away={counts[2]}")

        # --- Modelo ---
        model = MatchPredictionNet(input_dim=12, hidden_dim=128, output_dim=3)
        criterion = nn.CrossEntropyLoss()

        def loss_fn(preds, targets):
            return criterion(preds, targets)

        config = TrainerConfig(
            epochs=epochs,
            learning_rate=5e-4,
            weight_decay=1e-4,
            patience=20,
            checkpoint_dir='checkpoints',
            checkpoint_name='soccer_best_model.pth',
            grad_clip_norm=1.0,
            log_every_n=10,
        )

        trainer = SportsModelTrainer(model, loss_fn, config=config)
        history = trainer.fit(train_loader, val_loader)

        # --- Validacion final ---
        model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for xb, yb in val_loader:
                preds = model(xb)
                predicted = preds.argmax(dim=1)
                correct += (predicted == yb).sum().item()
                total += len(yb)

        acc = correct / total if total > 0 else 0
        self.stdout.write(self.style.SUCCESS(
            f"\nSoccer model entrenado | Val Accuracy: {acc:.1%} | "
            f"Checkpoint: checkpoints/soccer_best_model.pth"
        ))

    def _train_nba(self, epochs: int = 150, n_samples: int = 5000):
        """Entrena NBAPredictor con datos sinteticos calibrados."""
        from src.models.networks.nba_predictor import NBAPredictor, NBAConfig, NBAGaussianLoss
        from src.training.sports_trainer import SportsModelTrainer, TrainerConfig
        from torch.utils.data import DataLoader, TensorDataset
        import numpy as np

        self.stdout.write("Generando datos sint\u00e9ticos NBA calibrados...")
        random.seed(42)
        np.random.seed(42)

        # Stats hiperparametrizadas para NBA (basadas en promedios reales 2023-24)
        # Teams: top (100+ ORtg), mid (105-112), bottom (<100)
        team_profiles = [
            {'name': 'elite', 'ortg': 118, 'drtg': 108, 'pace': 102},
            {'name': 'good',  'ortg': 112, 'drtg': 112, 'pace': 100},
            {'name': 'avg',   'ortg': 108, 'drtg': 115, 'pace': 98},
            {'name': 'bad',   'ortg': 104, 'drtg': 118, 'pace': 96},
        ]

        X_list, y_list = [], []
        for _ in range(n_samples):
            home = random.choice(team_profiles)
            away = random.choice(team_profiles)

            # Home advantage: ~3.5 pts en NBA
            home_pts = home['ortg'] * home['pace'] / 100 * random.gauss(1.0, 0.05) + 3.5
            away_pts = away['ortg'] * away['pace'] / 100 * random.gauss(1.0, 0.05)

            home_pts = max(70, min(160, home_pts))
            away_pts = max(70, min(160, away_pts))

            spread = home_pts - away_pts  # positivo = local gana
            total = home_pts + away_pts

            # Features: [home_ortg, home_drtg, home_pace, home_3p%, away_ortg, away_drtg, away_pace, away_3p%]
            features = [
                home['ortg'] / 120.0,
                home['drtg'] / 120.0,
                home['pace'] / 105.0,
                random.gauss(0.36, 0.03),
                away['ortg'] / 120.0,
                away['drtg'] / 120.0,
                away['pace'] / 105.0,
                random.gauss(0.35, 0.03),
            ]
            targets = [spread, total]
            X_list.append(torch.tensor(features, dtype=torch.float32))
            y_list.append(torch.tensor(targets, dtype=torch.float32))

        X = torch.stack(X_list)
        y = torch.stack(y_list)

        n = len(X)
        idx = torch.randperm(n)
        X, y = X[idx], y[idx]
        split = int(n * 0.8)

        train_loader = DataLoader(TensorDataset(X[:split], y[:split]), batch_size=256, shuffle=True)
        val_loader = DataLoader(TensorDataset(X[split:], y[split:]), batch_size=512)

        model = NBAPredictor(NBAConfig(input_dim=8))
        criterion = NBAGaussianLoss(alpha_spread=0.5, alpha_total=0.5)

        def loss_fn(preds, targets):
            return criterion(preds, targets[:, 0:1], targets[:, 1:2])

        config = TrainerConfig(
            epochs=epochs,
            learning_rate=1e-3,
            weight_decay=1e-4,
            patience=20,
            checkpoint_dir='checkpoints',
            checkpoint_name='nba_best_model_weights.pth',
            log_every_n=10,
        )

        trainer = SportsModelTrainer(model, loss_fn, config=config)
        history = trainer.fit(train_loader, val_loader)
        self.stdout.write(self.style.SUCCESS(
            f"NBA model entrenado | Checkpoint: checkpoints/nba_best_model_weights.pth"
        ))

    def _train_mlb(self, epochs: int = 150, n_samples: int = 5000):
        """Entrena MLBPredictor con datos sinteticos calibrados."""
        from src.models.networks.mlb_predictor import (
            MLBPredictor, MLBConfig, NegativeBinomialLoss,
        )
        from src.training.sports_trainer import SportsModelTrainer, TrainerConfig
        from torch.utils.data import DataLoader, TensorDataset
        import math

        self.stdout.write("Generando datos sintéticos MLB calibrados...")
        random.seed(42)

        team_profiles = [
            {'era': 3.2, 'ba': 0.275, 'obp': 0.350, 'slg': 0.470, 'hr_game': 1.4},
            {'era': 3.8, 'ba': 0.255, 'obp': 0.320, 'slg': 0.430, 'hr_game': 1.1},
            {'era': 4.3, 'ba': 0.245, 'obp': 0.310, 'slg': 0.400, 'hr_game': 0.9},
            {'era': 5.0, 'ba': 0.235, 'obp': 0.300, 'slg': 0.370, 'hr_game': 0.7},
        ]

        X_list, y_list = [], []
        for _ in range(n_samples):
            home = random.choice(team_profiles)
            away = random.choice(team_profiles)

            runs_h = max(0, (9.0 - home['era'] / 2) * home['ba'] * 10 * random.gauss(1.0, 0.15) + 0.5)
            runs_a = max(0, (9.0 - away['era'] / 2) * away['ba'] * 10 * random.gauss(1.0, 0.15))
            runs_h = min(20, runs_h)
            runs_a = min(20, runs_a)

            features = [
                home['era'] / 6.0,
                home['ba'] / 0.300,
                home['obp'] / 0.380,
                home['slg'] / 0.500,
                home['hr_game'] / 1.5,
                away['era'] / 6.0,
                away['ba'] / 0.300,
                away['obp'] / 0.380,
                away['slg'] / 0.500,
                away['hr_game'] / 1.5,
            ]
            X_list.append(torch.tensor(features, dtype=torch.float32))
            # Targets: [runs_home, runs_away] como conteos reales
            y_list.append(torch.tensor([runs_h, runs_a], dtype=torch.float32))

        X = torch.stack(X_list)
        y = torch.stack(y_list)

        n = len(X)
        idx = torch.randperm(n)
        X, y = X[idx], y[idx]
        split = int(n * 0.8)

        train_loader = DataLoader(TensorDataset(X[:split], y[:split]), batch_size=256, shuffle=True)
        val_loader = DataLoader(TensorDataset(X[split:], y[split:]), batch_size=512)

        model = MLBPredictor(MLBConfig(input_dim=10))
        criterion = NegativeBinomialLoss()

        # NegativeBinomialLoss espera (preds_dict, target_home, target_away)
        def loss_fn(preds, targets):
            return criterion(preds, targets[:, 0:1], targets[:, 1:2])

        config = TrainerConfig(
            epochs=epochs,
            learning_rate=5e-4,
            weight_decay=1e-4,
            patience=20,
            checkpoint_dir='checkpoints',
            checkpoint_name='mlb_best_model_weights.pth',
            grad_clip_norm=1.0,
            log_every_n=10,
        )

        trainer = SportsModelTrainer(model, loss_fn, config=config)
        history = trainer.fit(train_loader, val_loader)
        self.stdout.write(self.style.SUCCESS(
            f"MLB model entrenado | Checkpoint: checkpoints/mlb_best_model_weights.pth"
        ))

    def _default_soccer_teams(self) -> list:
        """Teams de referencia si no hay datos en BD."""
        return [
            {'nombre': 'Elite', 'prom_goles': 2.1, 'prom_tiros_puerta': 6.0, 'prom_corners': 6.5, 'forma': 0.8},
            {'nombre': 'Good',  'prom_goles': 1.7, 'prom_tiros_puerta': 5.0, 'prom_corners': 5.5, 'forma': 0.65},
            {'nombre': 'Mid',   'prom_goles': 1.3, 'prom_tiros_puerta': 4.0, 'prom_corners': 4.5, 'forma': 0.5},
            {'nombre': 'Low',   'prom_goles': 0.9, 'prom_tiros_puerta': 3.0, 'prom_corners': 3.5, 'forma': 0.35},
            {'nombre': 'Weak',  'prom_goles': 0.6, 'prom_tiros_puerta': 2.0, 'prom_corners': 2.5, 'forma': 0.2},
        ] * 26  # duplicar para tener variedad
