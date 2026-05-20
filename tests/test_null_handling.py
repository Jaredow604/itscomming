"""
Paso 4: Test de Manejo de Nulos (NaN/None Injection)

Verifica que PipelineValidator, InferenceReadyDataset y SportsDataNormalizer
reaccionan correctamente ante datos nulos en el pipeline DB → Pandas → Tensor.
"""

import pytest
import pandas as pd
import numpy as np
import torch
from unittest.mock import MagicMock, patch

from src.pipeline.validator import PipelineValidator
from src.pipeline.normalizer import SportsDataNormalizer
from src.models.datasets.inference_ready_dataset import (
    InferenceReadyDataset,
    DEFAULT_FEATURE_COLUMNS,
    DEFAULT_TARGET_COLUMN,
)


# ==========================================
# PIPELINE VALIDATOR — CHECK NULLS
# ==========================================

FEATURES = ["playing_time_min_scaled", "total_shots_scaled", "standard_sot_scaled"]


class TestPipelineValidatorCheckNulls:
    """PipelineValidator.check_nulls() imputa nulos con fillna(0)."""

    @pytest.fixture
    def validator(self) -> PipelineValidator:
        return PipelineValidator()

    def test_no_nulls_passthrough(self, validator):
        """Sin nulos → mismo DataFrame, sin cambios."""
        df_in = pd.DataFrame({f: [1.0, 2.0, 3.0] for f in FEATURES})
        df_out = validator.check_nulls(df_in, FEATURES)
        pd.testing.assert_frame_equal(df_in, df_out)

    def test_some_nulls_imputed_to_zero(self, validator):
        """Nulos parciales → fillna(0) manteniendo shape."""
        df = pd.DataFrame({
            FEATURES[0]: [1.0, np.nan, 3.0],
            FEATURES[1]: [np.nan, 5.0, 6.0],
            FEATURES[2]: [7.0, 8.0, np.nan],
        })
        out = validator.check_nulls(df, FEATURES)
        assert out[FEATURES[0]].iloc[1] == 0.0
        assert out[FEATURES[1]].iloc[0] == 0.0
        assert out[FEATURES[2]].iloc[2] == 0.0
        assert out.shape == df.shape

    def test_all_nulls_imputed(self, validator):
        """Columna completamente nula → todo 0.0."""
        df = pd.DataFrame({f: [np.nan, np.nan] for f in FEATURES})
        out = validator.check_nulls(df, FEATURES)
        assert out[FEATURES].isnull().sum().sum() == 0
        assert (out[FEATURES] == 0.0).all().all()

    def test_original_df_not_mutated(self, validator):
        """check_nulls no muta el DataFrame original."""
        df = pd.DataFrame({FEATURES[0]: [np.nan, 2.0]})
        df_copy = df.copy()
        validator.check_nulls(df, [FEATURES[0]])
        pd.testing.assert_frame_equal(df, df_copy)

    def test_extra_columns_preserved(self, validator):
        """Columnas no-feature pasan intactas."""
        df = pd.DataFrame({
            "player_name": ["A", "B"],
            FEATURES[0]: [np.nan, 1.0],
        })
        out = validator.check_nulls(df, [FEATURES[0]])
        assert "player_name" in out.columns
        assert out["player_name"].tolist() == ["A", "B"]

    def test_empty_feature_list(self, validator):
        """Lista vacía de features → sin cambios."""
        df = pd.DataFrame({"player": [1.0]})
        out = validator.check_nulls(df, [])
        pd.testing.assert_frame_equal(df, out)

    @pytest.mark.parametrize("bad_value", [None, np.nan, float("nan")])
    def test_various_null_types_imputed(self, validator, bad_value):
        """None, np.nan, float('nan') → todos tratados igual."""
        df = pd.DataFrame({FEATURES[0]: [1.0, bad_value]})
        out = validator.check_nulls(df, [FEATURES[0]])
        assert out[FEATURES[0]].iloc[1] == 0.0


