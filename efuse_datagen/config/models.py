"""Configuration models and YAML/JSON loading.

All runtime behavior is driven by config objects so scenarios are
reproducible and parameters are never buried in code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

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

    model_config = {"extra": "forbid"}

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
    profile: Literal["commuter", "mixed", "heavy"] = Field(
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

    @model_validator(mode="after")
    def _check_trip_bounds(self) -> DriveCycleConfig:
        if self.min_trip_minutes >= self.max_trip_minutes:
            raise ValueError(
                f"min_trip_minutes ({self.min_trip_minutes}) must be < "
                f"max_trip_minutes ({self.max_trip_minutes})"
            )
        return self


class SimulationConfig(BaseModel):
    """Core scenario definition: channels, faults, power states, and drive cycle settings."""

    model_config = {"extra": "forbid"}

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
    topology_file: str = Field(
        default="",
        description=(
            "Path to a reusable topology YAML file containing zones and channel_specs. "
            "Can be a bundled name (e.g. 'bev_4zone_65ch') or a file path. "
            "When set, zones and channel_specs are loaded from this file."
        ),
    )
    fault_injections: list[FaultInjection] = Field(default_factory=list)
    power_state_events: list["PowerStateEvent"] = Field(
        default_factory=list,
        description=(
            "Ordered list of power-state transitions. Empty = always ACTIVE. "
            "First entry need not start at t=0 — state before first event is ACTIVE."
        ),
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

    model_config = {"extra": "forbid"}

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

    @model_validator(mode="after")
    def _check_window_bounds(self) -> FeatureConfig:
        if self.window_duration_s <= 0:
            raise ValueError("window_duration_s must be > 0")
        if self.min_duration_s <= 0:
            raise ValueError("min_duration_s must be > 0")
        if self.window_size < 0:
            raise ValueError("window_size must be >= 0")
        if self.min_periods < 0:
            raise ValueError("min_periods must be >= 0")
        return self

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

    model_config = {"extra": "forbid"}

    output_dir: str = "output"
    format: Literal["parquet", "csv", "json"] = "parquet"


# ---------------------------------------------------------------------------
# Fleet config — multi-vehicle simulation
# ---------------------------------------------------------------------------


class RegionalWeatherConfig(BaseModel):
    """Climate profile for a geographic region."""

    model_config = {"extra": "forbid"}

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
    profile: Literal["commuter", "mixed", "heavy"] = Field(
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

    @model_validator(mode="after")
    def _check_age_bounds(self) -> VehicleArchetypeConfig:
        if self.age_months_min > self.age_months_max:
            raise ValueError(
                f"age_months_min ({self.age_months_min}) must be <= "
                f"age_months_max ({self.age_months_max})"
            )
        return self


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

    @model_validator(mode="after")
    def _check_fleet_consistency(self) -> FleetConfig:
        from datetime import date as _date

        try:
            _date.fromisoformat(self.start_date)
        except ValueError:
            raise ValueError(
                f"start_date '{self.start_date}' is not valid ISO-8601 (expected YYYY-MM-DD)"
            )
        region_keys = set(self.regions)
        for arch in self.archetypes:
            if arch.region not in region_keys:
                raise ValueError(
                    f"Archetype '{arch.id}' references region '{arch.region}' "
                    f"which is not defined in fleet.regions (available: {sorted(region_keys)})"
                )
            valid_rate_fields = set(FaultRateConfig.model_fields)
            bad = set(arch.fault_rate_overrides) - valid_rate_fields
            if bad:
                raise ValueError(
                    f"Archetype '{arch.id}' has unknown fault_rate_overrides: {sorted(bad)}. "
                    f"Valid keys: {sorted(valid_rate_fields)}"
                )
        return self


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------


class GeneratorConfig(BaseModel):
    """Top-level config — drives all generation modes.

    Single-vehicle mode uses ``simulation`` + ``features`` + ``storage``.
    Fleet mode is activated when the ``fleet`` key is present.
    Unknown YAML keys are rejected — typos surface as clear validation errors.
    """

    model_config = {"extra": "forbid"}

    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    features: FeatureConfig = Field(default_factory=FeatureConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    fleet: FleetConfig | None = Field(
        default=None,
        description="Fleet settings — when present, activates multi-vehicle fleet mode.",
    )


def load_config(path: str | Path) -> GeneratorConfig:
    """Load a GeneratorConfig from a YAML or JSON file.

    After parsing, resolves the topology:
      - If topology_file is set, loads zones and channel_specs from that file
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
    sim_raw = raw.get("simulation", {})
    _resolve_topology(cfg, channels_explicit="channels" in sim_raw)
    return cfg


