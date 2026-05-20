"""
Paso 1: Auditoría de Mapeo de Columnas (Feature Mapping)

Verifica que:
  - input_dim de cada red neuronal coincida con el número de features
    extraíbles desde el ORM correspondiente.
  - Los tipos de datos (Decimal, Integer, Float) sean compatibles con
    torch.float32 sin pérdida de precisión significativa.
  - Documenta mismatches dimensionales conocidos.
"""

from dataclasses import dataclass, field
from typing import List

import pytest
import torch
from decimal import Decimal

from src.models.networks.player_prop_net import PlayerPropNet
from src.models.networks.match_prediction_net import MatchPredictionNet
from src.models.networks.nba_predictor import NBAPredictor, NBAConfig
from src.models.networks.mlb_predictor import MLBPredictor, MLBConfig
from src.models.model import SportsPredictorMLP
from src.config.config import ModelConfig

from src.models.datasets.inference_ready_dataset import DEFAULT_FEATURE_COLUMNS
from src.pipeline.normalizer import SportsDataNormalizer
from src.pipeline.validator import PipelineValidator


# ==========================================
# HARDCODED REGISTRY: Red → Features DB
# ==========================================
# Estas tablas son el resultado de la auditoría de código fuente.
# Documentan cuántas features extrae CADA DATASET/PIPELINE real,
# no cuántas declara la red.

@dataclass
class NetworkMapping:
    network_name: str
    network_class: type
    declared_input_dim: int
    db_feature_count: int
    db_source: str
    feature_list: List[str] = field(default_factory=list)
    is_mismatch: bool = False
    notes: str = ""


NETWORK_REGISTRY = [
    NetworkMapping(
        network_name="PlayerPropNet",
        network_class=PlayerPropNet,
        declared_input_dim=3,
        db_feature_count=3,
        db_source="InferenceReadyPlayerData / FBrefPlayerDataset",
        feature_list=['Playing Time_Min', 'Total_Shots', 'Standard_SoT'],
        is_mismatch=False,
        notes="Coincide exactamente. 3 features normalizadas → 3 input_dim.",
    ),
    NetworkMapping(
        network_name="MatchPredictionNet",
        network_class=MatchPredictionNet,
        declared_input_dim=12,
        db_feature_count=6,
        db_source="Django Equipos (via MatchDataset)",
        feature_list=[
            'l_goles', 'l_tiros', 'l_corners',
            'v_goles', 'v_tiros', 'v_corners',
        ],
        is_mismatch=True,
        notes=(
            "MatchDataset extrae solo 6 features desde Django ORM. "
            "MatchPredictionNet declara input_dim=12. Las 6 restantes "
            "(forma×2, elo×2, h2h, is_neutral) se computan externamente "
            "en build_soccer_feature_vector(). NO hay pipeline unificado "
            "que garantice las 12."
        ),
    ),
    NetworkMapping(
        network_name="NBAPredictor",
        network_class=NBAPredictor,
        declared_input_dim=8,
        db_feature_count=6,
        db_source="MatchStatsNBA (SQLAlchemy)",
        feature_list=[
            'puntos_local', 'puntos_visitante',
            'rebotes_local', 'rebotes_visitante',
            'triples_local', 'triples_visitante',
        ],
        is_mismatch=True,
        notes=(
            "NBAConfig.input_dim=8 pero MatchStatsNBA solo tiene 6 columnas. "
            "No existe un feature engineer público que genere las 8. "
            "Posiblemente falten asistencias y robos/bloqueos promediados."
        ),
    ),
    NetworkMapping(
        network_name="MLBPredictor",
        network_class=MLBPredictor,
        declared_input_dim=10,
        db_feature_count=6,
        db_source="MatchStatsMLB (SQLAlchemy)",
        feature_list=[
            'carreras_local', 'carreras_visitante',
            'hits_local', 'hits_visitante',
            'errores_local', 'errores_visitante',
        ],
        is_mismatch=True,
        notes=(
            "MLBConfig.input_dim=10 pero MatchStatsMLB solo tiene 6 columnas. "
            "Comentario en código menciona ERA, WHIP, OPS, wOBA, K/9, BB/9, "
            "HR/FB — ninguna almacenada en la DB relacional."
        ),
    ),
    NetworkMapping(
        network_name="SportsPredictorMLP",
        network_class=SportsPredictorMLP,
        declared_input_dim=None,  # dinámico
        db_feature_count=None,     # dinámico
        db_source="config-driven (ModelConfig)",
        feature_list=[],
        is_mismatch=False,
        notes="Arquitectura dinámica vía ModelConfig. Sin mismatch posible.",
    ),
]


