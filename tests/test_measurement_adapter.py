"""Tests for MeasurementAdapter helpers, DataSource, and save_as_run."""

from pathlib import Path

import pandas as pd
import pytest

from efuse_datagen.ingestion.measurement_adapter import (
    DataSource,
    MeasurementAdapter,
    save_as_run,
)


# ── MeasurementAdapter load / helpers ─────────────────────────────────────


@pytest.fixture
def sample_csv(tmp_path):
    """Create a minimal CSV file for adapter tests."""
    p = tmp_path / "test.csv"
    df = pd.DataFrame({
        "time_s": [0.0, 0.1, 0.2, 0.3, 0.4],
        "I": [1.0, 2.0, 3.0, 4.0, 5.0],
        "U": [13.5, 13.4, 13.3, 13.2, 13.1],
        "T": [25.0, 26.0, 27.0, 28.0, 29.0],
    })
    df.to_csv(p, index=False)
    return p


@pytest.fixture
def adapter():
    return MeasurementAdapter(
        column_map={"I": "current_a", "U": "voltage_v", "T": "temperature_c"},
        time_column="time_s",
        time_origin="2026-01-01",
        default_channel_id="ch_test",
    )


def test_load_csv(adapter, sample_csv):
    """Load a CSV file and verify schema conformance."""
    df = adapter.load(sample_csv)
    assert "timestamp" in df.columns
    assert "channel_id" in df.columns
    assert "current_a" in df.columns
    assert "voltage_v" in df.columns
    assert "temperature_c" in df.columns
    assert len(df) == 5
    assert (df["channel_id"] == "ch_test").all()


def test_load_csv_with_channel_override(adapter, sample_csv):
    """channel_id override takes precedence."""
    df = adapter.load(sample_csv, channel_id="override_ch")
    assert (df["channel_id"] == "override_ch").all()


def test_load_parquet(adapter, tmp_path):
    """Load a Parquet file."""
    p = tmp_path / "test.parquet"
    df = pd.DataFrame({
        "time_s": [0.0, 0.1, 0.2],
        "I": [1.0, 2.0, 3.0],
        "U": [13.5, 13.4, 13.3],
        "T": [25.0, 26.0, 27.0],
    })
    df.to_parquet(p, index=False)
    result = adapter.load(p)
    assert len(result) == 3


def test_load_unsupported_format(adapter, tmp_path):
    """Unsupported file extension raises ValueError."""
    p = tmp_path / "data.xyz"
    p.write_text("dummy")
    with pytest.raises(ValueError, match="Unsupported file format"):
        adapter.load(p)


def test_load_with_resample(tmp_path):
    """Resampling reduces data to the target interval."""
    p = tmp_path / "data.csv"
    # 10 samples at 100ms intervals → 1 second total
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=10, freq="100ms"),
        "current_a": range(10),
        "voltage_v": [13.0] * 10,
        "temperature_c": [25.0] * 10,
    })
    df.to_csv(p, index=False)
    adapter = MeasurementAdapter(resample_ms=500.0, default_channel_id="ch_r")
    result = adapter.load(p)
    assert len(result) < 10


def test_load_multi_channel(adapter, tmp_path):
    """load_multi_channel concatenates correctly."""
    for name in ("a.csv", "b.csv"):
        df = pd.DataFrame({
            "time_s": [0.0, 0.1],
            "I": [1.0, 2.0],
            "U": [13.5, 13.4],
            "T": [25.0, 26.0],
        })
        df.to_csv(tmp_path / name, index=False)

    pairs = [(tmp_path / "a.csv", "ch_a"), (tmp_path / "b.csv", "ch_b")]
    result = adapter.load_multi_channel(pairs)
    assert set(result["channel_id"].unique()) == {"ch_a", "ch_b"}


def test_load_directory(adapter, tmp_path):
    """load_directory globs and concatenates."""
    for name in ("ch_001.csv", "ch_002.csv"):
        df = pd.DataFrame({
            "time_s": [0.0, 0.1],
            "I": [1.0, 2.0],
            "U": [13.5, 13.4],
            "T": [25.0, 26.0],
        })
        df.to_csv(tmp_path / name, index=False)

    result = adapter.load_directory(tmp_path, glob_pattern="*.csv")
    assert "ch_001" in result["channel_id"].values
    assert "ch_002" in result["channel_id"].values


