"""Configuration models and YAML/JSON loading.

All runtime behavior is driven by config objects so scenarios are
reproducible and parameters are never buried in code.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from vip_datagen.schemas.telemetry import ChannelMeta, FaultInjection, PowerState, ZoneController


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
# Model config
# ---------------------------------------------------------------------------


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
    cfg = PlatformConfig.model_validate(raw)
    _resolve_topology(cfg)
    return cfg


def default_config() -> PlatformConfig:
    """Return a sensible default config for quick starts."""
    return PlatformConfig()


def _resolve_topology(cfg: PlatformConfig) -> None:
    """Populate simulation channels from topology or channel_specs."""
    from vip_datagen.config.catalog import build_channels, example_topology

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
