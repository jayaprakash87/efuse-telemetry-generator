"""Tests for cross-field validation in config and schema models."""

import pytest
from pydantic import ValidationError

from efuse_datagen.config.models import (
    DriveCycleConfig,
    FeatureConfig,
    FleetConfig,
    GeneratorConfig,
    SimulationConfig,
    StorageConfig,
    VehicleArchetypeConfig,
)
from efuse_datagen.schemas.telemetry import ChannelMeta


# ---------------------------------------------------------------------------
# ChannelMeta: nominal_current_a < max_current_a
# ---------------------------------------------------------------------------


class TestChannelMetaValidation:
    def test_nominal_below_max_ok(self):
        ch = ChannelMeta(channel_id="ch_01", nominal_current_a=5.0, max_current_a=20.0)
        assert ch.nominal_current_a < ch.max_current_a

    def test_nominal_equals_max_rejected(self):
        with pytest.raises(ValidationError, match="nominal_current_a.*must be <.*max_current_a"):
            ChannelMeta(channel_id="ch_01", nominal_current_a=20.0, max_current_a=20.0)

    def test_nominal_exceeds_max_rejected(self):
        with pytest.raises(ValidationError, match="nominal_current_a.*must be <.*max_current_a"):
            ChannelMeta(channel_id="ch_01", nominal_current_a=25.0, max_current_a=20.0)


# ---------------------------------------------------------------------------
# DriveCycleConfig: min_trip_minutes < max_trip_minutes
# ---------------------------------------------------------------------------


class TestDriveCycleValidation:
    def test_min_below_max_ok(self):
        dc = DriveCycleConfig(min_trip_minutes=5.0, max_trip_minutes=240.0)
        assert dc.min_trip_minutes < dc.max_trip_minutes

    def test_min_equals_max_rejected(self):
        with pytest.raises(ValidationError, match="min_trip_minutes.*must be <.*max_trip_minutes"):
            DriveCycleConfig(min_trip_minutes=60.0, max_trip_minutes=60.0)

    def test_min_exceeds_max_rejected(self):
        with pytest.raises(ValidationError, match="min_trip_minutes.*must be <.*max_trip_minutes"):
            DriveCycleConfig(min_trip_minutes=300.0, max_trip_minutes=60.0)


# ---------------------------------------------------------------------------
# VehicleArchetypeConfig: age_months_min <= age_months_max
# ---------------------------------------------------------------------------


class TestVehicleArchetypeValidation:
    def test_age_min_below_max_ok(self):
        va = VehicleArchetypeConfig(id="test", age_months_min=0, age_months_max=24)
        assert va.age_months_min <= va.age_months_max

    def test_age_equal_ok(self):
        va = VehicleArchetypeConfig(id="test", age_months_min=12, age_months_max=12)
        assert va.age_months_min == va.age_months_max

    def test_age_min_exceeds_max_rejected(self):
        with pytest.raises(ValidationError, match="age_months_min.*must be <=.*age_months_max"):
            VehicleArchetypeConfig(id="test", age_months_min=36, age_months_max=12)


# ---------------------------------------------------------------------------
# FleetConfig: start_date validation, region cross-ref, fault_rate_overrides
# ---------------------------------------------------------------------------


class TestFleetConfigValidation:
    def test_valid_start_date_ok(self):
        fc = FleetConfig(start_date="2026-01-01")
        assert fc.start_date == "2026-01-01"

    def test_invalid_start_date_rejected(self):
        with pytest.raises(ValidationError, match="not valid ISO-8601"):
            FleetConfig(start_date="01-01-2026")

    def test_nonsense_date_rejected(self):
        with pytest.raises(ValidationError, match="not valid ISO-8601"):
            FleetConfig(start_date="not-a-date")

    def test_archetype_unknown_region_rejected(self):
        with pytest.raises(ValidationError, match="references region.*not defined"):
            FleetConfig(
                archetypes=[VehicleArchetypeConfig(id="bad", region="tropical")],
                regions={},
            )

    def test_archetype_valid_region_ok(self):
        from efuse_datagen.config.models import RegionalWeatherConfig

        fc = FleetConfig(
            archetypes=[VehicleArchetypeConfig(id="ok", region="test_region")],
            regions={"test_region": RegionalWeatherConfig()},
        )
        assert len(fc.archetypes) == 1

    def test_archetype_invalid_fault_rate_override_rejected(self):
        with pytest.raises(ValidationError, match="unknown fault_rate_overrides"):
            FleetConfig(
                archetypes=[
                    VehicleArchetypeConfig(
                        id="bad",
                        region="temperate",
                        fault_rate_overrides={"nonexistent_fault": 0.5},
                    )
                ],
            )

    def test_archetype_valid_fault_rate_override_ok(self):
        fc = FleetConfig(
            archetypes=[
                VehicleArchetypeConfig(
                    id="ok",
                    region="temperate",
                    fault_rate_overrides={"cold_crank": 1.5},
                )
            ],
        )
        assert fc.archetypes[0].fault_rate_overrides["cold_crank"] == 1.5


# ---------------------------------------------------------------------------
# FeatureConfig: window/period bounds
# ---------------------------------------------------------------------------


class TestFeatureConfigValidation:
    def test_defaults_ok(self):
        fc = FeatureConfig()
        assert fc.window_duration_s > 0

    def test_negative_window_size_rejected(self):
        with pytest.raises(ValidationError, match="window_size must be >= 0"):
            FeatureConfig(window_size=-1)

    def test_negative_min_periods_rejected(self):
        with pytest.raises(ValidationError, match="min_periods must be >= 0"):
            FeatureConfig(min_periods=-1)


# ---------------------------------------------------------------------------
# Extra-field rejection (extra: "forbid")
# ---------------------------------------------------------------------------


class TestExtraFieldRejection:
    def test_generator_config_rejects_extra_keys(self):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            GeneratorConfig.model_validate({"simulation": {}, "bogus_key": 42})

    def test_simulation_config_rejects_extra_keys(self):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            SimulationConfig(scenario_id="test", typo_field="oops")

    def test_storage_config_rejects_extra_keys(self):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            StorageConfig(output_dir="output", fomat="csv")

    def test_valid_generator_config_accepted(self):
        cfg = GeneratorConfig.model_validate({
            "simulation": {"scenario_id": "test"},
            "features": {},
            "storage": {},
        })
        assert cfg.simulation.scenario_id == "test"
