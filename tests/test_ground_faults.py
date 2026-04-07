"""Tests for ground-offset and short-to-ground faults (P1 hardware realism)."""

import numpy as np
import pandas as pd

from efuse_datagen.schemas.telemetry import (
    ChannelMeta,
    FaultInjection,
    FaultType,
    ProtectionEvent,
)
from efuse_datagen.simulation.generator import TelemetryGenerator
from tests.conftest import make_config


def _base_ch(**extra) -> ChannelMeta:
    return ChannelMeta(
        channel_id="ch_01",
        load_name="test",
        nominal_current_a=5.0,
        max_current_a=30.0,
        fuse_rating_a=15.0,
        r_ds_on_ohm=0.020,
        harness_r_ohm=0.030,
        can_current_resolution_a=0.0,  # disable CAN packing for precise assertions
        can_voltage_resolution_v=0.0,
        **extra,
    )


def _fault_window(df: pd.DataFrame, start_s: float, duration_s: float) -> pd.DataFrame:
    """Return rows within [start_s, start_s + duration_s) relative to first timestamp."""
    t0 = df["timestamp"].iloc[0]
    t_start = t0 + pd.Timedelta(seconds=start_s)
    t_end = t0 + pd.Timedelta(seconds=start_s + duration_s)
    return df[(df["timestamp"] >= t_start) & (df["timestamp"] < t_end)]


def _pre_fault_window(df: pd.DataFrame, start_s: float) -> pd.DataFrame:
    """Return rows before start_s relative to first timestamp."""
    t0 = df["timestamp"].iloc[0]
    t_start = t0 + pd.Timedelta(seconds=start_s)
    return df[df["timestamp"] < t_start]


# ---------------------------------------------------------------------------
# GROUND_OFFSET tests
# ---------------------------------------------------------------------------

_GO_START_S = 3.0
_GO_DURATION_S = 5.0


def _ground_offset_config(ch: ChannelMeta, intensity: float = 0.5, **kw):
    defaults = dict(
        channels=[ch],
        duration_s=10.0,
        sample_interval_ms=50.0,
        fault_injections=[
            FaultInjection(
                channel_id="ch_01",
                fault_type=FaultType.GROUND_OFFSET,
                start_s=_GO_START_S,
                duration_s=_GO_DURATION_S,
                intensity=intensity,
            )
        ],
    )
    defaults.update(kw)
    return make_config(**defaults)


def test_ground_offset_raises_voltage():
    """During GROUND_OFFSET, voltage readings should be biased higher than nominal."""
    ch = _base_ch(ground_offset_max_v=2.0)
    cfg = _ground_offset_config(ch, intensity=1.0)
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()

    pre_fault = _pre_fault_window(df, _GO_START_S)["voltage_v"].dropna()
    during_fault = _fault_window(df, _GO_START_S, _GO_DURATION_S)["voltage_v"].dropna()

    assert len(during_fault) > 0, "Should have fault-window rows"
    # Mean voltage during fault (offset ramps to 2 V by end) should exceed pre-fault
    assert during_fault.mean() > pre_fault.mean() + 0.1, (
        "Ground offset should bias voltage readings higher; "
        f"pre={pre_fault.mean():.3f} V, during={during_fault.mean():.3f} V"
    )


def test_ground_offset_raises_current():
    """During GROUND_OFFSET, current readings should be elevated due to ISENSE CM shift."""
    ch = _base_ch(ground_offset_max_v=2.0)
    cfg = _ground_offset_config(ch, intensity=1.0)
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()

    pre_fault = _pre_fault_window(df, _GO_START_S)["current_a"].dropna()
    during_fault = _fault_window(df, _GO_START_S, _GO_DURATION_S)["current_a"].dropna()

    assert during_fault.mean() > pre_fault.mean(), (
        "Ground common-mode offset should lightly bias current readings upward"
    )


