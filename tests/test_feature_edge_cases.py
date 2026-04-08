"""Tests for feature engine edge cases — NaN handling, spike score bounds, temperature smoothing."""

import numpy as np
import pandas as pd

from efuse_datagen.config.models import FeatureConfig
from efuse_datagen.features.engine import FeatureEngine


def _make_telemetry(n: int = 100, current_a: float = 5.0, seed: int = 42) -> pd.DataFrame:
    """Build a minimal telemetry DataFrame for feature computation."""
    rng = np.random.default_rng(seed)
    timestamps = pd.date_range("2026-01-01", periods=n, freq="100ms")
    return pd.DataFrame({
        "channel_id": "ch_01",
        "timestamp": timestamps,
        "current_a": current_a + rng.normal(0, 0.1, n),
        "temperature_c": 25.0 + np.linspace(0, 5, n) + rng.normal(0, 0.2, n),
        "voltage_v": 13.5 + rng.normal(0, 0.05, n),
        "nominal_voltage_v": 13.5,
        "trip_flag": False,
    })


class TestRollingRmsBackfill:
    def test_no_nan_in_rolling_rms(self):
        df = _make_telemetry(n=20)
        engine = FeatureEngine(FeatureConfig(window_duration_s=1.0))
        result = engine.compute(df)
        assert result["rolling_rms_current"].isna().sum() == 0

    def test_rolling_rms_non_negative(self):
        df = _make_telemetry()
        engine = FeatureEngine()
        result = engine.compute(df)
        assert (result["rolling_rms_current"] >= 0).all()


class TestSpikeScoreCapped:
    def test_spike_score_capped_at_20(self):
        df = _make_telemetry(n=200)
        # Inject an extreme spike
        df.loc[100, "current_a"] = 1000.0
        engine = FeatureEngine()
        result = engine.compute(df)
        assert result["spike_score"].max() <= 20.0

    def test_spike_score_non_negative(self):
        df = _make_telemetry()
        engine = FeatureEngine()
        result = engine.compute(df)
        assert (result["spike_score"] >= 0).all()

    def test_spike_score_zero_std_handled(self):
        """When all current values are identical, std=0 should not produce inf."""
        df = _make_telemetry()
        df["current_a"] = 5.0  # constant — std will be 0
        engine = FeatureEngine()
        result = engine.compute(df)
        assert not np.isinf(result["spike_score"]).any()
        assert result["spike_score"].isna().sum() == 0


class TestTemperatureSlopeSmoothing:
    def test_temperature_slope_no_nan(self):
        df = _make_telemetry()
        engine = FeatureEngine()
        result = engine.compute(df)
        assert result["temperature_slope"].isna().sum() == 0

    def test_temperature_slope_bounded_with_noise(self):
        """Slope should be damped by smoothing even with noisy temperature."""
        rng = np.random.default_rng(99)
        df = _make_telemetry()
        # Add large noise spikes
        df["temperature_c"] = 25.0 + rng.normal(0, 5, len(df))
        engine = FeatureEngine()
        result = engine.compute(df)
        # With smoothing, slope magnitude should stay reasonable
        assert result["temperature_slope"].abs().max() < 50.0
