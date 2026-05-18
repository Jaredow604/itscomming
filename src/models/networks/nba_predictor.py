"""
nba_predictor.py — Arquitectura de Red Neuronal para Predicciones NBA.

Diseño Estadístico:
    La NBA produce puntajes altos (~100-130 pts por equipo) con una distribución
    aproximadamente Normal/Gaussiana. Poisson NO es viable porque está diseñada
    para eventos raros (λ bajo). En la NBA, los puntos se acumulan continuamente
    a través de posesiones, y el Teorema Central del Límite converge la suma
    de ~100 posesiones hacia una Gaussiana.

    Por tanto, esta red predice:
        1. Point Spread (diferencia de puntos): Salida continua ∈ (-∞, +∞)
        2. Total Over/Under (puntos totales): Salida continua ∈ (0, +∞)

    Ambas salidas se modelan con distribución Normal, y la función de pérdida
    ideal es GaussianNLLLoss (que penaliza simultáneamente el error en la media
    y la incertidumbre del modelo a través de la varianza aprendida).

Flujo de Datos:
    Tensores normalizados (RobustScaler) → NBAPredictor → [spread, total, log_var_spread, log_var_total]
"""

import logging
import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


# ==========================================
# CONFIGURACIÓN ESPECÍFICA NBA
# ==========================================

@dataclass
class NBAConfig:
    """Hiperparámetros de la arquitectura NBA."""
    input_dim: int = 8        # Features por equipo: puntos, rebotes, triples, asistencias, etc.
    hidden_dim: int = 128     # Dimensión base de las capas ocultas
    dropout_rate: float = 0.25
    num_outputs: int = 2      # [point_spread, total_over_under]


# ==========================================
# ARQUITECTURA PRINCIPAL: NBAPredictor
# ==========================================

