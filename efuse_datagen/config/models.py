"""Configuration models and YAML/JSON loading.

All runtime behavior is driven by config objects so scenarios are
reproducible and parameters are never buried in code.
"""

from __future__ import annotations

from pathlib import Path

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


class DriveCycleConfig(BaseModel):
    """Multi-day drive cycle schedule configuration.

    When ``enabled=True`` the planner auto-generates a realistic month-long
    schedule of ignition cycles, overriding the top-level ``duration_s``,
    ``power_state_events``, and ``fault_injections``.
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
    scenario_id: str = "default"
    name: str = "Default Scenario"
    description: str = ""
    duration_s: float = 60.0
    sample_interval_ms: float = 100.0
    seed: int = 42
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
    window_duration_s: float = Field(default=5.0, description="Rolling window duration in seconds")
    min_duration_s: float = Field(
        default=1.0, description="Minimum data duration before features are valid"
    )
    # Legacy sample-count fields — used if > 0, else auto-computed from duration
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
    output_dir: str = "output"
    format: str = "parquet"  # "parquet" | "csv" | "json"


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------


class GeneratorConfig(BaseModel):
    """Top-level config for the standalone data generator."""

    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)


# Keep PlatformConfig as an alias so existing YAML files (which may have
# extra top-level keys like 'model', 'edge', 'mqtt') still parse cleanly —
# Pydantic simply ignores unknown fields by default.
class PlatformConfig(GeneratorConfig):
    """Superset of GeneratorConfig — tolerates full VIP YAML files."""

    model_config = {"extra": "ignore"}


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_config(path: str | Path) -> PlatformConfig:
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


def load_config_data(raw: dict) -> PlatformConfig:
    """Validate config data from an in-memory mapping and resolve topology."""
    cfg = PlatformConfig.model_validate(raw)
    _resolve_topology(cfg)
    return cfg


def default_config() -> PlatformConfig:
    """Return a sensible default config for quick starts."""
    return PlatformConfig()


def _resolve_topology(cfg: PlatformConfig) -> None:
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
