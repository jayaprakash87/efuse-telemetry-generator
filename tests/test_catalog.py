"""Catalog channel-building tests."""

from efuse_datagen.config.catalog import build_channels, example_topology, EFUSE_CATALOG


def test_catalog_propagates_dual_adc():
    """build_channels should propagate current/voltage ADC bits from catalog."""
    zones, specs = example_topology()
    channels = build_channels(zones, specs)
    ch = channels[0]
    profile = EFUSE_CATALOG[ch.efuse_family]
    assert ch.current_adc_bits == profile.current_adc_bits
    assert ch.voltage_adc_bits == profile.voltage_adc_bits
