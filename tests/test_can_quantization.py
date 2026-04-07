"""Tests for CAN signal packing quantization."""

import numpy as np

from efuse_datagen.schemas.telemetry import ChannelMeta, SourceProtocol
from efuse_datagen.simulation.generator import TelemetryGenerator
from tests.conftest import make_config


def _make_can_channel(**extra) -> ChannelMeta:
    return ChannelMeta(
        channel_id="ch_01",
        load_name="test",
        nominal_current_a=5.0,
        max_current_a=20.0,
        source_protocol=SourceProtocol.CAN,
        can_current_resolution_a=0.05,
        can_voltage_resolution_v=0.05,
        **extra,
    )


def test_can_current_quantized_to_resolution():
    """CAN current values should be exact multiples of can_current_resolution_a."""
    ch = _make_can_channel()
    cfg = make_config(channels=[ch], duration_s=5.0, sample_interval_ms=50.0)
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()

    currents = df["current_a"].dropna().values
    res = ch.can_current_resolution_a
    residuals = currents / res - np.round(currents / res)
    assert np.abs(residuals).max() < 1e-9, (
        f"Current values not quantized to CAN resolution {res} A/bit"
    )


def test_can_voltage_quantized_to_resolution():
    """CAN voltage values should be exact multiples of can_voltage_resolution_v."""
    ch = _make_can_channel()
    cfg = make_config(channels=[ch], duration_s=5.0, sample_interval_ms=50.0)
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()

    voltages = df["voltage_v"].dropna().values
    res = ch.can_voltage_resolution_v
    residuals = voltages / res - np.round(voltages / res)
    assert np.abs(residuals).max() < 1e-9, (
        f"Voltage values not quantized to CAN resolution {res} V/bit"
    )


def test_xcp_bypasses_can_quantization():
    """XCP-protocol channels should NOT get CAN packing quantization."""
    ch = ChannelMeta(
        channel_id="ch_01",
        load_name="test",
        nominal_current_a=5.0,
        max_current_a=20.0,
        source_protocol=SourceProtocol.XCP,
        can_current_resolution_a=0.05,  # set but should be ignored for XCP
        current_adc_bits=12,
    )
    cfg = make_config(channels=[ch], duration_s=5.0, sample_interval_ms=50.0)
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()

    currents = df["current_a"].dropna().values
    can_res = ch.can_current_resolution_a
    residuals = currents / can_res - np.round(currents / can_res)
    # Some residuals should be non-zero — XCP channels have ADC quantization
    # but NOT CAN packing
    assert np.abs(residuals).max() > 0.001, (
        "XCP channel appears CAN-quantized; CAN packing should be skipped"
    )


def test_can_resolution_zero_disables_packing():
    """Setting can_current_resolution_a=0 should skip CAN packing even for CAN protocol."""
    ch = ChannelMeta(
        channel_id="ch_01",
        load_name="test",
        nominal_current_a=5.0,
        max_current_a=20.0,
        source_protocol=SourceProtocol.CAN,
        can_current_resolution_a=0.0,
        current_adc_bits=12,
    )
    cfg = make_config(channels=[ch], duration_s=5.0, sample_interval_ms=50.0)
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()

    currents = df["current_a"].dropna().values
    # With a coarse CAN resolution like 0.05, values would all be multiples.
    # With resolution=0 (disabled), they should follow the finer ADC step.
    adc_range = ch.max_current_a * 1.5
    adc_lsb = adc_range / (2**ch.current_adc_bits)
    residuals = currents / adc_lsb - np.round(currents / adc_lsb)
    assert np.abs(residuals).max() < 0.01, (
        "With CAN resolution=0, current should follow ADC quantization only"
    )


def test_can_quantization_coarser_than_adc():
    """CAN packing at 0.1 A/bit should produce wider steps than 12-bit ADC alone."""
    ch_can = ChannelMeta(
        channel_id="ch_01",
        load_name="test",
        nominal_current_a=5.0,
        max_current_a=20.0,
        source_protocol=SourceProtocol.CAN,
        can_current_resolution_a=0.1,
        can_voltage_resolution_v=0.05,
        current_adc_bits=12,
    )
    ch_xcp = ChannelMeta(
        channel_id="ch_01",
        load_name="test",
        nominal_current_a=5.0,
        max_current_a=20.0,
        source_protocol=SourceProtocol.XCP,
        current_adc_bits=12,
    )

    cfg_can = make_config(channels=[ch_can], duration_s=5.0, sample_interval_ms=50.0, seed=42)
    cfg_xcp = make_config(channels=[ch_xcp], duration_s=5.0, sample_interval_ms=50.0, seed=42)

    gen_can = TelemetryGenerator(cfg_can)
    gen_xcp = TelemetryGenerator(cfg_xcp)
    df_can, _ = gen_can.generate()
    df_xcp, _ = gen_xcp.generate()

    unique_can = len(np.unique(np.round(df_can["current_a"].dropna().values, 6)))
    unique_xcp = len(np.unique(np.round(df_xcp["current_a"].dropna().values, 6)))
    assert unique_can < unique_xcp, (
        "CAN packing should produce fewer unique current levels than raw ADC"
    )