class NBAPredictor(nn.Module):
    """
    Red neuronal de regresión Gaussiana para predicción de puntajes NBA.

    Produce 4 salidas:
        - mu_spread:        Media predicha del Point Spread (local - visitante).
        - mu_total:         Media predicha del Total de puntos (local + visitante).
        - log_var_spread:   Log-varianza del spread (para GaussianNLLLoss).
        - log_var_total:    Log-varianza del total (para GaussianNLLLoss).

    La red aprende no solo la predicción, sino también su propia incertidumbre
    (heteroscedastic regression), lo cual es esencial en deportes donde la
    varianza cambia según el matchup (ej. GSW vs LAL tiene más varianza
    que un tanking vs tanking).

    Attributes:
        shared_backbone: Capas compartidas para extracción de representaciones.
        spread_head: Cabeza de regresión para el Point Spread.
        total_head: Cabeza de regresión para el Over/Under Total.
        var_spread_head: Cabeza para la log-varianza del Spread.
        var_total_head: Cabeza para la log-varianza del Total.
    """

    def __init__(self, config: Optional[NBAConfig] = None) -> None:
        super().__init__()
        cfg = config or NBAConfig()

        # --- Backbone Compartido ---
        # Extrae representaciones latentes del matchup antes de bifurcar
        self.shared_backbone = nn.Sequential(
            nn.Linear(cfg.input_dim, cfg.hidden_dim),
            nn.BatchNorm1d(cfg.hidden_dim),
            nn.LeakyReLU(0.1),
            nn.Dropout(cfg.dropout_rate),

            nn.Linear(cfg.hidden_dim, cfg.hidden_dim // 2),
            nn.BatchNorm1d(cfg.hidden_dim // 2),
            nn.LeakyReLU(0.1),
            nn.Dropout(cfg.dropout_rate),
        )

        neck_dim = cfg.hidden_dim // 2  # 64

        # --- Cabeza: Point Spread (media) ---
        self.spread_head = nn.Sequential(
            nn.Linear(neck_dim, neck_dim // 2),
            nn.ReLU(),
            nn.Linear(neck_dim // 2, 1),  # Salida ∈ (-∞, +∞)
        )

        # --- Cabeza: Total Over/Under (media) ---
        self.total_head = nn.Sequential(
            nn.Linear(neck_dim, neck_dim // 2),
            nn.ReLU(),
            nn.Linear(neck_dim // 2, 1),
            nn.Softplus(),  # Asegura salida > 0 (los totales son siempre positivos)
        )

        # --- Cabezas de Incertidumbre (log-varianza) ---
        # Aprender la incertidumbre heterocedástica por cada predicción
        self.var_spread_head = nn.Sequential(
            nn.Linear(neck_dim, neck_dim // 4),
            nn.ReLU(),
            nn.Linear(neck_dim // 4, 1),
        )
        self.var_total_head = nn.Sequential(
            nn.Linear(neck_dim, neck_dim // 4),
            nn.ReLU(),
            nn.Linear(neck_dim // 4, 1),
        )

        self._init_weights()
        logger.info(
            "NBAPredictor inicializado: input_dim=%d, hidden=%d, dropout=%.2f",
            cfg.input_dim, cfg.hidden_dim, cfg.dropout_rate,
        )

    def _init_weights(self) -> None:
        """Inicialización Kaiming para capas lineales (óptima con LeakyReLU)."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.kaiming_normal_(module.weight, nonlinearity='leaky_relu')
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Forward pass del modelo NBA.

        Args:
            x: Tensor de features normalizadas [batch_size, input_dim].

        Returns:
            Diccionario con las 4 predicciones:
                'mu_spread':      [batch_size, 1] Media del Point Spread.
                'mu_total':       [batch_size, 1] Media del Total O/U.
                'log_var_spread': [batch_size, 1] Log-varianza del Spread.
                'log_var_total':  [batch_size, 1] Log-varianza del Total.
        """
        # Representación compartida
        h = self.shared_backbone(x)

        # Predicciones
        mu_spread = self.spread_head(h)
        mu_total = self.total_head(h)
        log_var_spread = self.var_spread_head(h)
        log_var_total = self.var_total_head(h)

        return {
            'mu_spread': mu_spread,
            'mu_total': mu_total,
            'log_var_spread': log_var_spread,
            'log_var_total': log_var_total,
        }


# ==========================================
# FUNCIÓN DE PÉRDIDA: GAUSSIAN NLL DUAL
# ==========================================

class NBAGaussianLoss(nn.Module):
    """
    Función de pérdida Gaussian NLL combinada para Spread + Total.

    Combina dos pérdidas GaussianNLLLoss (una por cada target) con pesos
    configurables. La GaussianNLLLoss penaliza tanto el error cuadrático
    como la calibración de la incertidumbre:

        L = 0.5 * [log(σ²) + (y - μ)² / σ²]

    Esto obliga a la red a:
        - Si está segura: reducir σ² y acertar en μ.
        - Si no está segura: aumentar σ² para no ser penalizada duramente.

    Attributes:
        alpha_spread: Peso de la loss del Spread en la suma total.
        alpha_total: Peso de la loss del Total en la suma total.
    """

    def __init__(self, alpha_spread: float = 0.5, alpha_total: float = 0.5) -> None:
        super().__init__()
        self.alpha_spread = alpha_spread
        self.alpha_total = alpha_total
        self.gaussian_nll = nn.GaussianNLLLoss(reduction='mean')

    def forward(
        self,
        predictions: Dict[str, torch.Tensor],
        target_spread: torch.Tensor,
        target_total: torch.Tensor,
    ) -> torch.Tensor:
        """
        Calcula la pérdida combinada.

        Args:
            predictions: Diccionario de salida de NBAPredictor.forward().
            target_spread: Tensor [batch, 1] con el spread real (local - visitante).
            target_total: Tensor [batch, 1] con el total real (local + visitante).

        Returns:
            Escalar: Pérdida combinada ponderada.
        """
        # Convertir log-varianza a varianza (siempre > 0)
        var_spread = torch.exp(predictions['log_var_spread'])
        var_total = torch.exp(predictions['log_var_total'])

        loss_spread = self.gaussian_nll(
            predictions['mu_spread'], target_spread, var_spread
        )
        loss_total = self.gaussian_nll(
            predictions['mu_total'], target_total, var_total
        )

        return self.alpha_spread * loss_spread + self.alpha_total * loss_total


# ==========================================
# ELO RATING SYSTEM — NBA
# ==========================================

def update_nba_elo(
    elo_home: float,
    elo_away: float,
    score_home: int,
    score_away: int,
    k_factor: float = 20.0,
    home_advantage: float = 100.0,
    is_back_to_back_home: bool = False,
    is_back_to_back_away: bool = False,
    b2b_penalty: float = 25.0,
) -> Tuple[float, float]:
    """
    Actualiza los ratings Elo para un partido de NBA con ajustes específicos.

    La NBA requiere factores que no existen en otros deportes:
        - Home Court Advantage (~100 pts Elo): En la NBA, el local gana ~60%
          de los partidos, lo cual se modela como un boost Elo significativo.
        - Fatiga Back-to-Back (~25 pts Elo de penalización): Los equipos que
          juegan dos noches consecutivas sufren una caída estadística real
          de ~2-3 puntos en el marcador.

    El Margin of Victory Multiplier (MOV) escala la magnitud de la actualización:
    una victoria por 20 puntos mueve más Elo que una victoria por 1 punto.

    Args:
        elo_home: Rating Elo actual del equipo local.
        elo_away: Rating Elo actual del equipo visitante.
        score_home: Puntaje final del local.
        score_away: Puntaje final del visitante.
        k_factor: Factor K base (velocidad de convergencia).
        home_advantage: Bonus Elo para el local (default: 100 pts).
        is_back_to_back_home: True si el local juega back-to-back.
        is_back_to_back_away: True si el visitante juega back-to-back.
        b2b_penalty: Penalización Elo por fatiga back-to-back.

    Returns:
        Tupla (nuevo_elo_home, nuevo_elo_away).

    Example:
        >>> new_home, new_away = update_nba_elo(1500, 1500, 110, 105)
        >>> print(f"Home: {new_home:.1f}, Away: {new_away:.1f}")
    """
    # Aplicar ajustes contextuales al Elo efectivo
    effective_home = elo_home + home_advantage
    effective_away = elo_away

    if is_back_to_back_home:
        effective_home -= b2b_penalty
        logger.debug("Penalización B2B aplicada al local: -%.1f Elo", b2b_penalty)

    if is_back_to_back_away:
        effective_away -= b2b_penalty
        logger.debug("Penalización B2B aplicada al visitante: -%.1f Elo", b2b_penalty)

    # Expectativa de victoria (fórmula logística estándar de Elo)
    expected_home = 1.0 / (1.0 + 10.0 ** ((effective_away - effective_home) / 400.0))
    expected_away = 1.0 - expected_home

    # Resultado real: 1.0 = victoria, 0.0 = derrota
    actual_home = 1.0 if score_home > score_away else 0.0
    actual_away = 1.0 - actual_home

    # Margin of Victory Multiplier (FiveThirtyEight-style)
    # Escala logarítmicamente para evitar que blowouts dominen
    point_diff = abs(score_home - score_away)
    mov_multiplier = math.log(max(point_diff, 1) + 1) * (2.2 / (2.2 + 0.001 * abs(effective_home - effective_away)))

    # Actualización de Elo
    adjustment = k_factor * mov_multiplier
    new_elo_home = elo_home + adjustment * (actual_home - expected_home)
    new_elo_away = elo_away + adjustment * (actual_away - expected_away)

    return new_elo_home, new_elo_away


# ==========================================
# EXPECTATIVA PITAGÓRICA — NBA
# ==========================================

def nba_pythagorean_expectation(
    points_scored: float,
    points_allowed: float,
    exponent: float = 14.23,
) -> float:
    """
    Calcula la expectativa pitagórica para NBA.

    La fórmula pitagórica estima el porcentaje de victorias esperado de un equipo
    basándose únicamente en sus puntos anotados y permitidos:

        Win% = PF^exp / (PF^exp + PA^exp)

    Para la NBA, el exponente óptimo se sitúa entre 13.91 y 16.5 según diversas
    investigaciones (Daryl Morey, Dean Oliver, John Hollinger). Usamos 14.23
    como default (estudio de Basketball-Reference), que produce el RMSE más bajo
    históricamente en temporadas regulares de la NBA.

    Args:
        points_scored: Promedio de puntos anotados por el equipo.
        points_allowed: Promedio de puntos permitidos al equipo.
        exponent: Exponente pitagórico NBA (default: 14.23).

    Returns:
        Porcentaje de victorias esperado ∈ [0.0, 1.0].

    Raises:
        ValueError: Si alguno de los valores de puntos es negativo.

    Example:
        >>> win_pct = nba_pythagorean_expectation(112.5, 108.3)
        >>> print(f"Win%: {win_pct:.3f}")  # ~0.620
    """
    if points_scored < 0 or points_allowed < 0:
        raise ValueError(
            f"Los puntos no pueden ser negativos: scored={points_scored}, allowed={points_allowed}"
        )

    if points_scored == 0 and points_allowed == 0:
        return 0.5  # Sin datos, probabilidad neutral

    pf_exp = points_scored ** exponent
    pa_exp = points_allowed ** exponent

    denominator = pf_exp + pa_exp
    if denominator == 0:
        return 0.5

    return pf_exp / denominator


# ==========================================
# PRUEBA UNITARIA STANDALONE
# ==========================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')

    print("=" * 65)
    print("  PRUEBA: NBAPredictor + Elo + Pitágoras")
    print("=" * 65)

    # --- Test 1: Arquitectura ---
    cfg = NBAConfig(input_dim=8)
    model = NBAPredictor(config=cfg)
    print(f"\n{model}\n")

    dummy = torch.randn(4, 8)  # batch=4, features=8
    output = model(dummy)
    print("--- Forward Pass (batch=4) ---")
    for key, val in output.items():
        print(f"  {key}: shape={val.shape}, sample={val[0].item():.4f}")

    # --- Test 2: Loss Function ---
    criterion = NBAGaussianLoss(alpha_spread=0.6, alpha_total=0.4)
    target_s = torch.randn(4, 1)  # Spread real
    target_t = torch.rand(4, 1) * 220 + 180  # Total real (~180-400)
    loss = criterion(output, target_s, target_t)
    print(f"\nLoss combinada: {loss.item():.4f}")

    # --- Test 3: Elo NBA ---
    print("\n--- Elo NBA ---")
    h, a = update_nba_elo(1500, 1500, 112, 105, is_back_to_back_away=True)
    print(f"  Home: 1500 -> {h:.1f} | Away (B2B): 1500 -> {a:.1f}")

    # --- Test 4: Pitágoras NBA ---
    print("\n--- Expectativa Pitagórica NBA ---")
    wp = nba_pythagorean_expectation(112.5, 108.3)
    print(f"  PF=112.5, PA=108.3 -> Win%={wp:.3f} ({wp*82:.1f} victorias en 82 juegos)")
