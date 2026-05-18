"""
mlb_predictor.py — Arquitectura de Red Neuronal para Predicciones MLB.

Diseño Estadístico:
    Las carreras en béisbol (~4-5 por equipo) tienen una distribución que se
    asemeja a Poisson, PERO con sobredispersión sistemática: la varianza real
    supera a la media. Esto ocurre por:
        - Extra innings (juegos que se extienden producen más carreras de lo esperado).
        - Bullpen blowups (una mala entrada puede producir 5+ carreras).
        - Efectos del ballpark (Coors Field vs. Dodger Stadium).

    Solución: Distribución Binomial Negativa (NegBin).
    NegBin generaliza Poisson al añadir un parámetro de dispersión α:
        - Si α → 0, NegBin → Poisson (sin sobredispersión).
        - Si α > 0, permite capturar la varianza extra del béisbol.

    La red predice:
        1. log_mu (logaritmo de la tasa de carreras λ): se pasa por exp() para
           obtener λ > 0, garantizando carreras no-negativas.
        2. log_alpha (logaritmo del parámetro de dispersión): controla cuánta
           sobredispersión permite el modelo para cada matchup.

Flujo de Datos:
    Tensores normalizados → MLBPredictor → [log_mu_home, log_mu_away, log_alpha_home, log_alpha_away]
"""

import logging
import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


# ==========================================
# CONFIGURACIÓN ESPECÍFICA MLB
# ==========================================

@dataclass
class MLBConfig:
    """Hiperparámetros de la arquitectura MLB."""
    input_dim: int = 10       # Features: ERA, WHIP, OPS, wOBA, K/9, BB/9, HR/FB, etc.
    hidden_dim: int = 128     # Dimensión base de las capas ocultas
    dropout_rate: float = 0.3 # El béisbol requiere más regularización por datasets más pequeños
    num_outputs: int = 2      # [carreras_local, carreras_visitante]


# ==========================================
# ARQUITECTURA PRINCIPAL: MLBPredictor
# ==========================================

