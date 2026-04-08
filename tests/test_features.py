"""Tests for efuse_datagen.features.engine – FeatureEngine."""

import pandas as pd

from efuse_datagen.features.engine import FeatureEngine
from efuse_datagen.config.models import FeatureConfig
from efuse_datagen.schemas.telemetry import ProtectionEvent
from efuse_datagen.simulation.generator import TelemetryGenerator
from tests.conftest import make_config


def _generate_telemetry(**cfg_overrides) -> pd.DataFrame:
    """Helper: generate raw telemetry for feature tests."""
    cfg = make_config(duration_s=20.0, sample_interval_ms=100.0, **cfg_overrides)
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()
    return df


class TestRollingStatistics:
    """Rolling current/voltage statistics columns."""

    def test_rolling_columns_present(self):
        df = _generate_telemetry()
        fe = FeatureEngine()
        out = fe.compute(df)
        expected = {
            "rolling_rms_current",
            "rolling_mean_current",
            "rolling_max_current",
            "rolling_min_current",
            "temperature_slope",
            "spike_score",
            "trip_frequency",
            "recovery_time_s",
            "degradation_trend",
        }
        assert expected.issubset(set(out.columns)), f"Missing: {expected - set(out.columns)}"

    def test_rolling_mean_within_bounds(self):
        df = _generate_telemetry()
        out = FeatureEngine().compute(df)
        # Rolling mean should be between rolling min and rolling max
        valid = out.dropna(subset=["rolling_mean_current", "rolling_min_current", "rolling_max_current"])
        assert (valid["rolling_mean_current"] >= valid["rolling_min_current"] - 1e-9).all()
        assert (valid["rolling_mean_current"] <= valid["rolling_max_current"] + 1e-9).all()

    def test_rms_at_least_mean(self):
        df = _generate_telemetry()
        out = FeatureEngine().compute(df)
        valid = out.dropna(subset=["rolling_rms_current", "rolling_mean_current"])
        # RMS >= |mean| for non-negative currents
        assert (valid["rolling_rms_current"] >= valid["rolling_mean_current"].abs() - 1e-9).all()


class TestSpikeScore:
    """spike_score should be >= 0 and peak on faults."""

    def test_spike_score_non_negative(self):
        df = _generate_telemetry()
        out = FeatureEngine().compute(df)
        assert (out["spike_score"].dropna() >= -1e-9).all()

    def test_spike_score_elevated_on_fault(self):
        from efuse_datagen.schemas.telemetry import FaultInjection, FaultType

        cfg = make_config(
            duration_s=20.0,
            sample_interval_ms=100.0,
            fault_injections=[
                FaultInjection(
                    channel_id="ch_01",
                    fault_type=FaultType.OVERLOAD_SPIKE,
                    start_s=8.0,
                    duration_s=2.0,
                    intensity=0.9,
                ),
            ],
        )
        gen = TelemetryGenerator(cfg)
        df, _ = gen.generate()
        out = FeatureEngine().compute(df)
        t0 = out["timestamp"].min()
        fault_window = out[
            (out["timestamp"] > t0 + pd.Timedelta(seconds=8))
            & (out["timestamp"] < t0 + pd.Timedelta(seconds=11))
        ]
        nominal = out[out["timestamp"] < t0 + pd.Timedelta(seconds=7)]
        assert fault_window["spike_score"].max() > nominal["spike_score"].median() + 0.5


class TestProtectionFeatures:
    """Protection-event rate and per-mechanism count columns."""

    def test_protection_event_rate_present(self):
        df = _generate_telemetry()
        out = FeatureEngine().compute(df)
        assert "protection_event_rate" in out.columns

    def test_per_mechanism_count_columns(self):
        df = _generate_telemetry()
        out = FeatureEngine().compute(df)
        for event in (
            ProtectionEvent.SCP,
            ProtectionEvent.I2T,
            ProtectionEvent.LATCH_OFF,
            ProtectionEvent.THERMAL_SHUTDOWN,
            ProtectionEvent.OPEN_LOAD_DIAG,
            ProtectionEvent.OVER_VOLTAGE,
        ):
            assert f"{event.value}_count" in out.columns

    def test_nominal_zero_protection_rate(self):
        df = _generate_telemetry()
        out = FeatureEngine().compute(df)
        assert out["protection_event_rate"].max() < 1e-9


class TestVoltageFeatures:
    """Rolling voltage stats when voltage_v is present."""

    def test_voltage_columns_present(self):
        df = _generate_telemetry()
        assert "voltage_v" in df.columns, "Generator must produce voltage_v"
        out = FeatureEngine().compute(df)
        assert "rolling_min_voltage" in out.columns
        assert "rolling_max_voltage" in out.columns
        assert "rolling_voltage_drop" in out.columns


class TestFeatureConfig:
    """FeatureConfig.resolve correctly computes window parameters."""

    def test_resolve_auto_from_duration(self):
        fc = FeatureConfig(window_duration_s=5.0, min_duration_s=1.0)
        w, mp = fc.resolve(0.1)  # 100 ms interval
        assert w == 50  # 5.0 / 0.1
        assert mp == 10  # 1.0 / 0.1

    def test_resolve_override(self):
        fc = FeatureConfig(window_size=20, min_periods=5)
        w, mp = fc.resolve(0.1)
        assert w == 20
        assert mp == 5

    def test_output_row_count_matches_input(self):
        df = _generate_telemetry()
        out = FeatureEngine().compute(df)
        assert len(out) == len(df)