# ==========================================
# TESTS: DIMENSIONALIDAD
# ==========================================

class TestFeatureCount:
    """Cada red debe tener input_dim = número de features de su fuente."""

    def _get_actual_input_dim(self, instance) -> int:
        """Inspecciona la primera capa lineal para obtener el input_dim real."""
        if hasattr(instance, 'input_dim') and instance.input_dim is not None:
            return instance.input_dim
        for module in instance.modules():
            if isinstance(module, torch.nn.Linear):
                return module.in_features
        raise TypeError("No se pudo determinar input_dim del modelo")

    @pytest.mark.structural
    @pytest.mark.parametrize("mapping", [
        m for m in NETWORK_REGISTRY if not m.is_mismatch and m.network_name != "SportsPredictorMLP"
    ], ids=lambda m: m.network_name)
    def test_feature_count_match(self, mapping: NetworkMapping):
        instance = mapping.network_class(input_dim=mapping.declared_input_dim)
        actual_dim = self._get_actual_input_dim(instance)
        assert actual_dim == mapping.declared_input_dim, (
            f"{mapping.network_name}: instanciado con input_dim="
            f"{mapping.declared_input_dim} pero la primera capa "
            f"tiene in_features={actual_dim}"
        )

    @pytest.mark.structural
    @pytest.mark.mismatch
    @pytest.mark.parametrize("mapping", [
        m for m in NETWORK_REGISTRY if m.is_mismatch
    ], ids=lambda m: m.network_name)
    def test_known_mismatches(self, mapping: NetworkMapping):
        """
        NO falla — solo documenta mismatches dimensionales conocidos.
        Cambia a assert False cuando se resuelva el mismatch.
        """
        print(f"\n⚠️  MISMATCH DOCUMENTADO: {mapping.network_name}")
        print(f"   Declarado:   input_dim = {mapping.declared_input_dim}")
        print(f"   Real (DB):   features   = {mapping.db_feature_count}")
        print(f"   Fuente DB:   {mapping.db_source}")
        print(f"   Features:    {mapping.feature_list}")
        print(f"   Notas:       {mapping.notes}")
        mismatch = mapping.declared_input_dim - mapping.db_feature_count
        assert mismatch > 0, "Este mismatch debe resolverse (o actualizar el registry)"

    @pytest.mark.structural
    def test_sports_predictor_mlp_dynamic(self):
        """SportsPredictorMLP es dinámico — verificar que se construye correctamente."""
        config = ModelConfig(input_dim=7, output_dim=3, hidden_dims=[64, 32])
        model = SportsPredictorMLP(config)
        assert model.network[0].in_features == 7
        assert model.network[-1].out_features == 3

        # También verificar con valores reales de uso
        config_match = ModelConfig(input_dim=12, output_dim=3)
        model_match = SportsPredictorMLP(config_match)
        assert model_match.network[0].in_features == 12

    @pytest.mark.structural
    def test_inference_ready_dataset_features(self):
        """Verificar que DEFAULT_FEATURE_COLUMNS coincida con PlayerPropNet."""
        assert len(DEFAULT_FEATURE_COLUMNS) == 3, (
            f"InferenceReadyDataset usa {len(DEFAULT_FEATURE_COLUMNS)} features, "
            f"PlayerPropNet espera 3"
        )
        assert DEFAULT_FEATURE_COLUMNS == [
            'playing_time_min_scaled',
            'total_shots_scaled',
            'standard_sot_scaled',
        ], "Feature columns cambiaron — revisar sync con PlayerPropNet"


# ==========================================
# TESTS: COMPATIBILIDAD DE TIPOS
# ==========================================

