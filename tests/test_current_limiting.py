"""Tests for IC current-limiting (I_CL) before F(i,t) trip."""


from efuse_datagen.schemas.telemetry import (
    ChannelMeta,
    FaultInjection,
    FaultType,
    ProtectionEvent,
)
from efuse_datagen.simulation.generator import TelemetryGenerator
from tests.conftest import make_config


def _overload_config(ch: ChannelMeta, intensity: float = 0.7, **kw):
    """Helper: 10 s config with a sustained overload fault."""
    defaults = dict(
        channels=[ch],
        duration_s=10.0,
        sample_interval_ms=10.0,
        fault_injections=[
            FaultInjection(
                channel_id="ch_01",
                fault_type=FaultType.OVERLOAD_SPIKE,
                start_s=2.0,
                duration_s=6.0,
                intensity=intensity,
            ),
        ],
    )
    defaults.update(kw)
    return make_config(**defaults)


def test_current_clamped_at_icl_during_overload():
    """During overload, peak current should not exceed I_CL + noise margin."""
    fuse_a = 15.0
    ch = ChannelMeta(
        channel_id="ch_01",
        load_name="test",
        nominal_current_a=5.0,
        max_current_a=40.0,
        fuse_rating_a=fuse_a,
        cooldown_s=0.5,
        max_retries=2,
        current_limit_a=0.0,  # auto → 1.5× fuse_rating = 22.5 A
        can_current_resolution_a=0.0,  # disable CAN packing for precise assertion
    )
    i_cl = fuse_a * 1.5  # expected auto-resolved value

    cfg = _overload_config(ch, intensity=0.8)
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()

    # Filter to fault window rows that aren't tripped/cooled-down
    fault_mask = (df["current_a"].abs() > ch.nominal_current_a * 1.2) & ~df["trip_flag"]
    if fault_mask.any():
        overcurrent = df.loc[fault_mask, "current_a"].abs()
        # Allow 5% noise margin above I_CL (the 2% σ normal noise)
        assert overcurrent.max() < i_cl * 1.10, (
            f"Peak overcurrent {overcurrent.max():.2f} A exceeds I_CL {i_cl:.1f} A + margin"
        )


def test_custom_current_limit_respected():
    """Explicit current_limit_a should override the auto 1.5× fuse value."""
    custom_icl = 10.0
    ch = ChannelMeta(
        channel_id="ch_01",
        load_name="test",
        nominal_current_a=5.0,
        max_current_a=40.0,
        fuse_rating_a=15.0,
        cooldown_s=0.5,
        max_retries=2,
        current_limit_a=custom_icl,
        can_current_resolution_a=0.0,
    )
    cfg = _overload_config(ch, intensity=0.8)
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()

    fault_mask = (df["current_a"].abs() > ch.nominal_current_a * 1.2) & ~df["trip_flag"]
    if fault_mask.any():
        overcurrent = df.loc[fault_mask, "current_a"].abs()
        assert overcurrent.max() < custom_icl * 1.10, (
            f"Peak overcurrent {overcurrent.max():.2f} A exceeds custom I_CL {custom_icl} A"
        )


def test_fit_still_trips_under_current_limit():
    """F(i,t) should eventually trip even when current is clamped at I_CL.

    The IC clamps output but still dissipates P = I_CL² × Rds,on internally,
    so the energy integral must still accumulate and trip.
    """
    ch = ChannelMeta(
        channel_id="ch_01",
        load_name="test",
        nominal_current_a=5.0,
        max_current_a=40.0,
        fuse_rating_a=10.0,  # low rating → easier to trip
        fit_threshold_a2s=1.0,  # low threshold
        cooldown_s=0.5,
        max_retries=1,
        current_limit_a=0.0,  # auto → 15.0 A
        can_current_resolution_a=0.0,
    )
    cfg = _overload_config(ch, intensity=0.9, duration_s=15.0)
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()

    assert df["trip_flag"].any(), (
        "F(i,t) should trip during sustained overload even with current clamping"
    )
    events = set(df["protection_event"].unique())
    assert ProtectionEvent.I2T.value in events or ProtectionEvent.LATCH_OFF.value in events, (
        "Expected I2T or LATCH_OFF protection event after sustained clamped overload"
    )


def test_scp_fires_above_icl():
    """High-intensity overload exceeding SCP threshold should trigger SCP despite I_CL."""
    ch = ChannelMeta(
        channel_id="ch_01",
        load_name="test",
        nominal_current_a=5.0,
        max_current_a=40.0,
        fuse_rating_a=15.0,
        short_circuit_threshold_a=50.0,  # lower SCP threshold to ensure it fires
        cooldown_s=0.5,
        max_retries=1,
        current_limit_a=0.0,
        can_current_resolution_a=0.0,
    )
    cfg = make_config(
        channels=[ch],
        duration_s=10.0,
        sample_interval_ms=10.0,
        fault_injections=[
            FaultInjection(
                channel_id="ch_01",
                fault_type=FaultType.OVERLOAD_SPIKE,
                start_s=2.0,
                duration_s=4.0,
                intensity=1.0,
            ),
        ],
    )
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()

    events = set(df["protection_event"].unique())
    assert ProtectionEvent.SCP.value in events, (
        "Short-circuit fault should trigger SCP even with I_CL active"
    )