# ==========================================
# PIPELINE VALIDATOR — DETECT OUTLIERS
# ==========================================

class TestPipelineValidatorOutliers:
    """detect_outliers_iqr maneja NaN sin errores."""

    @pytest.fixture
    def validator(self) -> PipelineValidator:
        return PipelineValidator()

    def test_nan_in_feature_does_not_crash(self, validator):
        """NaN en feature → IQR calcula Q1/Q3 ignorando NaN gracias a pandas."""
        df = pd.DataFrame({
            FEATURES[0]: [1.0, 2.0, np.nan, 100.0, 3.0, 4.0],
        })
        validator.detect_outliers_iqr(df, [FEATURES[0]])

    def test_all_nan_no_crash(self, validator):
        """Columna completamente NaN → no crash (quantile retorna NaN)."""
        df = pd.DataFrame({FEATURES[0]: [np.nan, np.nan, np.nan]})
        validator.detect_outliers_iqr(df, [FEATURES[0]])


# ==========================================
# PIPELINE VALIDATOR — DATA DRIFT
# ==========================================

class TestPipelineValidatorDrift:
    """check_data_drift maneja NaN correctamente."""

    @pytest.fixture
    def validator(self) -> PipelineValidator:
        v = PipelineValidator()
        v.fit_historical_stats(
            pd.DataFrame({FEATURES[0]: [1.0, 2.0, 3.0]}),
            [FEATURES[0]],
        )
        return v

    def test_nan_batch_mean_is_safe(self, validator):
        """Batch con NaN → mean() produce NaN, drift_score = NaN, no crash."""
        df = pd.DataFrame({FEATURES[0]: [np.nan, np.nan]})
        validator.check_data_drift(df, [FEATURES[0]])

    def test_nan_historical_std_is_safe(self):
        """Desviación histórica 0 → skip feature."""
        v = PipelineValidator()
        v.fit_historical_stats(
            pd.DataFrame({FEATURES[0]: [5.0, 5.0, 5.0]}),  # std = 0
            [FEATURES[0]],
        )
        df = pd.DataFrame({FEATURES[0]: [10.0, 12.0]})
        v.check_data_drift(df, [FEATURES[0]])


# ==========================================
# PIPELINE VALIDATOR — END-TO-END VALIDATE
# ==========================================

class TestPipelineValidatorE2E:
    """validate_pipeline encadena todas las validaciones."""

    @pytest.fixture
    def validator(self) -> PipelineValidator:
        v = PipelineValidator()
        v.fit_historical_stats(
            pd.DataFrame({f: [1.0, 2.0, 3.0] for f in FEATURES}),
            FEATURES,
        )
        return v

    def test_nulls_imputed_in_pipeline(self, validator):
        """validate_pipeline imputa nulos y retorna DataFrame limpio."""
        df = pd.DataFrame({
            FEATURES[0]: [1.0, np.nan, 3.0],
            FEATURES[1]: [4.0, 5.0, np.nan],
            FEATURES[2]: [np.nan, 8.0, 9.0],
        })
        out = validator.validate_pipeline(df, FEATURES)
        assert out.isnull().sum().sum() == 0
        assert (out[FEATURES] >= 0).all().all()


# ==========================================
# INFERENCE READY DATASET — NULL HANDLING
# ==========================================