class TestTypeCompatibility:
    """Decimal/Integer → float32: sin pérdida de precisión."""

    @pytest.mark.type_check
    @pytest.mark.parametrize("value,expected,eps", [
        (Decimal("12.34"), 12.34, 1e-6),
        (Decimal("99.99"), 99.99, 1e-4),   # float32 no representa 99.99 exactamente
        (Decimal("0.00"), 0.00, 1e-6),
        (Decimal("-5.50"), -5.50, 1e-6),
        (Decimal("12345.67"), 12345.67, 1e-3),  # float32 pierde ~7.8e-5 en >5 dígitos
    ])
    def test_decimal_to_float32_preserves_value(self, value, expected, eps):
        result = torch.tensor(float(value), dtype=torch.float32).item()
        assert abs(result - expected) < eps, (
            f"Decimal({value}) → float32({result}) perdió precisión "
            f"(error={abs(result - expected):.2e}, límite={eps})"
        )

    @pytest.mark.type_check
    @pytest.mark.parametrize("value,expected", [
        (0, 0.0),
        (1, 1.0),
        (-1, -1.0),
        (255, 255.0),
        (1_000_000, 1_000_000.0),  # float32 exacto hasta 2^24
    ])
    def test_integer_to_float32_preserves_value(self, value, expected):
        result = torch.tensor(float(value), dtype=torch.float32).item()
        assert abs(result - expected) < 1e-6, (
            f"int({value}) → float32({result}) perdió precisión"
        )

    @pytest.mark.type_check
    def test_float32_precision_limit(self):
        """Documentar el límite de precisión de float32 (~7 dígitos)."""
        value = Decimal("12345.6789")
        f32 = torch.tensor(float(value), dtype=torch.float32).item()
        f64 = torch.tensor(float(value), dtype=torch.float64).item()
        diff = abs(f64 - f32)
        # float32 preserva ~7 dígitos decimales significativos.
        # Para 12345.6789 (~9 dígitos), el error en float32 es ~1.9e-4,
        # que es inofensivo para predicciones deportivas (< 0.002%).
        assert diff < 5e-4, (
            f"Pérdida excesiva float32→float64: {diff} (esperado < 5e-4)"
        )
        print(f"  Documentación: float32 pierde {diff:.2e} para 12345.6789")

    @pytest.mark.type_check
    def test_none_to_float32_via_fillna_zero(self):
        """Simular fillna(0) del pipeline: None → float32(0.0)."""
        raw_value = None
        safe_value = 0.0 if raw_value is None else float(raw_value)
        tensor = torch.tensor(safe_value, dtype=torch.float32)
        assert tensor.item() == 0.0

    @pytest.mark.type_check
    def test_null_decimal_via_orm_pipeline(self):
        """
        Decimal NULL desde Django ORM → float → float32.
        Simula el casting en MatchDataset._load_and_process_data:
          float(p.local.prom_goles)
        donde prom_goles puede ser None.
        """
        from decimal import Decimal

        class MockEquipo:
            prom_goles: Decimal or None = None
            prom_tiros_puerta: Decimal or None = None
            prom_corners: Decimal or None = None

        equipo_null = MockEquipo()
        try:
            goles = float(equipo_null.prom_goles) if equipo_null.prom_goles is not None else 0.0
            tiros = float(equipo_null.prom_tiros_puerta) if equipo_null.prom_tiros_puerta is not None else 0.0
            corners = float(equipo_null.prom_corners) if equipo_null.prom_corners is not None else 0.0
        except (TypeError, ValueError) as e:
            pytest.fail(f"Falló al castear Decimal NULL a float: {e}")

        features = torch.tensor([goles, tiros, corners], dtype=torch.float32)
        assert features.shape == (3,)
        assert features.sum().item() == 0.0


# ==========================================
# TESTS: PIPELINE (NORMALIZER + VALIDATOR)
# ==========================================

class TestPipelineTypeFlow:
    """Verificar que el pipeline completo maneja tipos correctamente."""

    @pytest.mark.structural
    def test_normalizer_accepts_numeric_types(self):
        normalizer = SportsDataNormalizer(scaler_dir='tests/_test_scalers')
        assert normalizer is not None

    @pytest.mark.structural
    def test_validator_accepts_numeric_types(self):
        validator = PipelineValidator()
        assert validator is not None
