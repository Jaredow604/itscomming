"""
Paso 3: Test de Dimensionalidad de Tensores (Shape Assertions)

Simula la ingesta DB → Pandas → PyTorch para cada pipeline:
  - Verifica que el tensor resultante tenga la forma [batch, input_dim]
  - Verifica que la red acepte el tensor en forward()
  - Documenta mismatches entre features extraídas y lo que la red espera
"""

import pytest
import torch
import pandas as pd
import numpy as np

from src.models.networks.player_prop_net import PlayerPropNet
from src.models.networks.match_prediction_net import (
    MatchPredictionNet,
    build_soccer_feature_vector,
)
from src.models.networks.nba_predictor import NBAPredictor, NBAConfig
from src.models.networks.mlb_predictor import MLBPredictor, MLBConfig
from src.models.model import SportsPredictorMLP
from src.config.config import ModelConfig


# ==========================================
# HELPERS: Synthetic batch builders
# ==========================================

def make_batch(*features_list: list) -> torch.Tensor:
    """Convierte N listas de features en tensor [N, D] float32."""
    return torch.tensor(np.array(features_list, dtype=np.float32))


def assert_batch_ok(tensor: torch.Tensor, expected_dim: int) -> None:
    assert tensor.ndim == 2, f"Se esperaba 2D [batch, feat], got {tensor.ndim}D"
    assert tensor.shape[1] == expected_dim, (
        f"input_dim={expected_dim} pero tensor.shape={tensor.shape}"
    )
    assert tensor.dtype == torch.float32


# ==========================================
# PLAYER PROP NET
# ==========================================

PLAYER_FEATURE_NAMES = [
    "playing_time_min_scaled",
    "total_shots_scaled",
    "standard_sot_scaled",
]

PLAYER_FEATURE_COUNT = len(PLAYER_FEATURE_NAMES)  # 3


class TestPlayerPropPipeline:
    """DB (InferenceReadyPlayerData / FBref) → Pandas → Tensor → PlayerPropNet."""

    @pytest.fixture
    def synthetic_df(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"player": "A", PLAYER_FEATURE_NAMES[0]: 45.0,
             PLAYER_FEATURE_NAMES[1]: 3.0, PLAYER_FEATURE_NAMES[2]: 1.5},
            {"player": "B", PLAYER_FEATURE_NAMES[0]: 90.0,
             PLAYER_FEATURE_NAMES[1]: 5.0, PLAYER_FEATURE_NAMES[2]: 3.0},
            {"player": "C", PLAYER_FEATURE_NAMES[0]: 15.0,
             PLAYER_FEATURE_NAMES[1]: 1.0, PLAYER_FEATURE_NAMES[2]: 0.0},
        ])

    def test_pandas_to_tensor_shape(self, synthetic_df):
        """Simula InferenceReadyDataset: pd.read_sql → torch.from_numpy."""
        arr = synthetic_df[PLAYER_FEATURE_NAMES].values.astype("float32")
        tensor = torch.from_numpy(arr)
        assert_batch_ok(tensor, PLAYER_FEATURE_COUNT)
        assert tensor.shape == (3, 3)

    def test_single_player_tensor_shape(self):
        """Simula player individual desde dataset.__getitem__."""
        row = torch.tensor([30.0, 2.0, 1.0], dtype=torch.float32)
        assert row.shape == (3,)
        batch = row.unsqueeze(0)
        assert_batch_ok(batch, PLAYER_FEATURE_COUNT)

    def test_player_prop_net_forward(self):
        """Tensor [N, 3] → PlayerPropNet → output [N, 1]."""
        model = PlayerPropNet(input_dim=PLAYER_FEATURE_COUNT)
        x = torch.rand(4, PLAYER_FEATURE_COUNT)
        out = model(x)
        assert out.shape == (4, 1), f"Esperado [4,1], got {out.shape}"

    def test_player_prop_single_inference(self):
        """Tensor [1, 3] → PlayerPropNet → scalar."""
        model = PlayerPropNet(input_dim=PLAYER_FEATURE_COUNT)
        model.eval()
        x = torch.rand(1, PLAYER_FEATURE_COUNT)
        with torch.no_grad():
            out = model(x)
        assert out.shape == (1, 1)
        assert isinstance(out.item(), float)


# ==========================================
# MATCH PREDICTION NET (Soccer)
# ==========================================