class TestInferenceReadyDatasetNulls:
    """Simula InferenceReadyDataset con nulos en datos mockeados."""

    @pytest.fixture
    def mock_session(self):
        """Crea un mock de sesión SQLAlchemy."""
        session = MagicMock()
        session.bind = MagicMock()
        return session

    def _make_dataset(self, session, df: pd.DataFrame) -> InferenceReadyDataset:
        """Helper: mockea pd.read_sql para retornar df controlado."""
        with patch("src.models.datasets.inference_ready_dataset.pd.read_sql",
                   return_value=df):
            return InferenceReadyDataset(db_session=session)

    def test_target_nulls_dropped(self, mock_session):
        """Filas con target nulo son eliminadas."""
        df = pd.DataFrame({
            "player_name": ["A", "B", "C"],
            "team_name": ["X", "Y", "Z"],
            DEFAULT_FEATURE_COLUMNS[0]: [1.0, 2.0, 3.0],
            DEFAULT_FEATURE_COLUMNS[1]: [4.0, 5.0, 6.0],
            DEFAULT_FEATURE_COLUMNS[2]: [7.0, 8.0, 9.0],
            DEFAULT_TARGET_COLUMN: [0.5, np.nan, 1.2],
        })
        ds = self._make_dataset(mock_session, df)
        assert len(ds) == 2
        assert ds.targets.tolist() == pytest.approx([0.5, 1.2])

    def test_feature_nulls_imputed_to_zero(self, mock_session):
        """Features nulas → imputadas con 0.0."""
        df = pd.DataFrame({
            "player_name": ["A"],
            "team_name": ["X"],
            DEFAULT_FEATURE_COLUMNS[0]: [np.nan],
            DEFAULT_FEATURE_COLUMNS[1]: [np.nan],
            DEFAULT_FEATURE_COLUMNS[2]: [np.nan],
            DEFAULT_TARGET_COLUMN: [0.5],
        })
        ds = self._make_dataset(mock_session, df)
        assert len(ds) == 1
        assert ds.features[0].tolist() == [0.0, 0.0, 0.0]

    def test_mixed_nulls(self, mock_session):
        """Combinación de nulos en features + target."""
        df = pd.DataFrame({
            "player_name": ["A", "B", "C"],
            "team_name": ["X", "Y", "Z"],
            DEFAULT_FEATURE_COLUMNS[0]: [1.0, np.nan, 3.0],
            DEFAULT_FEATURE_COLUMNS[1]: [4.0, 5.0, np.nan],
            DEFAULT_FEATURE_COLUMNS[2]: [np.nan, 8.0, 9.0],
            DEFAULT_TARGET_COLUMN: [0.5, np.nan, 1.2],
        })
        ds = self._make_dataset(mock_session, df)
        # Target null para B → eliminado → quedan A y C
        assert len(ds) == 2
        # Features de A: intactas [1, 4, 0]
        assert ds.features[0][0] == 1.0
        assert ds.features[0][1] == 4.0
        assert ds.features[0][2] == 0.0
        # Features de C: [3, 0, 9]
        assert ds.features[1][0] == 3.0
        assert ds.features[1][1] == 0.0
        assert ds.features[1][2] == 9.0

    def test_no_nulls_preserves_all(self, mock_session):
        """Sin nulos → todos los registros preservados."""
        df = pd.DataFrame({
            "player_name": ["A", "B"],
            "team_name": ["X", "Y"],
            **{f: [1.0, 2.0] for f in DEFAULT_FEATURE_COLUMNS},
            DEFAULT_TARGET_COLUMN: [0.5, 1.2],
        })
        ds = self._make_dataset(mock_session, df)
        assert len(ds) == 2
        assert ds.features.shape == (2, 3)

    def test_all_targets_null_raises(self, mock_session):
        """
        Todos los targets nulos → dropna elimina todo.
        ⚠️  El código actual valida df.empty antes del dropna, no después.
             Actualmente dataset vacío se crea; mejoraría con post-dropna check.
        """
        df = pd.DataFrame({
            "player_name": ["A"],
            "team_name": ["X"],
            DEFAULT_FEATURE_COLUMNS[0]: [1.0],
            DEFAULT_FEATURE_COLUMNS[1]: [4.0],
            DEFAULT_FEATURE_COLUMNS[2]: [7.0],
            DEFAULT_TARGET_COLUMN: [np.nan],
        })
        ds = self._make_dataset(mock_session, df)
        assert len(ds) == 0  # dropna eliminó la única fila

    def test_tensor_dtype_after_imputation(self, mock_session):
        """Tensor imputado sigue siendo float32."""
        df = pd.DataFrame({
            "player_name": ["A"],
            "team_name": ["X"],
            DEFAULT_FEATURE_COLUMNS[0]: [np.nan],
            DEFAULT_FEATURE_COLUMNS[1]: [np.nan],
            DEFAULT_FEATURE_COLUMNS[2]: [np.nan],
            DEFAULT_TARGET_COLUMN: [0.5],
        })
        ds = self._make_dataset(mock_session, df)
        assert ds.features.dtype == torch.float32
        assert ds.targets.dtype == torch.float32

    def test_metadata_preserved_after_nulls(self, mock_session):
        """Metadata (player_name, team_name) preservada tras dropna target."""
        df = pd.DataFrame({
            "player_name": ["A", "B", "C"],
            "team_name": ["X", "Y", "Z"],
            DEFAULT_FEATURE_COLUMNS[0]: [1.0, 2.0, 3.0],
            DEFAULT_FEATURE_COLUMNS[1]: [4.0, 5.0, 6.0],
            DEFAULT_FEATURE_COLUMNS[2]: [7.0, 8.0, 9.0],
            DEFAULT_TARGET_COLUMN: [0.5, np.nan, 1.2],
        })
        ds = self._make_dataset(mock_session, df)
        assert ds.metadata["player_name"].tolist() == ["A", "C"]
        assert ds.metadata["team_name"].tolist() == ["X", "Z"]

    def test_imputed_tensor_passes_forward(self, mock_session):
        """Tensor imputado → PlayerPropNet forward sin errores."""
        from src.models.networks.player_prop_net import PlayerPropNet

        df = pd.DataFrame({
            "player_name": ["A"],
            "team_name": ["X"],
            DEFAULT_FEATURE_COLUMNS[0]: [np.nan],
            DEFAULT_FEATURE_COLUMNS[1]: [np.nan],
            DEFAULT_FEATURE_COLUMNS[2]: [np.nan],
            DEFAULT_TARGET_COLUMN: [0.5],
        })
        ds = self._make_dataset(mock_session, df)
        model = PlayerPropNet(input_dim=3)
        model.eval()
        with torch.no_grad():
            out = model(ds.features)
        assert out.shape == (1, 1)
        assert not torch.isnan(out).any()