def test_ground_offset_ramps_over_time():
    """Ground offset should ramp from zero — later fault samples have larger offset."""
    ch = _base_ch(ground_offset_max_v=2.0)
    cfg = _ground_offset_config(ch, intensity=1.0)
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()

    fault_rows = _fault_window(df, _GO_START_S, _GO_DURATION_S)["voltage_v"].dropna()
    assert len(fault_rows) > 4, "Need enough fault rows to test ramp"
    first_half = fault_rows.iloc[: len(fault_rows) // 2].mean()
    second_half = fault_rows.iloc[len(fault_rows) // 2 :].mean()
    assert second_half > first_half, (
        "Ground offset should ramp — second half should show higher voltage offset"
    )


def test_ground_offset_does_not_trip():
    """GROUND_OFFSET is a measurement bias, not overcurrent — channel should stay on."""
    ch = _base_ch(ground_offset_max_v=1.0)
    cfg = _ground_offset_config(ch, intensity=0.5)
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()

    fault_rows = _fault_window(df, _GO_START_S, _GO_DURATION_S)
    assert not fault_rows["trip_flag"].any(), (
        "GROUND_OFFSET should not trip the eFuse — it is a measurement bias only"
    )


def test_ground_offset_intensity_scales_offset():
    """Higher intensity should produce a larger voltage offset."""
    ch_low = _base_ch(ground_offset_max_v=2.0)
    ch_high = _base_ch(ground_offset_max_v=2.0)

    cfg_low = _ground_offset_config(ch_low, intensity=0.2, seed=99)
    cfg_high = _ground_offset_config(ch_high, intensity=1.0, seed=99)

    df_low, _ = TelemetryGenerator(cfg_low).generate()
    df_high, _ = TelemetryGenerator(cfg_high).generate()

    mean_low = _fault_window(df_low, _GO_START_S, _GO_DURATION_S)["voltage_v"].mean()
    mean_high = _fault_window(df_high, _GO_START_S, _GO_DURATION_S)["voltage_v"].mean()
    assert mean_high > mean_low, (
        "Higher intensity GROUND_OFFSET should produce a larger voltage bias"
    )


# ---------------------------------------------------------------------------
# SHORT_TO_GROUND tests
# ---------------------------------------------------------------------------

_STG_START_S = 3.0
_STG_DURATION_S = 5.0


def _stg_config(ch: ChannelMeta, intensity: float = 1.0, **kw):
    defaults = dict(
        channels=[ch],
        duration_s=10.0,
        sample_interval_ms=10.0,
        fault_injections=[
            FaultInjection(
                channel_id="ch_01",
                fault_type=FaultType.SHORT_TO_GROUND,
                start_s=_STG_START_S,
                duration_s=_STG_DURATION_S,
                intensity=intensity,
            )
        ],
    )
    defaults.update(kw)
    return make_config(**defaults)


def test_stg_produces_high_current_spike():
    """SHORT_TO_GROUND should produce a measurable current spike above nominal before tripping."""
    ch = _base_ch(stg_resistance_ohm=0.05, cooldown_s=0.5, max_retries=1)
    cfg = _stg_config(ch, intensity=1.0)
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()

    # The eFuse trips within 1–2 samples, but the brief pre-trip ramp should
    # produce current clearly above nominal.  Check the full DataFrame peak
    # (protection trims sustained high current, not the initial ramp spike).
    peak_current = df["current_a"].abs().max()
    assert peak_current > ch.nominal_current_a * 2.0, (
        f"STG should produce >2× nominal current before protection trips "
        f"(nominal={ch.nominal_current_a} A, peak={peak_current:.2f} A)"
    )


def test_stg_collapses_voltage():
    """SHORT_TO_GROUND should collapse load voltage — short fraction of bus goes to load."""
    ch = _base_ch(stg_resistance_ohm=0.01, cooldown_s=0.5, max_retries=1)  # hard short: 0.01Ω
    cfg = _stg_config(ch, intensity=1.0)
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()

    pre_fault = _pre_fault_window(df, _STG_START_S)["voltage_v"].dropna()
    fault_rows = _fault_window(df, _STG_START_S, _STG_DURATION_S)["voltage_v"].dropna()

    # With R_stg=0.01, R_ds_on=0.02: V_load = V_bus * 0.01/0.03 = 33% of bus
    # So during STG fault, mean voltage should be < 50% of pre-fault nominal
    if len(fault_rows) > 0:
        assert fault_rows.mean() < pre_fault.mean() * 0.5, (
            "Hard STG (R=0.01Ω) should collapse load voltage to < 50% of nominal"
        )


def test_stg_triggers_protection():
    """SHORT_TO_GROUND high current should trigger eFuse protection."""
    ch = _base_ch(
        stg_resistance_ohm=0.05,
        fit_threshold_a2s=0.5,
        cooldown_s=0.5,
        max_retries=1,
    )
    cfg = _stg_config(ch, intensity=1.0)
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()

    assert df["trip_flag"].any(), "SHORT_TO_GROUND should trip the eFuse"
    events = set(df["protection_event"].unique())
    expected = {ProtectionEvent.SCP.value, ProtectionEvent.I2T.value, ProtectionEvent.LATCH_OFF.value}
    assert events & expected, (
        f"STG should produce SCP/I2T/LATCH_OFF protection event, got: {events}"
    )


def test_stg_lower_resistance_produces_higher_current():
    """Lower STG path resistance (harder short) should produce higher fault current."""
    ch_mild = _base_ch(stg_resistance_ohm=0.5, max_retries=0)
    ch_hard = _base_ch(stg_resistance_ohm=0.05, max_retries=0)

    cfg_mild = _stg_config(ch_mild, intensity=1.0, seed=42)
    cfg_hard = _stg_config(ch_hard, intensity=1.0, seed=42)

    df_mild, _ = TelemetryGenerator(cfg_mild).generate()
    df_hard, _ = TelemetryGenerator(cfg_hard).generate()

    peak_mild = df_mild["current_a"].abs().max()
    peak_hard = df_hard["current_a"].abs().max()
    assert peak_hard > peak_mild, (
        f"Harder STG (R=0.05 Ω) should draw more current than mild STG (R=0.5 Ω); "
        f"hard={peak_hard:.1f} A, mild={peak_mild:.1f} A"
    )


def test_stg_fault_labelled_correctly():
    """Labels DataFrame should tag SHORT_TO_GROUND fault type in the fault window."""
    ch = _base_ch(stg_resistance_ohm=0.05, max_retries=0)
    cfg = _stg_config(ch, intensity=1.0)
    gen = TelemetryGenerator(cfg)
    _, labels = gen.generate()

    assert len(labels) > 0, "Labels DataFrame should have fault rows for STG"
    assert FaultType.SHORT_TO_GROUND.value in labels["fault_type"].values, (
        "Labels should contain 'short_to_ground' fault_type entries"
    )


def test_ground_offset_fault_labelled_correctly():
    """Labels DataFrame should tag GROUND_OFFSET fault type in the fault window."""
    ch = _base_ch(ground_offset_max_v=2.0)
    cfg = _ground_offset_config(ch, intensity=1.0)
    gen = TelemetryGenerator(cfg)
    _, labels = gen.generate()

    assert len(labels) > 0, "Labels DataFrame should have fault rows for GROUND_OFFSET"
    assert FaultType.GROUND_OFFSET.value in labels["fault_type"].values, (
        "Labels should contain 'ground_offset' fault_type entries"
    )