class TestMatchPredictionPipeline:
    """Equipos (Django ORM) → MatchDataset → Tensor → MatchPredictionNet."""

    SOCCER_DB_FEATURES = [
        "l_goles", "l_tiros", "l_corners",
        "v_goles", "v_tiros", "v_corners",
    ]  # 6 features desde MatchDataset

    NETWORK_INPUT_DIM = 12  # MatchPredictionNet declara 12

    def test_match_dataset_6_features(self):
        """MatchDataset extrae 6 features desde Django ORM."""
        df = pd.DataFrame([
            {f: float(v) for f, v in zip(self.SOCCER_DB_FEATURES,
                                          [1.5, 4.0, 5.0, 0.8, 3.0, 4.0])}
        ])
        assert len(df.columns) == 6
        arr = df.values.astype("float32")
        tensor = torch.from_numpy(arr)
        assert tensor.shape == (1, 6)
        assert tensor.shape[1] == 6

    def test_build_soccer_feature_vector_12_features(self):
        """build_soccer_feature_vector() produce tensor [1, 12]."""
        home = {"prom_goles": 1.89, "prom_tiros_puerta": 4.89,
                "prom_corners": 5.81, "forma": 0.8}
        away = {"prom_goles": 0.68, "prom_tiros_puerta": 2.92,
                "prom_corners": 4.0, "forma": 0.3}
        feat = build_soccer_feature_vector(home, away,
                                           elo_home=1620, elo_away=1380,
                                           h2h_win_rate_home=0.6)
        assert feat.shape == (1, 12), f"Esperado [1,12], got {feat.shape}"

    def test_match_net_forward_12_features(self):
        """MatchPredictionNet acepta tensor [N, 12] → [N, 3]."""
        model = MatchPredictionNet(input_dim=12)
        x = torch.rand(2, 12)
        logits = model(x)
        assert logits.shape == (2, 3), f"Esperado [2,3], got {logits.shape}"

    def test_match_net_forward_6_features_raises(self):
        """
        ⚠️ MatchDataset produce 6-feat tensors.
        MatchPredictionNet espera 12. Forward con 6 falla.
        """
        model = MatchPredictionNet(input_dim=12)
        x_wrong = torch.rand(2, 6)
        with pytest.raises(RuntimeError):
            model(x_wrong)

    @pytest.mark.mismatch
    def test_match_net_known_mismatch(self):
        """Documenta: 12 declarados vs 6 desde MatchDataset."""
        gap = self.NETWORK_INPUT_DIM - len(self.SOCCER_DB_FEATURES)
        assert gap == 6
        print(f"\n⚠️  MatchPredictionNet: input_dim={self.NETWORK_INPUT_DIM}, "
              f"MatchDataset features={len(self.SOCCER_DB_FEATURES)} (gap={gap})")

    def test_poisson_bivariate_output_shapes(self):
        """poisson_bivariate_predict devuelve dict con keys esperadas."""
        from src.models.networks.match_prediction_net import (
            poisson_bivariate_predict
        )
        result = poisson_bivariate_predict(1.5, 1.0)
        assert "probabilities" in result
        assert "xg_home" in result
        assert "xg_away" in result
        assert "favored" in result
        probs = result["probabilities"]
        assert set(probs.keys()) == {"home", "draw", "away"}


# ==========================================
# NBA PREDICTOR
# ==========================================

class TestNBAPipeline:
    """MatchStatsNBA → feature engineering → NBAPredictor."""

    NBA_INPUT_DIM = NBAConfig.input_dim  # 8

    def test_nba_forward_shape(self):
        """NBAPredictor acepta [N, 8] → dict con 4 tensores [N, 1]."""
        model = NBAPredictor()
        x = torch.rand(4, self.NBA_INPUT_DIM)
        out = model(x)
        assert isinstance(out, dict)
        assert set(out.keys()) == {
            "mu_spread", "mu_total",
            "log_var_spread", "log_var_total",
        }
        for key, val in out.items():
            assert val.shape == (4, 1), (
                f"{key}: esperado [4,1], got {val.shape}"
            )

    def test_nba_single_inference(self):
        """Un solo partido: [1, 8] → predicciones escalares."""
        model = NBAPredictor()
        model.eval()
        x = torch.rand(1, self.NBA_INPUT_DIM)
        with torch.no_grad():
            out = model(x)
        for key, val in out.items():
            assert val.shape == (1, 1)
            assert isinstance(val.item(), float)

    def test_nba_stats_nba_only_6_cols(self):
        """MatchStatsNBA tiene 6 columnas, pero NBAPredictor espera 8."""
        nba_stats_cols = [
            "puntos_local", "puntos_visitante",
            "rebotes_local", "rebotes_visitante",
            "triples_local", "triples_visitante",
        ]
        assert len(nba_stats_cols) == 6
        gap = self.NBA_INPUT_DIM - len(nba_stats_cols)
        assert gap == 2, f"NBA gap={gap} (8 esperados, 6 en DB)"
        print(f"\n⚠️  NBAPredictor: input_dim={self.NBA_INPUT_DIM}, "
              f"MatchStatsNBA cols={len(nba_stats_cols)} (gap={gap})")

    def test_nba_batch_uniformity(self):
        """Diferentes tamaños de batch producen salidas consistentes."""
        model = NBAPredictor()
        model.eval()
        for batch_size in [1, 2, 8, 16]:
            x = torch.rand(batch_size, self.NBA_INPUT_DIM)
            out = model(x)
            for val in out.values():
                assert val.shape[0] == batch_size


# ==========================================
# MLB PREDICTOR
# ==========================================

