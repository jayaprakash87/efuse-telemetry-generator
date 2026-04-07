"""ADC quantization tests for current and voltage channels."""

from efuse_datagen.schemas.telemetry import ChannelMeta
from efuse_datagen.simulation.generator import TelemetryGenerator
from tests.conftest import make_config


def test_voltage_adc_quantization():
    """Voltage signal should be quantized to voltage_adc_bits resolution."""
    ch = ChannelMeta(
        channel_id="ch_01",
        load_name="test",
        nominal_current_a=5.0,
        voltage_adc_bits=10,
        can_voltage_resolution_v=0.0,  # disable CAN packing to isolate ADC test
    )
    cfg = make_config(channels=[ch], duration_s=5.0, sample_interval_ms=50.0)
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()
    voltages = df["voltage_v"].dropna().values
    # With 10-bit ADC and ~40.5V range, LSB ≈ 0.0396V
    v_lsb = (ch.nominal_voltage_v * 3.0) / (2**ch.voltage_adc_bits)
    # Verify all voltages are near multiples of LSB
    residuals = voltages / v_lsb - (voltages / v_lsb).round()
    assert abs(residuals).max() < 0.01, "Voltage not quantized to voltage_adc_bits"


def test_current_adc_quantization():
    """Current signal should be quantized per current_adc_bits."""
    ch = ChannelMeta(
        channel_id="ch_01",
        load_name="test",
        nominal_current_a=5.0,
        max_current_a=20.0,
        current_adc_bits=10,  # coarse — easy to verify
        can_current_resolution_a=0.0,  # disable CAN packing to isolate ADC test
    )
    cfg = make_config(channels=[ch], duration_s=5.0, sample_interval_ms=50.0)
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()
    currents = df["current_a"].dropna().values
    adc_range = ch.max_current_a * 1.5
    lsb = adc_range / (2**ch.current_adc_bits)
    residuals = currents / lsb - (currents / lsb).round()
    assert abs(residuals).max() < 0.01, "Current not quantized to current_adc_bits"
