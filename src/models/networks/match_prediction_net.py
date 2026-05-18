"""
match_prediction_net.py -- Red Neuronal Mejorada para Predicci\u00f3n de Partidos (1X2).

Arquitectura v2 \u2014 Dise\u00f1o de \u00e9lite:
    - input_dim=12: 6 m\u00e9tricas por equipo (goles, tiros, corners, forma, elo, h2h)
    - Capas: 12 \u2192 256 \u2192 BN \u2192 128 \u2192 BN \u2192 64 \u2192 3 (logits 1X2)
    - Dropout adaptativo + LayerNorm
    - Inicializaci\u00f3n Kaiming para LeakyReLU

Features de entrada (12):
    [0]  prom_goles_local          (avg desde Equipos DB)
    [1]  prom_goles_visitante
    [2]  prom_tiros_puerta_local
    [3]  prom_tiros_puerta_visitante
    [4]  prom_corners_local
    [5]  prom_corners_visitante
    [6]  forma_local               (W=1, D=0.5, L=0 \u2014 promedio \u00faltimos 5)
    [7]  forma_visitante
    [8]  elo_local                 (normalizado / 1500.0)
    [9]  elo_visitante
    [10] h2h_win_rate_local        (fraction de victorias en H2H hist\u00f3rico)
    [11] is_neutral                (0 = local en casa, 1 = cancha neutral)
"""

import math
import torch
import torch.nn as nn
import logging

logger = logging.getLogger(__name__)


