"""Configuration models and YAML/JSON loading.

All runtime behavior is driven by config objects so scenarios are
reproducible and parameters are never buried in code.
"""

from __future__ import annotations

from pathlib import Path

from typing import Optional

import yaml
from pydantic import BaseModel, Field

from efuse_datagen.schemas.telemetry import ChannelMeta, FaultInjection, PowerState, ZoneController


# ---------------------------------------------------------------------------
# Power state timeline
# ---------------------------------------------------------------------------


class PowerStateEvent(BaseModel):
    """A power-state transition at a given time offset in the scenario.

    Example timeline — ignition cycle with cold crank:
      t=0s  SLEEP   (vehicle parked)
      t=5s  CRANK   (starter engaged)
      t=8s  ACTIVE  (engine running, KL15 on)
      t=55s SLEEP   (ignition off)
    """

    time_s: float = Field(ge=0.0, description="Seconds from scenario start for this transition")
    state: PowerState = Field(description="Target power state at this time")


# ---------------------------------------------------------------------------
# Simulation config
# ---------------------------------------------------------------------------


class FaultRateConfig(BaseModel):
    """Fault occurrence rates — probability per vehicle-hour of driving.

    When a Poisson draw fires, one random eligible channel is picked.
    """

    overload_spike: float = Field(default=0.05, ge=0)
    intermittent_overload: float = Field(default=0.03, ge=0)
    voltage_sag: float = Field(default=0.04, ge=0)
    thermal_drift: float = Field(default=0.02, ge=0)
    noisy_sensor: float = Field(default=0.03, ge=0)
    connector_aging: float = Field(default=0.01, ge=0)
    open_load: float = Field(default=0.005, ge=0)
    gradual_degradation: float = Field(default=0.01, ge=0)
    cold_crank: float = Field(default=0.5, ge=0)  # conditional on ambient < 5 °C
    jump_start: float = Field(default=0.002, ge=0)
    load_dump: float = Field(default=0.02, ge=0)
    thermal_coupling: float = Field(default=0.03, ge=0)
    wake_transient: float = Field(default=0.15, ge=0)
    ground_offset: float = Field(default=0.02, ge=0)
    short_to_ground: float = Field(default=0.01, ge=0)
    dropped_packet: float = Field(default=0.03, ge=0)


class DriveCycleConfig(BaseModel):
    """Multi-day drive cycle schedule configuration.

    When ``enabled=True`` the planner auto-generates a realistic calendar of
    ignition cycles.  The top-level ``SimulationConfig.duration_s`` is ignored —
    each cycle's duration is computed by the planner.  ``fault_injections`` and
    ``power_state_events`` are also generated per-cycle.
    """

    enabled: bool = Field(default=False, description="Enable multi-cycle mode")
    total_days: int = Field(default=30, ge=1, description="Simulation span in calendar days")
    profile: str = Field(
        default="mixed",
        description="Driving profile: commuter | mixed | heavy",
    )
    mean_trips_per_day: float = Field(default=2.5, ge=0)
    max_trips_per_day: int = Field(default=6, ge=1)
    no_drive_day_probability: float = Field(default=0.10, ge=0, le=1)
    min_trip_minutes: float = Field(default=5.0, ge=1)
    max_trip_minutes: float = Field(default=240.0, ge=1)
    median_trip_minutes: float = Field(default=30.0, ge=1)
    ambient_temp_mean_c: float = Field(default=22.0, description="Seasonal mean ambient °C")
    ambient_temp_std_c: float = Field(default=8.0, ge=0, description="Day-to-day σ °C")
    fault_rates: FaultRateConfig = Field(default_factory=FaultRateConfig)


