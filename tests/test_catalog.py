"""Catalog channel-building tests."""

from efuse_datagen.config.catalog import build_channels, EFUSE_CATALOG
from efuse_datagen.schemas.telemetry import ZoneController


def test_catalog_propagates_dual_adc():
    """build_channels should propagate current/voltage ADC bits from catalog."""
    zones = [ZoneController(zone_id="z1", label="Test Zone", num_channels=2)]
    specs = [
        {"channel_id": "ch_001", "zone_id": "z1", "efuse_family": "inf_hs_14a", "load_name": "headlamp_left"},
        {"channel_id": "ch_002", "zone_id": "z1", "efuse_family": "st_hs_30a", "load_name": "seat_heater"},
    ]
    channels = build_channels(zones, specs)
    ch = channels[0]
    profile = EFUSE_CATALOG[ch.efuse_family]
    assert ch.current_adc_bits == profile.current_adc_bits
    assert ch.voltage_adc_bits == profile.voltage_adc_bits
