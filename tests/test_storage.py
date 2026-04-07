"""Tests for efuse_datagen.storage.writer – StorageWriter."""

import json
from pathlib import Path

import pandas as pd
import pytest

from efuse_datagen.config.models import StorageConfig
from efuse_datagen.schemas.telemetry import ChannelMeta, PowerClass
from efuse_datagen.storage.writer import StorageWriter


@pytest.fixture()
def tmp_storage(tmp_path: Path):
    """Return a StorageWriter pointed at a temp directory."""
    def _make(fmt: str = "parquet", disk_min_free_mb: int = 0) -> StorageWriter:
        cfg = StorageConfig(output_dir=str(tmp_path), format=fmt)
        return StorageWriter(config=cfg, disk_min_free_mb=disk_min_free_mb)
    return _make


@pytest.fixture()
def sample_df() -> pd.DataFrame:
    return pd.DataFrame({
        "channel_id": ["ch_01"] * 5,
        "timestamp": pd.date_range("2025-01-01", periods=5, freq="100ms"),
        "current_a": [1.0, 2.0, 3.0, 4.0, 5.0],
        "voltage_v": [13.5] * 5,
    })


class TestParquetRoundTrip:
    def test_write_and_read(self, tmp_storage, sample_df):
        sw = tmp_storage("parquet")
        p = sw.write_telemetry(sample_df)
        assert p is not None and p.exists()
        df_back = pd.read_parquet(p)
        assert len(df_back) == len(sample_df)
        assert list(df_back.columns) == list(sample_df.columns)

    def test_features_write(self, tmp_storage, sample_df):
        sw = tmp_storage("parquet")
        p = sw.write_features(sample_df, name="feat_out")
        assert p is not None
        assert "feat_out.parquet" in p.name


class TestCsvRoundTrip:
    def test_write_and_read(self, tmp_storage, sample_df):
        sw = tmp_storage("csv")
        p = sw.write_telemetry(sample_df)
        assert p is not None and p.suffix == ".csv"
        df_back = pd.read_csv(p)
        assert len(df_back) == len(sample_df)


class TestJsonRoundTrip:
    def test_write_and_read(self, tmp_storage, sample_df):
        sw = tmp_storage("json")
        p = sw.write_telemetry(sample_df)
        assert p is not None and p.suffix == ".json"
        df_back = pd.read_json(p, orient="records")
        assert len(df_back) == len(sample_df)


class TestListColumnSerialization:
    def test_list_columns_serialised_as_json_strings(self, tmp_storage):
        df = pd.DataFrame({
            "id": [1, 2],
            "tags": [["a", "b"], ["c"]],
        })
        sw = tmp_storage("csv")
        p = sw.write_labels(df)
        df_back = pd.read_csv(p)
        # List columns should be stored as JSON strings
        assert df_back["tags"].iloc[0] == '["a", "b"]'


class TestChannelManifest:
    def test_manifest_written(self, tmp_storage):
        ch = ChannelMeta(
            channel_id="ch_01",
            load_name="test",
            nominal_current_a=5.0,
            power_class=PowerClass.IGNITION,
        )
        sw = tmp_storage("parquet")
        p = sw.write_channel_manifest([ch])
        assert p is not None and p.exists()
        df = pd.read_parquet(p)
        assert "channel_id" in df.columns
        assert df["channel_id"].iloc[0] == "ch_01"

    def test_empty_channels_returns_none(self, tmp_storage):
        sw = tmp_storage("parquet")
        assert sw.write_channel_manifest([]) is None


class TestAlerts:
    def test_write_alerts(self, tmp_storage):
        sw = tmp_storage("parquet")
        alerts = [{"level": "warning", "msg": "overtemp"}]
        p = sw.write_alerts(alerts)
        assert p is not None and p.exists()
        with open(p) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["level"] == "warning"

    def test_alerts_append(self, tmp_storage):
        sw = tmp_storage("parquet")
        sw.write_alerts([{"a": 1}])
        sw.write_alerts([{"b": 2}])
        p = sw._out / "alerts.json"
        with open(p) as f:
            data = json.load(f)
        assert len(data) == 2


class TestDiskSpace:
    def test_check_disk_space_passes_default(self, tmp_storage):
        sw = tmp_storage("parquet", disk_min_free_mb=0)
        assert sw.check_disk_space() is True

    def test_check_disk_space_fails_huge_threshold(self, tmp_storage):
        sw = tmp_storage("parquet", disk_min_free_mb=999_999_999)
        assert sw.check_disk_space() is False

    def test_write_skipped_when_low_disk(self, tmp_storage, sample_df):
        sw = tmp_storage("parquet", disk_min_free_mb=999_999_999)
        p = sw.write_telemetry(sample_df)
        assert p is None


class TestDriveCycleWrite:
    def test_write_drive_cycles_empty(self, tmp_storage):
        sw = tmp_storage("parquet")
        assert sw.write_drive_cycles([]) is None
