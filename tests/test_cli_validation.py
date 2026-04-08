"""Tests for CLI input validation — format, range checks, mode-mismatch warnings."""

import pytest
from typer.testing import CliRunner

from efuse_datagen.cli import app

runner = CliRunner()


class TestFormatValidation:
    def test_invalid_format_rejected(self):
        result = runner.invoke(app, ["--config", "quick_demo", "--format", "xml"])
        assert result.exit_code != 0
        assert "Invalid format" in result.output

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
        assert "--duration must be > 0" in result.output

    def test_zero_duration_rejected(self):
        result = runner.invoke(app, ["--config", "quick_demo", "--duration", "0"])
        assert result.exit_code != 0
        assert "--duration must be > 0" in result.output

    def test_negative_seed_rejected(self):
        result = runner.invoke(app, ["--config", "quick_demo", "--seed", "-1"])
        assert result.exit_code != 0
        assert "--seed must be >= 0" in result.output

    def test_zero_vehicles_rejected(self):
        result = runner.invoke(app, ["--config", "fleet", "--vehicles", "0"])
        assert result.exit_code != 0
        assert "--vehicles must be >= 1" in result.output

    def test_zero_days_rejected(self):
        result = runner.invoke(app, ["--config", "fleet", "--days", "0"])
        assert result.exit_code != 0
        assert "--days must be >= 1" in result.output

    def test_zero_workers_rejected(self):
        result = runner.invoke(app, ["--config", "fleet", "--workers", "0"])
        assert result.exit_code != 0
        assert "--workers must be >= 1" in result.output


class TestModeMismatchWarnings:
    def test_fleet_flags_warn_in_single_mode(self):
        result = runner.invoke(app, ["--config", "quick_demo", "--vehicles", "5"])
        # Should run but emit a warning
        assert "--vehicles ignored in single-vehicle mode" in result.output

    def test_duration_flag_warns_in_fleet_mode(self):
        result = runner.invoke(app, ["--config", "fleet", "--duration", "60", "--vehicles", "1", "--days", "1"])
        assert "--duration is ignored in fleet mode" in result.output