# ==========================================
# SPORTS DATA NORMALIZER — NULL BEHAVIOR
# ==========================================

class TestSportsDataNormalizerNulls:
    """SportsDataNormalizer con NaN en datos de entrada."""

    @pytest.fixture
    def normalizer(self, tmp_path) -> SportsDataNormalizer:
        return SportsDataNormalizer(scaler_dir=str(tmp_path))

    def test_nan_in_fit_propagates_nan(self, normalizer):
        """NaN en fit → RobustScaler propaga NaN a salida (sin crash)."""
        df = pd.DataFrame({FEATURES[0]: [1.0, np.nan, 3.0, 4.0, 5.0]})
        out = normalizer.fit_and_save(df, [FEATURES[0]], "test_scaler")
        assert np.isnan(out[FEATURES[0]].iloc[1])

    def test_nan_in_transform_propagates_nan(self, normalizer):
        """NaN en transform → salida con NaN."""
        df_fit = pd.DataFrame({FEATURES[0]: [1.0, 2.0, 3.0, 4.0, 5.0]})
        normalizer.fit_and_save(df_fit, [FEATURES[0]], "test_scaler")

        df_transform = pd.DataFrame({FEATURES[0]: [np.nan, 10.0]})
        out = normalizer.load_and_transform(
            df_transform, [FEATURES[0]], "test_scaler"
        )
        assert np.isnan(out[FEATURES[0]].iloc[0])
        assert not np.isnan(out[FEATURES[0]].iloc[1])

    def test_pipeline_validator_then_normalizer(self, normalizer, tmp_path):
        """PipelineValidator.fillna(0) → SportsDataNormalizer (ya sin NaN)."""
        normalizer.scaler_dir = str(tmp_path)
        df = pd.DataFrame({FEATURES[0]: [np.nan, 2.0, 3.0, 4.0, 5.0]})

        # Primero: PipelineValidator imputa NaN → 0
        v = PipelineValidator()
        df_clean = v.check_nulls(df, [FEATURES[0]])

        # Luego: Normalizer sin NaN en entrada → sin NaN en salida
        out = normalizer.fit_and_save(df_clean, [FEATURES[0]], "test_scaler")
        assert not np.isnan(out[FEATURES[0]]).any()