class MatchPredictionNet(nn.Module):
    """
    Red neuronal profunda para predicci\u00f3n moneyline (1X2) de f\u00fatbol.

    Salida: logits para [Draw, Home Win, Away Win]
    (CrossEntropyLoss aplica softmax internamente durante entrenamiento;
     en inferencia usar torch.softmax para obtener probabilidades)
    """

    def __init__(self, input_dim: int = 12, hidden_dim: int = 128, output_dim: int = 3):
        super().__init__()

        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim

        # --- Backbone profundo con BatchNorm ---
        self.network = nn.Sequential(
            # Bloque 1: input_dim -> hidden_dim
            nn.Linear(input_dim, hidden_dim * 2),
            nn.BatchNorm1d(hidden_dim * 2),
            nn.LeakyReLU(0.1),
            nn.Dropout(0.3),

            # Bloque 2: hidden_dim*2 -> hidden_dim
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.LeakyReLU(0.1),
            nn.Dropout(0.25),

            # Bloque 3: hidden_dim -> hidden_dim//2
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.BatchNorm1d(hidden_dim // 2),
            nn.LeakyReLU(0.1),
            nn.Dropout(0.2),

            # Salida: 3 logits (Draw=0, Home=1, Away=2)
            nn.Linear(hidden_dim // 2, output_dim),
        )

        self._init_weights()
        logger.info(
            "MatchPredictionNet v2 inicializada: input_dim=%d, hidden=%d",
            input_dim, hidden_dim,
        )

    def _init_weights(self) -> None:
        """Inicializaci\u00f3n Kaiming para capas lineales con LeakyReLU."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.kaiming_normal_(module.weight, nonlinearity='leaky_relu')
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: Tensor [batch_size, input_dim] con features normalizadas.

        Returns:
            Logits [batch_size, 3] para (Draw, Home Win, Away Win).
        """
        return self.network(x)


# ==========================================
# FEATURE ENGINEERING
# ==========================================

def build_soccer_feature_vector(
    home_stats: dict,
    away_stats: dict,
    elo_home: float = 1500.0,
    elo_away: float = 1500.0,
    h2h_win_rate_home: float = 0.5,
    is_neutral: bool = False,
) -> torch.Tensor:
    """
    Construye el vector de features de 12 dimensiones para un partido de soccer.

    Args:
        home_stats: {'prom_goles': float, 'prom_tiros_puerta': float, 'prom_corners': float, 'forma': float}
        away_stats: Idem para visitante
        elo_home: Rating Elo del local (default 1500)
        elo_away: Rating Elo del visitante (default 1500)
        h2h_win_rate_home: Fraction de victorias del local en H2H (0-1)
        is_neutral: True si es cancha neutral (0/1)

    Returns:
        Tensor [1, 12] listo para inferencia
    """
    features = [
        float(home_stats.get('prom_goles', 1.2)),
        float(away_stats.get('prom_goles', 1.0)),
        float(home_stats.get('prom_tiros_puerta', 4.0)),
        float(away_stats.get('prom_tiros_puerta', 3.5)),
        float(home_stats.get('prom_corners', 5.0)),
        float(away_stats.get('prom_corners', 4.5)),
        float(home_stats.get('forma', 0.6)),     # forma: 0-1 (1=5W consecutivos)
        float(away_stats.get('forma', 0.5)),
        elo_home / 1500.0,                        # normalizado a ~1.0
        elo_away / 1500.0,
        float(h2h_win_rate_home),
        float(1.0 if is_neutral else 0.0),
    ]
    return torch.tensor([features], dtype=torch.float32)


def poisson_bivariate_predict(
    lambda_home: float,
    lambda_away: float,
    max_goals: int = 7,
) -> dict:
    """
    Calcula probabilidades 1X2 con el modelo de Poisson Bivariado independiente.

    Es el baseline estad\u00edstico m\u00e1s respetado en an\u00e1lisis de f\u00fatbol
    (Dixon-Coles, 1997). Para cada combinaci\u00f3n de goles (i, j), calcula
    P(home=i) * P(away=j) y suma las probabilidades de victoria/empate/derrota.

    Args:
        lambda_home: Goles esperados del local (prom\u00f3 hist\u00f3rico ajustado)
        lambda_away: Goles esperados del visitante
        max_goals: M\u00e1ximo de goles por equipo a considerar

    Returns:
        Dict con 'probabilities' (home, draw, away), 'xg_home', 'xg_away', 'favored'
    """
    def poisson_pmf(lam: float, k: int) -> float:
        if lam <= 0:
            return 1.0 if k == 0 else 0.0
        return (lam ** k) * math.exp(-lam) / math.factorial(k)

    home_win = away_win = draw = 0.0
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p = poisson_pmf(lambda_home, i) * poisson_pmf(lambda_away, j)
            if i > j:
                home_win += p
            elif i < j:
                away_win += p
            else:
                draw += p

    total = home_win + away_win + draw
    if total > 0:
        home_win /= total
        away_win /= total
        draw /= total

    favored = 'home' if home_win > max(draw, away_win) else (
        'draw' if draw > away_win else 'away'
    )

    return {
        'probabilities': {
            'home': round(home_win, 4),
            'draw': round(draw, 4),
            'away': round(away_win, 4),
        },
        'xg_home': round(lambda_home, 2),
        'xg_away': round(lambda_away, 2),
        'favored': favored,
    }


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("  PRUEBA: MatchPredictionNet v2")
    print("=" * 60)

    model = MatchPredictionNet(input_dim=12, hidden_dim=128)
    print(f"\nParámetros totales: {sum(p.numel() for p in model.parameters()):,}")

    home = {'prom_goles': 1.89, 'prom_tiros_puerta': 4.89, 'prom_corners': 5.81, 'forma': 0.8}
    away = {'prom_goles': 0.68, 'prom_tiros_puerta': 2.92, 'prom_corners': 4.0, 'forma': 0.3}

    feat = build_soccer_feature_vector(home, away, elo_home=1620, elo_away=1380, h2h_win_rate_home=0.6)
    logits = model(feat)
    probs = torch.softmax(logits, dim=1)
    print(f"\nArsenal vs Burnley:")
    print(f"  Logits: {logits.detach().numpy()}")
    print(f"  Probs [Draw, Home, Away]: {probs.detach().numpy()}")

    poisson = poisson_bivariate_predict(1.89, 0.68)
    print(f"\nPoisson Bivariado: {poisson}")