class SimulationConfig(BaseModel):
    """Core scenario definition: channels, faults, power states, and drive cycle settings."""
    scenario_id: str = "quick_demo"
    name: str = "Quick Demo"
    description: str = ""
    duration_s: float = Field(
        default=60.0,
        description="Scenario duration in seconds (single-cycle mode). Ignored when drive_cycle.enabled is true.",
    )
    sample_interval_ms: float = 100.0
    seed: int = 42
    bus_voltage_nominal: float = Field(
        default=13.5,
        gt=0.0,
        description="Nominal bus voltage in V. 13.5 V typical; set to 9 or 12 for supply-corner sweeps.",
    )
    zones: list[ZoneController] = Field(
        default_factory=list, description="Zone Controllers in the vehicle"
    )
    channels: list[ChannelMeta] = Field(
        default_factory=lambda: [
            ChannelMeta(channel_id="ch_01", load_name="headlamp_left", nominal_current_a=6.0),
            ChannelMeta(channel_id="ch_02", load_name="rear_defroster", nominal_current_a=12.0),
            ChannelMeta(channel_id="ch_03", load_name="seat_heater", nominal_current_a=8.0),
        ]
    )
    # Compact channel definitions — expanded via catalog if present
    channel_specs: list[dict] = Field(
        default_factory=list,
        description="Compact channel specs referencing eFuse catalog. Expanded to channels by build_channels().",
    )
    fault_injections: list[FaultInjection] = Field(default_factory=list)
    power_state_events: list["PowerStateEvent"] = Field(
        default_factory=list,
        description=(
            "Ordered list of power-state transitions. Empty = always ACTIVE. "
            "First entry need not start at t=0 — state before first event is ACTIVE."
        ),
    )
    use_example_topology: bool = Field(
        default=False,
        description="When True, populate channels from the built-in 65-channel example topology.",
    )
    drive_cycle: DriveCycleConfig = Field(
        default_factory=DriveCycleConfig,
        description="Multi-day drive cycle schedule. Overrides duration/faults/power_state when enabled.",
    )


# ---------------------------------------------------------------------------
# Feature config — time-based (auto-computes sample counts from interval)
# ---------------------------------------------------------------------------


class FeatureConfig(BaseModel):
    """Rolling-window parameters for the feature extraction engine."""
    window_duration_s: float = Field(default=5.0, description="Rolling window duration in seconds")
    min_duration_s: float = Field(
        default=1.0, description="Minimum data duration before features are valid"
    )
    # Sample-count overrides — if > 0, used instead of auto-computed values
    window_size: int = Field(
        default=0, description="Override: fixed window in samples (0=auto from duration)"
    )
    min_periods: int = Field(
        default=0, description="Override: fixed min_periods (0=auto from duration)"
    )

    def resolve(self, sample_interval_s: float) -> tuple[int, int]:
        """Return (window_size, min_periods) for a given sample interval."""
        if self.window_size > 0:
            w = self.window_size
        else:
            w = max(int(self.window_duration_s / sample_interval_s), 2)
        if self.min_periods > 0:
            mp = self.min_periods
        else:
            mp = max(int(self.min_duration_s / sample_interval_s), 1)
        return w, min(mp, w)


# ---------------------------------------------------------------------------
# Storage config
# ---------------------------------------------------------------------------


class StorageConfig(BaseModel):
    """Output persistence settings: directory and file format."""
    output_dir: str = "output"
    format: str = "parquet"  # "parquet" | "csv" | "json"


# ---------------------------------------------------------------------------
# Fleet config — multi-vehicle simulation
# ---------------------------------------------------------------------------


class RegionalWeatherConfig(BaseModel):
    """Climate profile for a geographic region."""

    ambient_temp_mean_c: float = Field(default=15.0, description="Annual mean ambient temperature °C")
    ambient_temp_std_c: float = Field(default=8.0, ge=0, description="Day-to-day σ °C")
    seasonal_amplitude_c: float = Field(
        default=10.0,
        ge=0,
        description="Half-amplitude of the seasonal sinusoidal swing (±°C around mean)",
    )
    season_peak_day: int = Field(
        default=200,
        ge=1,
        le=365,
        description="Day of year when temperature peaks (200 ≈ mid-July for northern hemisphere)",
    )
    supply_voltage_mean_v: float = Field(default=13.5, description="Mean bus voltage V")
    supply_voltage_std_v: float = Field(default=0.3, ge=0, description="Bus voltage σ V")


class VehicleArchetypeConfig(BaseModel):
    """A vehicle population segment — sampled to produce individual vehicle specs."""

    id: str = Field(description="Unique archetype identifier used in manifest and tags")
    weight: float = Field(default=1.0, gt=0, description="Relative weight in fleet sampling")
    profile: str = Field(
        default="mixed",
        description="Driving profile: commuter | mixed | heavy",
    )
    age_months_min: int = Field(default=0, ge=0, description="Min vehicle age in months")
    age_months_max: int = Field(default=24, ge=0, description="Max vehicle age in months")
    region: str = Field(
        default="temperate",
        description="Region key — must match a key in fleet.regions",
    )
    fault_rate_overrides: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Override specific fault rates for this archetype. "
            "Keys must match FaultRateConfig field names. "
            "Example: {connector_aging: 0.04} for an aged fleet."
        ),
    )