def test_load_directory_no_match(adapter, tmp_path):
    """load_directory with no matches raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        adapter.load_directory(tmp_path, glob_pattern="*.xyz")


def test_fill_defaults(adapter, sample_csv):
    """Optional columns get default values."""
    df = adapter.load(sample_csv)
    assert "state_on_off" in df.columns
    assert "trip_flag" in df.columns
    assert "protection_event" in df.columns


def test_validate_drops_nan(tmp_path):
    """Rows with NaN current/voltage are dropped."""
    p = tmp_path / "nan.csv"
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=3, freq="100ms"),
        "current_a": [1.0, float("nan"), 3.0],
        "voltage_v": [13.0, 13.0, float("nan")],
        "temperature_c": [25.0, 25.0, 25.0],
    })
    df.to_csv(p, index=False)
    adapter = MeasurementAdapter(default_channel_id="ch_nan")
    result = adapter.load(p)
    assert len(result) == 1  # only the first row survives


# ── DataSource ────────────────────────────────────────────────────────────


def test_datasource_detect_marker(tmp_path):
    """DataSource.detect reads data_source.txt marker."""
    (tmp_path / "data_source.txt").write_text("bench")
    assert DataSource.detect(tmp_path) == "bench"


def test_datasource_detect_synthetic(tmp_path):
    """DataSource.detect recognises synthetic runs via config.yaml."""
    import yaml

    cfg = {"scenario_id": "test", "channels": []}
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg))
    assert DataSource.detect(tmp_path) == "synthetic"


def test_datasource_detect_bench_fallback(tmp_path):
    """DataSource.detect falls back to 'bench'."""
    assert DataSource.detect(tmp_path) == "bench"


def test_datasource_detect_mapping_yaml(tmp_path):
    """DataSource.detect recognises bench via mapping.yaml."""
    (tmp_path / "mapping.yaml").write_text("col: val")
    assert DataSource.detect(tmp_path) == "bench"


# ── save_as_run ───────────────────────────────────────────────────────────


def test_save_as_run_basic(tmp_path):
    """save_as_run writes the expected directory structure."""
    tel = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=5, freq="100ms"),
        "channel_id": ["ch_001"] * 5,
        "current_a": [1.0] * 5,
        "voltage_v": [13.5] * 5,
        "temperature_c": [25.0] * 5,
        "state_on_off": [True] * 5,
        "trip_flag": [False] * 5,
        "overload_flag": [False] * 5,
        "protection_event": ["none"] * 5,
        "reset_counter": [0] * 5,
        "pwm_duty_pct": [100.0] * 5,
        "device_status": ["ok"] * 5,
    })
    out = tmp_path / "run1"
    result = save_as_run(tel, out, data_source="bench", metadata={"note": "test"})
    assert result == out
    assert (out / "telemetry.parquet").exists()
    assert (out / "features.parquet").exists()
    assert (out / "labels.parquet").exists()
    assert (out / "data_source.txt").read_text() == "bench"
    assert (out / "metadata.json").exists()


def test_save_as_run_with_labels(tmp_path):
    """save_as_run with labels writes labels.parquet."""
    tel = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=3, freq="100ms"),
        "channel_id": ["ch_001"] * 3,
        "current_a": [1.0] * 3,
        "voltage_v": [13.5] * 3,
        "temperature_c": [25.0] * 3,
        "state_on_off": [True] * 3,
        "trip_flag": [False] * 3,
        "overload_flag": [False] * 3,
        "protection_event": ["none"] * 3,
        "reset_counter": [0] * 3,
        "pwm_duty_pct": [100.0] * 3,
        "device_status": ["ok"] * 3,
    })
    labels = pd.DataFrame({
        "timestamp": [pd.Timestamp("2026-01-01")],
        "channel_id": ["ch_001"],
        "fault_type": ["overcurrent"],
        "severity": ["high"],
        "description": ["test"],
    })
    out = tmp_path / "run2"
    save_as_run(tel, out, labels_df=labels)
    lbl = pd.read_parquet(out / "labels.parquet")
    assert len(lbl) == 1
