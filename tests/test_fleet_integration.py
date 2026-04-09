"""Integration tests for fleet-scale generation."""

from __future__ import annotations

import pandas as pd
import pytest

from efuse_datagen.config.builtin import load_bundled_config
from efuse_datagen.simulation.fleet import (
    FleetRunner,
    build_regional_weather,
    sample_population,
)


@pytest.fixture()
def fleet_cfg():
    """Load the bundled fleet config with small overrides for fast tests."""
    cfg = load_bundled_config("fleet")
    assert cfg.fleet is not None
    # Shrink to 2 vehicles, 1 day, 1 worker; coarsen interval to 10 s for speed
    cfg = cfg.model_copy(
        update={
            "fleet": cfg.fleet.model_copy(
                update={
                    "n_vehicles": 2,
                    "duration_days": 1,
                    "max_workers": 1,
                    "write_combined": True,
                }
            ),
            "simulation": cfg.simulation.model_copy(
                update={"sample_interval_ms": 10000.0}
            ),
        }
    )
    return cfg


class TestSamplePopulation:
    def test_correct_count(self, fleet_cfg):
        specs = sample_population(fleet_cfg.fleet)
        assert len(specs) == 2

    def test_unique_seeds(self):
        """With enough vehicles, seeds should be unique (entropy mod 2^31 may collide for tiny N)."""
        cfg = load_bundled_config("fleet")
        cfg = cfg.model_copy(
            update={"fleet": cfg.fleet.model_copy(update={"n_vehicles": 20})}
        )
        specs = sample_population(cfg.fleet)
        seeds = [s.seed for s in specs]
        assert len(set(seeds)) == len(seeds), "Vehicle seeds must be unique"

    def test_unique_vehicle_ids(self, fleet_cfg):
        specs = sample_population(fleet_cfg.fleet)
        ids = [s.vehicle_id for s in specs]
        assert len(set(ids)) == len(ids)


class TestRegionalWeather:
    def test_weather_shape(self, fleet_cfg):
        region_name = list(fleet_cfg.fleet.regions.keys())[0]
        region_cfg = fleet_cfg.fleet.regions[region_name]
        df = build_regional_weather(region_cfg, n_days=5, seed=42)
        assert len(df) == 5
        assert "ambient_temp_c" in df.columns
        assert "supply_voltage_v" in df.columns

    def test_supply_voltage_bounds(self, fleet_cfg):
        region_name = list(fleet_cfg.fleet.regions.keys())[0]
        region_cfg = fleet_cfg.fleet.regions[region_name]
        df = build_regional_weather(region_cfg, n_days=30, seed=99)
        assert df["supply_voltage_v"].min() >= 10.5
        assert df["supply_voltage_v"].max() <= 15.0


class TestFleetRunner:
    def test_end_to_end(self, fleet_cfg, tmp_path):
        """Full fleet run: 2 vehicles × 2 days, verify manifests and outputs."""
        runner = FleetRunner(fleet_cfg, output_dir=tmp_path)
        manifest_df = runner.run(run_id="test_fleet")

        assert isinstance(manifest_df, pd.DataFrame)
        assert len(manifest_df) == 2

        # At least one vehicle should succeed
        ok_mask = manifest_df["status"] == "ok"
        assert ok_mask.sum() >= 1, f"No vehicles succeeded: {manifest_df['status'].tolist()}"

        # Check output structure
        run_dir = tmp_path / "test_fleet"
        assert (run_dir / "fleet_manifest.parquet").exists()
        assert (run_dir / "fleet_config.yaml").exists()
        assert (run_dir / "regions").is_dir()

        # Per-vehicle outputs
        for _, row in manifest_df[ok_mask].iterrows():
            v_dir = run_dir / "vehicles" / row["vehicle_id"]
            assert (v_dir / "telemetry.parquet").exists()
            assert (v_dir / "features.parquet").exists()
            assert (v_dir / "drive_cycles.parquet").exists()

    def test_combined_output(self, fleet_cfg, tmp_path):
        """Combined fleet output files should exist when write_combined=True."""
        runner = FleetRunner(fleet_cfg, output_dir=tmp_path)
        manifest_df = runner.run(run_id="test_combined")

        run_dir = tmp_path / "test_combined"
        ok_count = (manifest_df["status"] == "ok").sum()
        if ok_count > 0:
            assert (run_dir / "fleet_telemetry.parquet").exists()

    def test_progress_callback(self, fleet_cfg, tmp_path):
        """Progress callback should be invoked for each vehicle."""
        calls = []

        def cb(done: int, total: int) -> None:
            calls.append((done, total))

        runner = FleetRunner(fleet_cfg, output_dir=tmp_path, progress_callback=cb)
        runner.run(run_id="test_progress")

        assert len(calls) == 2
        assert calls[-1] == (2, 2)

    def test_manifest_columns(self, fleet_cfg, tmp_path):
        runner = FleetRunner(fleet_cfg, output_dir=tmp_path)
        manifest_df = runner.run(run_id="test_cols")

        expected_cols = {
            "vehicle_id", "archetype_id", "region", "profile", "age_months",
            "seed", "status", "n_telemetry_rows", "n_fault_labels",
            "n_drive_cycles", "driving_hours",
        }
        assert expected_cols.issubset(set(manifest_df.columns))
