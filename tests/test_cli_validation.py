"""Tests for CLI input validation — format, range checks, mode-mismatch warnings."""

import re
from unittest.mock import patch

from typer.testing import CliRunner

from efuse_datagen.cli import app

runner = CliRunner()


def _plain(text: str) -> str:
    """Strip ANSI escape codes so assertions aren't broken by Rich formatting."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestFormatValidation:
    def test_invalid_format_rejected(self):
        result = runner.invoke(app, ["--config", "quick_demo", "--format", "xml"])
        assert result.exit_code != 0
        assert "Invalid format" in _plain(result.output)

    def test_parquet_accepted(self):
        result = runner.invoke(app, ["--config", "quick_demo", "--format", "parquet"])
        assert result.exit_code == 0

    def test_csv_accepted(self):
        result = runner.invoke(app, ["--config", "quick_demo", "--format", "csv"])
        assert result.exit_code == 0


class TestNumericRangeValidation:
    def test_negative_duration_rejected(self):
        result = runner.invoke(app, ["--config", "quick_demo", "--duration", "-5"])
        assert result.exit_code != 0
        assert "--duration must be > 0" in _plain(result.output)

    def test_zero_duration_rejected(self):
        result = runner.invoke(app, ["--config", "quick_demo", "--duration", "0"])
        assert result.exit_code != 0
        assert "--duration must be > 0" in _plain(result.output)

    def test_negative_seed_rejected(self):
        result = runner.invoke(app, ["--config", "quick_demo", "--seed", "-1"])
        assert result.exit_code != 0
        assert "--seed must be >= 0" in _plain(result.output)

    def test_zero_vehicles_rejected(self):
        result = runner.invoke(app, ["--config", "fleet", "--vehicles", "0"])
        assert result.exit_code != 0
        assert "--vehicles must be >= 1" in _plain(result.output)

    def test_zero_days_rejected(self):
        result = runner.invoke(app, ["--config", "fleet", "--days", "0"])
        assert result.exit_code != 0
        assert "--days must be >= 1" in _plain(result.output)

    def test_zero_workers_rejected(self):
        result = runner.invoke(app, ["--config", "fleet", "--workers", "0"])
        assert result.exit_code != 0
        assert "--workers must be >= 1" in _plain(result.output)


class TestModeMismatchWarnings:
    def test_fleet_flags_warn_in_single_mode(self):
        result = runner.invoke(app, ["--config", "quick_demo", "--vehicles", "5"])
        # Should run but emit a warning
        assert "--vehicles ignored in single-vehicle mode" in _plain(result.output)

    def test_duration_flag_warns_in_fleet_mode(self):
        with patch("efuse_datagen.cli._run_fleet"):
            result = runner.invoke(app, ["--config", "fleet", "--duration", "60", "--vehicles", "1", "--days", "1"])
        assert "--duration is ignored in fleet mode" in _plain(result.output)


class TestConfigResolution:
    def test_list_configs(self):
        result = runner.invoke(app, ["--list-configs"])
        assert result.exit_code == 0
        assert "quick_demo" in _plain(result.output)

    def test_unknown_config_rejected(self):
        result = runner.invoke(app, ["--config", "nonexistent_config_xyz"])
        assert result.exit_code != 0
        assert "not found" in _plain(result.output).lower()

    def test_quick_demo_runs(self):
        """Smoke test: quick_demo should complete end-to-end."""
        result = runner.invoke(app, ["--config", "quick_demo", "--format", "parquet"])
        assert result.exit_code == 0
        assert "Done" in _plain(result.output)

    def test_seed_override(self):
        result = runner.invoke(app, ["--config", "quick_demo", "--seed", "123"])
        assert result.exit_code == 0
        assert "Seed" in _plain(result.output)
        assert "123" in _plain(result.output)

    def test_duration_override(self):
        result = runner.invoke(app, ["--config", "quick_demo", "--duration", "5"])
        assert result.exit_code == 0
        assert "Done" in _plain(result.output)

    def test_json_format(self):
        result = runner.invoke(app, ["--config", "quick_demo", "--format", "json"])
        assert result.exit_code == 0
        assert "Done" in _plain(result.output)

    def test_csv_format(self):
        result = runner.invoke(app, ["--config", "quick_demo", "--format", "csv"])
        assert result.exit_code == 0
        assert "Done" in _plain(result.output)


class TestIngestCLI:
    def test_ingest_missing_source(self):
        from efuse_datagen.cli import ingest_app

        result = runner.invoke(ingest_app, ["/tmp/nonexistent_file_xyz.csv"])
        assert result.exit_code != 0

    def test_ingest_csv(self, tmp_path):
        """Smoke test: ingest a minimal CSV file into run format."""
        import pandas as pd

        from efuse_datagen.cli import ingest_app

        csv_path = tmp_path / "test_input.csv"
        df = pd.DataFrame({
            "timestamp": pd.date_range("2026-01-01", periods=10, freq="100ms"),
            "current_a": [1.0] * 10,
            "voltage_v": [12.0] * 10,
            "temperature_c": [25.0] * 10,
        })
        df.to_csv(csv_path, index=False)

        result = runner.invoke(ingest_app, [
            str(csv_path),
            "--output", str(tmp_path / "output"),
            "--time-col", "timestamp",
        ])
        assert result.exit_code == 0
        assert "Ingestion complete" in _plain(result.output)