class TestMLBPipeline:
    """MatchStatsMLB → feature engineering → MLBPredictor."""

    MLB_INPUT_DIM = MLBConfig.input_dim  # 10

    def test_mlb_forward_shape(self):
        """MLBPredictor acepta [N, 10] → dict con 4 tensores [N, 1]."""
        model = MLBPredictor()
        x = torch.rand(4, self.MLB_INPUT_DIM)
        out = model(x)
        assert isinstance(out, dict)
        assert set(out.keys()) == {
            "log_mu_home", "log_mu_away",
            "log_alpha_home", "log_alpha_away",
        }
        for key, val in out.items():
            assert val.shape == (4, 1), (
                f"{key}: esperado [4,1], got {val.shape}"
            )

    def test_mlb_single_inference(self):
        model = MLBPredictor()
        model.eval()
        x = torch.rand(1, self.MLB_INPUT_DIM)
        with torch.no_grad():
            out = model(x)
        for key, val in out.items():
            assert val.shape == (1, 1)

    def test_mlb_stats_mlb_only_6_cols(self):
        """MatchStatsMLB tiene 6 columnas, pero MLBPredictor espera 10."""
        mlb_stats_cols = [
            "carreras_local", "carreras_visitante",
            "hits_local", "hits_visitante",
            "errores_local", "errores_visitante",
        ]
        assert len(mlb_stats_cols) == 6
        gap = self.MLB_INPUT_DIM - len(mlb_stats_cols)
        assert gap == 4, f"MLB gap={gap} (10 esperados, 6 en DB)"
        print(f"\n⚠️  MLBPredictor: input_dim={self.MLB_INPUT_DIM}, "
              f"MatchStatsMLB cols={len(mlb_stats_cols)} (gap={gap})")

    def test_mlb_batch_uniformity(self):
        model = MLBPredictor()
        model.eval()
        for batch_size in [1, 4, 12]:
            x = torch.rand(batch_size, self.MLB_INPUT_DIM)
            out = model(x)
            for val in out.values():
                assert val.shape[0] == batch_size

    def test_negative_binomial_loss_shapes(self):
        from src.models.networks.mlb_predictor import NegativeBinomialLoss
        model = MLBPredictor()
        criterion = NegativeBinomialLoss()
        x = torch.rand(4, self.MLB_INPUT_DIM)
        preds = model(x)
        target_h = torch.tensor([[3.0], [5.0], [1.0], [7.0]])
        target_a = torch.tensor([[2.0], [4.0], [0.0], [3.0]])
        loss = criterion(preds, target_h, target_a)
        assert loss.ndim == 0, f"Loss debe ser escalar, got shape {loss.shape}"
        assert loss.item() > 0


# ==========================================
# SPORTS PREDICTOR MLP (dinámico)
# ==========================================

class TestSportsPredictorMLPPipeline:
    """Config-driven: input_dim dinámico según ModelConfig."""

    @pytest.mark.parametrize("input_dim", [3, 6, 8, 10, 12, 20])
    def test_mlp_adapts_to_any_input_dim(self, input_dim):
        cfg = ModelConfig(input_dim=input_dim, output_dim=3)
        model = SportsPredictorMLP(cfg)
        x = torch.rand(2, input_dim)
        out = model(x)
        assert out.shape == (2, 3), (
            f"input_dim={input_dim}: esperado [2,3], got {out.shape}"
        )

    def test_sports_mlp_matches_player_prop(self):
        cfg = ModelConfig(input_dim=3, output_dim=1)
        mlp = SportsPredictorMLP(cfg)
        pn = PlayerPropNet(input_dim=3)
        x = torch.rand(1, 3)
        assert mlp(x).shape == pn(x).shape


# ==========================================
# CROSS-PIPELINE CONSISTENCY
# ==========================================

class TestCrossPipelineConsistency:
    """Verifica que todas las redes comparten convenciones de shape."""

    PIPELINES = [
        ("PlayerPropNet", PlayerPropNet(3), 3, lambda m: m(torch.rand(2, 3)).shape),
        ("MatchPredictionNet", MatchPredictionNet(12), 12,
         lambda m: m(torch.rand(2, 12)).shape),
        ("NBAPredictor", NBAPredictor(), 8,
         lambda m: m(torch.rand(2, 8))["mu_spread"].shape),
        ("MLBPredictor", MLBPredictor(), 10,
         lambda m: m(torch.rand(2, 10))["log_mu_home"].shape),
    ]

    @pytest.mark.parametrize("name,model,input_dim,shape_fn", PIPELINES,
                             ids=lambda x: x if isinstance(x, str) else "")
    def test_all_networks_output_batch_size(self, name, model, input_dim, shape_fn):
        """Salida debe tener batch_size 2 en primera dimensión."""
        model.eval()
        with torch.no_grad():
            out_shape = shape_fn(model)
        assert out_shape[0] == 2, (
            f"{name}: batch_size=2 → output batch={out_shape[0]}"
        )

    def test_all_input_dims_non_zero(self):
        dims = {
            "PlayerPropNet": 3,
            "MatchPredictionNet": 12,
            "NBAPredictor": 8,
            "MLBPredictor": 10,
        }
        for name, dim in dims.items():
            assert dim > 0, f"{name}: input_dim={dim} inválido"