def default_config() -> GeneratorConfig:
    """Return a sensible default config for quick starts."""
    return GeneratorConfig()


def _resolve_topology(cfg: GeneratorConfig, *, channels_explicit: bool = False) -> None:
    """Populate simulation channels from topology file, channel_specs, or explicit channels."""
    from efuse_datagen.config.catalog import build_channels

    sim = cfg.simulation

    # Guard: reject ambiguous topology sources
    has_topology_file = bool(sim.topology_file)
    has_channel_specs = bool(sim.channel_specs)
    has_explicit_channels = channels_explicit and bool(sim.channels)

    sources = [
        name
        for name, active in [
            ("topology_file", has_topology_file),
            ("channel_specs", has_channel_specs),
            ("channels", has_explicit_channels),
        ]
        if active
    ]
    if len(sources) > 1:
        raise ValueError(
            f"Multiple topology sources specified: {', '.join(sources)}. "
            "Use exactly one of: topology_file (for reusable architectures), "
            "channel_specs (for catalog-based setup), or channels (for explicit definitions)."
        )

    # 1. Load from a topology file (bundled name or file path)
    if has_topology_file:
        _load_topology_file(sim)

    # 2. Expand channel_specs via catalog
    if sim.channel_specs:
        sim.channels = build_channels(sim.zones, sim.channel_specs)
        return

    # 3. Otherwise: use explicit channels list as-is


_topology_cache: dict[str, dict] = {}


def _load_topology_file(sim: SimulationConfig) -> None:
    """Load zones and channel_specs from a topology YAML file.

    Resolution order:
      1. Bundled topology (e.g. 'bev_4zone_65ch') in the topologies/ package directory
      2. Absolute or relative file path

    Parsed YAML is cached so fleet-mode (N vehicles sharing one topology)
    doesn't re-parse the same file on every vehicle.
    """
    from importlib.resources import files as pkg_files

    name = sim.topology_file

    # Return cached copy if already parsed
    if name in _topology_cache:
        topo = _topology_cache[name]
    else:
        # Try bundled topology first
        bundled = pkg_files("efuse_datagen").joinpath(f"config/topologies/{name}.yaml")
        if bundled.is_file():  # type: ignore[union-attr]
            topo = yaml.safe_load(bundled.read_text(encoding="utf-8"))  # type: ignore[union-attr]
        else:
            # Treat as a file path — guard against path traversal
            path = Path(name).resolve()
            if ".." in Path(name).parts:
                raise ValueError(
                    f"Topology file path must not contain '..': '{name}'. "
                    f"Use an absolute path or a path relative to the working directory."
                )
            if not path.exists():
                raise FileNotFoundError(
                    f"Topology file not found: '{name}'. "
                    f"Provide an existing file path or a bundled topology name."
                )
            with open(path) as f:
                topo = yaml.safe_load(f)

        if not isinstance(topo, dict):
            raise ValueError(f"Topology file '{name}' must be a YAML mapping with 'zones' and 'channel_specs'.")

        _topology_cache[name] = topo

    # Merge — topology file provides zones and channel_specs;
    # the scenario config can still override or extend.
    if "zones" in topo and not sim.zones:
        sim.zones = [ZoneController(**z) for z in topo["zones"]]
    if "channel_specs" in topo and not sim.channel_specs:
        sim.channel_specs = list(topo["channel_specs"])