class FleetConfig(BaseModel):
    """Fleet-scale generation settings.

    When present as the ``fleet`` key in a GeneratorConfig, activates fleet mode:
    multiple vehicles generated in parallel from population archetypes with
    regional weather correlation.
    """

    n_vehicles: int = Field(default=50, ge=1, description="Total vehicles to simulate")
    seed: int = Field(default=42, description="Master seed for reproducible fleet sampling")
    start_date: str = Field(
        default="2026-01-01",
        description="Calendar start date for all vehicles (ISO-8601: YYYY-MM-DD)",
    )
    duration_days: int = Field(default=90, ge=1, description="Simulation span in days per vehicle")
    max_workers: int = Field(
        default=4,
        ge=1,
        description="Parallel workers for vehicle generation (ProcessPoolExecutor)",
    )
    write_combined: bool = Field(
        default=False,
        description=(
            "If True, concatenate all vehicles into fleet_telemetry.parquet / "
            "fleet_labels.parquet.  Disabled by default for large fleets."
        ),
    )
    archetypes: list[VehicleArchetypeConfig] = Field(
        default_factory=lambda: [
            VehicleArchetypeConfig(
                id="commuter",
                weight=0.5,
                profile="commuter",
                age_months_min=0,
                age_months_max=36,
                region="temperate",
            ),
            VehicleArchetypeConfig(
                id="heavy",
                weight=0.3,
                profile="heavy",
                age_months_min=12,
                age_months_max=60,
                region="temperate",
                fault_rate_overrides={"connector_aging": 0.03, "gradual_degradation": 0.02},
            ),
            VehicleArchetypeConfig(
                id="nordic_aged",
                weight=0.2,
                profile="commuter",
                age_months_min=24,
                age_months_max=72,
                region="nordic",
                fault_rate_overrides={"cold_crank": 1.5, "connector_aging": 0.04},
            ),
        ]
    )
    regions: dict[str, RegionalWeatherConfig] = Field(
        default_factory=lambda: {
            "temperate": RegionalWeatherConfig(
                ambient_temp_mean_c=13.0,
                ambient_temp_std_c=7.0,
                seasonal_amplitude_c=12.0,
                season_peak_day=196,
            ),
            "nordic": RegionalWeatherConfig(
                ambient_temp_mean_c=3.0,
                ambient_temp_std_c=9.0,
                seasonal_amplitude_c=18.0,
                season_peak_day=196,
            ),
            "mediterranean": RegionalWeatherConfig(
                ambient_temp_mean_c=18.0,
                ambient_temp_std_c=6.0,
                seasonal_amplitude_c=10.0,
                season_peak_day=196,
            ),
        }
    )


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------


class GeneratorConfig(BaseModel):
    """Top-level config — drives all generation modes.

    Single-vehicle mode uses ``simulation`` + ``features`` + ``storage``.
    Fleet mode is activated when the ``fleet`` key is present.
    Extra YAML keys are silently ignored for forward-compatibility.
    """

    model_config = {"extra": "ignore"}

    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    fleet: Optional[FleetConfig] = Field(
        default=None,
        description="Fleet settings — when present, activates multi-vehicle fleet mode.",
    )


def load_config(path: str | Path) -> GeneratorConfig:
    """Load a GeneratorConfig from a YAML or JSON file.

    After parsing, resolves the topology:
      - If use_example_topology is True, populates channels from example_topology()
      - If channel_specs are present, expands them via the eFuse catalog
      - Otherwise uses the explicit channels list as-is
    """
    path = Path(path)
    with open(path) as f:
        raw = yaml.safe_load(f)
    return load_config_data(raw)


def load_config_data(raw: dict) -> GeneratorConfig:
    """Validate config data from an in-memory mapping and resolve topology."""
    cfg = GeneratorConfig.model_validate(raw)
    _resolve_topology(cfg)
    return cfg


def default_config() -> GeneratorConfig:
    """Return a sensible default config for quick starts."""
    return GeneratorConfig()


def _resolve_topology(cfg: GeneratorConfig) -> None:
    """Populate simulation channels from topology or channel_specs."""
    from efuse_datagen.config.catalog import build_channels, example_topology

    sim = cfg.simulation

    if sim.use_example_topology:
        zones, specs = example_topology()
        sim.zones = zones
        sim.channels = build_channels(zones, specs)
        return

    if sim.channel_specs:
        sim.channels = build_channels(sim.zones, sim.channel_specs)
        return

    # Otherwise: use explicit channels list as-is