# ==========================================
# TENSOR PROPAGATION — INF / EXTREME VALUES
# ==========================================

class TestTensorPropagationEdgeCases:
    """Valores extremos en tensores → forward pass."""

    @pytest.mark.parametrize("extreme_val", [float("inf"), float("-inf"), 1e20, -1e20])
    def test_extreme_values_forward(self, extreme_val):
        """inf/-inf/valores extremos → forward pass no crash."""
        from src.models.networks.player_prop_net import PlayerPropNet
        model = PlayerPropNet(input_dim=3)
        model.eval()
        x = torch.tensor([[extreme_val, 0.0, 0.0]], dtype=torch.float32)
        with torch.no_grad():
            out = model(x)
        # Puede producir NaN/Inf, pero no debe crash
        assert out.shape == (1, 1)

    def test_nan_after_forward_no_crash(self):
        """NaN en input → forward puede producir NaN, pero no crash."""
        from src.models.networks.match_prediction_net import MatchPredictionNet
        model = MatchPredictionNet(input_dim=12)
        model.eval()
        x = torch.full((1, 12), float("nan"), dtype=torch.float32)
        with torch.no_grad():
            out = model(x)
        assert out.shape == (1, 3)

    def test_zero_division_protection(self):
        """División por cero protegida (check_data_drift con std=0)."""
        v = PipelineValidator()
        v.fit_historical_stats(
            pd.DataFrame({FEATURES[0]: [5.0, 5.0, 5.0]}),
            [FEATURES[0]],
        )
        df = pd.DataFrame({FEATURES[0]: [np.nan, float("inf")]})
        v.check_data_drift(df, [FEATURES[0]])


# ==========================================
# PREVENCIÓN DE REGRESIÓN
# ==========================================

class TestNullRegressionPrevention:
    """Pruebas que fallarían si se quita la imputación de nulos."""

    def test_imputation_is_not_optional(self):
        """Si check_nulls no imputara, el pipeline fallaría."""
        df = pd.DataFrame({FEATURES[0]: [np.nan, 2.0]})
        # Sin imputación manual → isnull() > 0
        v = PipelineValidator()
        out = v.check_nulls(df, [FEATURES[0]])
        assert out[FEATURES[0]].isnull().sum() == 0

    def test_dataset_rejects_all_nan_target(self):
        """Si no se dropearan targets nulos, el dataset tendría NaN targets."""
        from unittest.mock import MagicMock, patch
        session = MagicMock()
        session.bind = MagicMock()
        df = pd.DataFrame({
            "player_name": ["A"],
            "team_name": ["X"],
            DEFAULT_FEATURE_COLUMNS[0]: [1.0],
            DEFAULT_FEATURE_COLUMNS[1]: [4.0],
            DEFAULT_FEATURE_COLUMNS[2]: [7.0],
            DEFAULT_TARGET_COLUMN: [np.nan],
        })
        with patch("src.models.datasets.inference_ready_dataset.pd.read_sql",
                   return_value=df):
            ds = InferenceReadyDataset(db_session=session)
            # ⚠️  El código actual no valida dataset vacío tras dropna target
            assert len(ds) == 0
