"""Shared test fixtures and helpers."""

from efuse_datagen.config.models import SimulationConfig
from efuse_datagen.schemas.telemetry import ChannelMeta


def make_config(**overrides) -> SimulationConfig:
    """Build a minimal SimulationConfig with sensible test defaults."""
    defaults = dict(
        scenario_id="test",
        name="Test",
        duration_s=10.0,
        sample_interval_ms=100.0,
        seed=42,
        channels=[ChannelMeta(channel_id="ch_01", load_name="test_load", nominal_current_a=5.0)],
        fault_injections=[],
    )
    defaults.update(overrides)
    return SimulationConfig(**defaults)