class MLBPredictor(nn.Module):
    """
    Red neuronal de regresión Binomial Negativa para predicción de carreras MLB.

    Arquitectura multi-cabeza con backbone compartido:
        - shared_backbone: Representación latente del matchup (pitcher vs lineup).
        - home_mu_head:    Log-tasa de carreras del equipo local.
        - away_mu_head:    Log-tasa de carreras del equipo visitante.
        - home_alpha_head: Dispersión del local (sobredispersión vs Poisson).
        - away_alpha_head: Dispersión del visitante.

    El modelo captura explícitamente que un matchup Ace vs lineup débil tiene
    MENOS varianza que un 5to abridor vs lineup fuerte, a través de las
    cabezas de dispersión (alpha) separadas.

    Attributes:
        shared_backbone: Extractor de representaciones compartido.
        home_mu_head: Predicción de log(λ) para carreras del local.
        away_mu_head: Predicción de log(λ) para carreras del visitante.
        home_alpha_head: Log-dispersión del local.
        away_alpha_head: Log-dispersión del visitante.
    """

    def __init__(self, config: Optional[MLBConfig] = None) -> None:
        super().__init__()
        cfg = config or MLBConfig()

        # --- Backbone Compartido ---
        self.shared_backbone = nn.Sequential(
            nn.Linear(cfg.input_dim, cfg.hidden_dim),
            nn.BatchNorm1d(cfg.hidden_dim),
            nn.GELU(),  # GELU converge mejor que ReLU para distribuciones de conteo
            nn.Dropout(cfg.dropout_rate),

            nn.Linear(cfg.hidden_dim, cfg.hidden_dim // 2),
            nn.BatchNorm1d(cfg.hidden_dim // 2),
            nn.GELU(),
            nn.Dropout(cfg.dropout_rate),

            nn.Linear(cfg.hidden_dim // 2, cfg.hidden_dim // 4),
            nn.BatchNorm1d(cfg.hidden_dim // 4),
            nn.GELU(),
        )

        neck_dim = cfg.hidden_dim // 4  # 32

        # --- Cabezas de Media (λ): log_mu ---
        # Salida sin activación: se le aplica exp() en la loss para garantizar λ > 0
        self.home_mu_head = nn.Sequential(
            nn.Linear(neck_dim, neck_dim // 2),
            nn.ReLU(),
            nn.Linear(neck_dim // 2, 1),
        )
        self.away_mu_head = nn.Sequential(
            nn.Linear(neck_dim, neck_dim // 2),
            nn.ReLU(),
            nn.Linear(neck_dim // 2, 1),
        )

        # --- Cabezas de Dispersión (α): log_alpha ---
        # Controlan cuánta sobredispersión modela la NegBin por encima de Poisson
        self.home_alpha_head = nn.Sequential(
            nn.Linear(neck_dim, neck_dim // 4),
            nn.ReLU(),
            nn.Linear(neck_dim // 4, 1),
        )
        self.away_alpha_head = nn.Sequential(
            nn.Linear(neck_dim, neck_dim // 4),
            nn.ReLU(),
            nn.Linear(neck_dim // 4, 1),
        )

        self._init_weights()
        logger.info(
            "MLBPredictor inicializado: input_dim=%d, hidden=%d, dropout=%.2f",
            cfg.input_dim, cfg.hidden_dim, cfg.dropout_rate,
        )

    def _init_weights(self) -> None:
        """Inicialización Xavier (óptima con GELU y funciones de activación suaves)."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_normal_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Forward pass del modelo MLB.

        Args:
            x: Tensor de features normalizadas [batch_size, input_dim].

        Returns:
            Diccionario con 4 predicciones:
                'log_mu_home':    [batch, 1] Log-tasa de carreras del local.
                'log_mu_away':    [batch, 1] Log-tasa de carreras del visitante.
                'log_alpha_home': [batch, 1] Log-dispersión del local.
                'log_alpha_away': [batch, 1] Log-dispersión del visitante.
        """
        h = self.shared_backbone(x)

        return {
            'log_mu_home': self.home_mu_head(h),
            'log_mu_away': self.away_mu_head(h),
            'log_alpha_home': self.home_alpha_head(h),
            'log_alpha_away': self.away_alpha_head(h),
        }


# ==========================================
# FUNCIÓN DE PÉRDIDA: NEGATIVE BINOMIAL NLL
# ==========================================

class NegativeBinomialLoss(nn.Module):
    """
    Función de pérdida basada en la log-verosimilitud negativa de la distribución
    Binomial Negativa.

    La Binomial Negativa parametrizada por (μ, α) tiene la PMF:

        P(Y=y | μ, α) = Γ(y + 1/α) / (Γ(1/α) * y!) * (1/(1+αμ))^(1/α) * (αμ/(1+αμ))^y

    Y la NLL correspondiente:

        -log P = -[log Γ(y + r) - log Γ(r) - log(y!) + r*log(r/(r+μ)) + y*log(μ/(r+μ))]

    donde r = 1/α es el parámetro de "número de fracasos" de la NegBin.

    Cuando α → 0, la distribución converge a Poisson, lo cual es correcto:
    si no hay sobredispersión, el modelo "desactiva" la corrección NegBin
    automáticamente.
    """

    def __init__(self) -> None:
        super().__init__()

    def _negbin_nll(
        self, log_mu: torch.Tensor, log_alpha: torch.Tensor, target: torch.Tensor
    ) -> torch.Tensor:
        """
        Calcula la NLL de la Binomial Negativa para un solo equipo.

        Args:
            log_mu: Log de la tasa media de carreras [batch, 1].
            log_alpha: Log del parámetro de dispersión [batch, 1].
            target: Carreras reales observadas [batch, 1].

        Returns:
            Escalar: NLL promedio del batch.
        """
        mu = torch.exp(log_mu)             # λ > 0
        alpha = torch.exp(log_alpha) + 1e-8 # α > 0 (estabilidad numérica)
        r = 1.0 / alpha                     # r = 1/α (parámetro de éxitos)

        # Log-verosimilitud de la NegBin
        # Usamos torch.lgamma para estabilidad numérica en lugar de factoriales
        nll = (
            torch.lgamma(r)
            + torch.lgamma(target + 1)
            - torch.lgamma(target + r)
            + r * torch.log(r / (r + mu))
            + target * torch.log(mu / (r + mu))
        )

        return -nll.mean()  # NLL = negativo de la log-likelihood

    def forward(
        self,
        predictions: Dict[str, torch.Tensor],
        target_home: torch.Tensor,
        target_away: torch.Tensor,
    ) -> torch.Tensor:
        """
        Pérdida total = NLL(local) + NLL(visitante).

        Args:
            predictions: Diccionario de salida de MLBPredictor.forward().
            target_home: Carreras reales del local [batch, 1].
            target_away: Carreras reales del visitante [batch, 1].

        Returns:
            Escalar: Pérdida NLL combinada.
        """
        loss_home = self._negbin_nll(
            predictions['log_mu_home'],
            predictions['log_alpha_home'],
            target_home,
        )
        loss_away = self._negbin_nll(
            predictions['log_mu_away'],
            predictions['log_alpha_away'],
            target_away,
        )

        return loss_home + loss_away


# ==========================================
# ELO RATING SYSTEM — MLB (Pitcher-Adjusted)
# ==========================================

def update_mlb_elo(
    elo_home: float,
    elo_away: float,
    score_home: int,
    score_away: int,
    k_factor: float = 4.0,
    home_advantage: float = 24.0,
    pitcher_home_rating: float = 0.0,
    pitcher_away_rating: float = 0.0,
) -> Tuple[float, float]:
    """
    Actualiza los ratings Elo para un partido de MLB con ajuste de pitcher.

    MLB requiere un sistema Elo fundamentalmente diferente a otros deportes:
        - K-Factor bajo (4.0): El béisbol tiene ~162 juegos, así que cada
          partido individual mueve poco el Elo (el mejor equipo gana ~60%).
        - Home Advantage bajo (24 pts Elo): En MLB, el local gana ~54%
          de los partidos, mucho menos que en NBA (~60%).
        - Ajuste de Pitcher Abridor: El Elo del equipo se modifica dinámicamente
          según quién lanza. Un Ace (pitcher_rating = +50) sube el Elo efectivo,
          mientras que un 5to abridor (pitcher_rating = -30) lo baja. Esto
          refleja que el mismo equipo puede tener un 70% o un 45% de probabilidad
          de ganar dependiendo de quién abre.

    El `pitcher_rating` se calcula externamente basado en métricas del pitcher:
        pitcher_rating ≈ (league_avg_ERA - pitcher_ERA) * scaling_factor
        Valores típicos: Ace = +40 a +60, #5 Starter = -20 a -40.

    Args:
        elo_home: Rating Elo base del equipo local.
        elo_away: Rating Elo base del equipo visitante.
        score_home: Carreras del local.
        score_away: Carreras del visitante.
        k_factor: Factor K (velocidad de convergencia, bajo por temporada larga).
        home_advantage: Bonus Elo para el local (default: 24 pts).
        pitcher_home_rating: Ajuste Elo del pitcher abridor local.
        pitcher_away_rating: Ajuste Elo del pitcher abridor visitante.

    Returns:
        Tupla (nuevo_elo_home, nuevo_elo_away).

    Example:
        >>> # Ace local vs 5to abridor visitante
        >>> h, a = update_mlb_elo(1500, 1500, 5, 2, pitcher_home_rating=50.0, pitcher_away_rating=-30.0)
        >>> print(f"Home: {h:.1f}, Away: {a:.1f}")
    """
    # Elo efectivo = base + ventaja de local + calidad del pitcher
    effective_home = elo_home + home_advantage + pitcher_home_rating
    effective_away = elo_away + pitcher_away_rating

    # Expectativa de victoria
    expected_home = 1.0 / (1.0 + 10.0 ** ((effective_away - effective_home) / 400.0))
    expected_away = 1.0 - expected_home

    # Resultado binario
    actual_home = 1.0 if score_home > score_away else 0.0
    actual_away = 1.0 - actual_home

    # MOV Multiplier adaptado a MLB (menor escala que NBA)
    # En béisbol, una victoria por 5+ carreras ya es un blowout
    run_diff = abs(score_home - score_away)
    mov_multiplier = math.log(max(run_diff, 1) + 1) * (
        1.5 / (1.5 + 0.001 * abs(effective_home - effective_away))
    )

    # Actualización
    adjustment = k_factor * mov_multiplier
    new_elo_home = elo_home + adjustment * (actual_home - expected_home)
    new_elo_away = elo_away + adjustment * (actual_away - expected_away)

    return new_elo_home, new_elo_away


# ==========================================
# UTILIDAD: PITCHER RATING DESDE MÉTRICAS
# ==========================================

def calculate_pitcher_rating(
    pitcher_era: float,
    league_avg_era: float = 4.25,
    scaling_factor: float = 12.0,
) -> float:
    """
    Calcula el ajuste Elo de un pitcher basado en su ERA vs la media de la liga.

    Un pitcher con ERA inferior a la media de la liga recibe un rating positivo
    (mejora el Elo del equipo), mientras que uno con ERA superior recibe un
    rating negativo.

    La escala por defecto produce:
        - ERA 2.50 (Ace élite): rating ≈ +21.0
        - ERA 3.50 (Sólido):    rating ≈ +9.0
        - ERA 4.25 (Promedio):   rating = 0.0
        - ERA 5.50 (#5 Starter): rating ≈ -15.0

    Args:
        pitcher_era: ERA del pitcher abridor.
        league_avg_era: ERA promedio de la liga (default: 4.25, MLB 2023).
        scaling_factor: Factor de escala para convertir ERA-diff a puntos Elo.

    Returns:
        Ajuste Elo del pitcher (puede ser positivo o negativo).
    """
    return (league_avg_era - pitcher_era) * scaling_factor


# ==========================================
# EXPECTATIVA PITAGÓRICA — MLB
# ==========================================

def mlb_pythagorean_expectation(
    runs_scored: float,
    runs_allowed: float,
    exponent: float = 1.83,
) -> float:
    """
    Calcula la expectativa pitagórica para MLB.

    La fórmula pitagórica original del béisbol fue propuesta por Bill James en 1980:

        Win% = RS^exp / (RS^exp + RA^exp)

    El exponente original era 2.0 (de ahí el nombre "pitagórica"), pero el
    valor óptimo empírico para MLB es 1.83 (estudio de Baseball Prospectus
    y Baseball-Reference), que minimiza el RMSE histórico.

    Nota: Para un cálculo aún más preciso, algunos analistas usan el
    "Pythagenpat" de David Smyth, donde el exponente es dinámico:
        exp = (RS + RA)^0.287
    Pero el exponente fijo de 1.83 es suficientemente preciso para la mayoría
    de aplicaciones de modelos predictivos.

    Args:
        runs_scored: Carreras anotadas por el equipo en la temporada (o promedio).
        runs_allowed: Carreras permitidas por el equipo en la temporada (o promedio).
        exponent: Exponente pitagórico MLB (default: 1.83).

    Returns:
        Porcentaje de victorias esperado ∈ [0.0, 1.0].

    Raises:
        ValueError: Si alguno de los valores de carreras es negativo.

    Example:
        >>> win_pct = mlb_pythagorean_expectation(800, 700)
        >>> print(f"Win%: {win_pct:.3f}")  # ~0.562
        >>> print(f"Proyección en 162 juegos: {win_pct * 162:.0f} victorias")
    """
    if runs_scored < 0 or runs_allowed < 0:
        raise ValueError(
            f"Las carreras no pueden ser negativas: scored={runs_scored}, allowed={runs_allowed}"
        )

    if runs_scored == 0 and runs_allowed == 0:
        return 0.5

    rs_exp = runs_scored ** exponent
    ra_exp = runs_allowed ** exponent

    denominator = rs_exp + ra_exp
    if denominator == 0:
        return 0.5

    return rs_exp / denominator


# ==========================================
# PRUEBA UNITARIA STANDALONE
# ==========================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')

    print("=" * 65)
    print("  PRUEBA: MLBPredictor + NegBin Loss + Elo + Pitágoras")
    print("=" * 65)

    # --- Test 1: Arquitectura ---
    cfg = MLBConfig(input_dim=10)
    model = MLBPredictor(config=cfg)
    print(f"\n{model}\n")

    dummy = torch.randn(4, 10)  # batch=4, features=10
    output = model(dummy)
    print("--- Forward Pass (batch=4) ---")
    for key, val in output.items():
        print(f"  {key}: shape={val.shape}, sample={val[0].item():.4f}")

    # --- Test 2: Loss Function ---
    criterion = NegativeBinomialLoss()
    target_h = torch.tensor([[3.0], [5.0], [1.0], [7.0]])  # Carreras reales
    target_a = torch.tensor([[2.0], [4.0], [0.0], [3.0]])
    loss = criterion(output, target_h, target_a)
    print(f"\nNegBin NLL Loss: {loss.item():.4f}")

    # --- Test 3: Elo MLB (Ace vs #5 Starter) ---
    print("\n--- Elo MLB (Pitcher-Adjusted) ---")
    ace_rating = calculate_pitcher_rating(pitcher_era=2.80)
    fifth_rating = calculate_pitcher_rating(pitcher_era=5.20)
    print(f"  Ace (ERA 2.80)  -> rating = {ace_rating:+.1f}")
    print(f"  #5  (ERA 5.20)  -> rating = {fifth_rating:+.1f}")

    h, a = update_mlb_elo(
        1500, 1500, 5, 2,
        pitcher_home_rating=ace_rating,
        pitcher_away_rating=fifth_rating,
    )
    print(f"  Resultado: Home(Ace) 5-2 Away(#5)")
    print(f"  Home: 1500 -> {h:.1f} | Away: 1500 -> {a:.1f}")

    # --- Test 4: Pitágoras MLB ---
    print("\n--- Expectativa Pitagórica MLB ---")
    wp = mlb_pythagorean_expectation(800, 700)
    print(f"  RS=800, RA=700 -> Win%={wp:.3f} ({wp*162:.0f} victorias en 162 juegos)")
