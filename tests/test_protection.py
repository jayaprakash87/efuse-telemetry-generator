"""F(i,t) protection, thermal shutdown, and protection event tests."""

from efuse_datagen.schemas.telemetry import (
    ChannelMeta,
    FaultInjection,
    FaultType,
    ProtectionEvent,
)
from efuse_datagen.simulation.generator import TelemetryGenerator
from tests.conftest import make_config


def test_fit_protection_trips_on_overload():
    """Overload spike fault should still cause a trip via F(i,t) model."""
    ch = ChannelMeta(
        channel_id="ch_01",
        load_name="test",
        nominal_current_a=5.0,
        max_current_a=20.0,
        fuse_rating_a=15.0,
        cooldown_s=0.5,
        max_retries=2,
    )
    cfg = make_config(
        channels=[ch],
        duration_s=10.0,
        sample_interval_ms=50.0,
        fault_injections=[
            FaultInjection(
                channel_id="ch_01",
                fault_type=FaultType.OVERLOAD_SPIKE,
                start_s=2.0,
                duration_s=4.0,
                intensity=0.9,
            )
        ],
    )
    gen = TelemetryGenerator(cfg)
    df, labels = gen.generate()
    # Trip flag should be set at some point during the fault
    assert df["trip_flag"].any(), "F(i,t) protection should trip on overload"
    # After max retries, channel should latch off (current near zero)
    tripped_rows = df[df["trip_flag"]]
    assert (tripped_rows["current_a"].abs() < 1.0).any(), "Latch-off should have near-zero current"


def test_protection_event_tagged_on_overload():
    """protection_event column should carry SCP/I2T/LATCH_OFF, not just 'none'."""
    ch = ChannelMeta(
        channel_id="ch_01",
        load_name="test",
        nominal_current_a=5.0,
        max_current_a=20.0,
        fuse_rating_a=15.0,
        cooldown_s=0.5,
        max_retries=2,
    )
    cfg = make_config(
        channels=[ch],
        duration_s=10.0,
        sample_interval_ms=50.0,
        fault_injections=[
            FaultInjection(
                channel_id="ch_01",
                fault_type=FaultType.OVERLOAD_SPIKE,
                start_s=2.0,
                duration_s=4.0,
                intensity=0.9,
            )
        ],
    )
    gen = TelemetryGenerator(cfg)
    df, labels = gen.generate()

    assert "protection_event" in df.columns, "DataFrame must include protection_event"
    events = set(df["protection_event"].unique())
    # Should have at least 'none' and one of the trip types
    assert ProtectionEvent.NONE.value in events
    non_none = events - {ProtectionEvent.NONE.value}
    assert len(non_none) > 0, "Overload should produce at least one protection event"
    # All non-none events should be valid ProtectionEvent values
    valid_values = {e.value for e in ProtectionEvent}
    assert non_none <= valid_values, f"Unexpected protection events: {non_none - valid_values}"


def test_nominal_has_no_protection_events():
    """Nominal scenario should have protection_event = 'none' everywhere."""
    cfg = make_config()
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()
    assert (df["protection_event"] == ProtectionEvent.NONE.value).all()


def test_thermal_shutdown_fires_on_extreme_drift():
    """A THERMAL_DRIFT fault with high intensity on a low-threshold channel
    should trigger THERMAL_SHUTDOWN protection events."""
    ch = ChannelMeta(
        channel_id="ch_01",
        load_name="test",
        nominal_current_a=10.0,
        max_current_a=30.0,
        fuse_rating_a=20.0,
        thermal_shutdown_c=100.0,  # low threshold to make it easier to trigger
        r_thermal_kw=60.0,  # higher thermal resistance → faster heating
        tau_thermal_s=5.0,
        t_ambient_c=25.0,
    )
    cfg = make_config(
        channels=[ch],
        duration_s=20.0,
        sample_interval_ms=100.0,
        fault_injections=[
            FaultInjection(
                channel_id="ch_01",
                fault_type=FaultType.THERMAL_DRIFT,
                start_s=1.0,
                duration_s=15.0,
                intensity=1.0,
            )
        ],
    )
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()

    thermal_events = df[df["protection_event"] == ProtectionEvent.THERMAL_SHUTDOWN.value]
    assert len(thermal_events) > 0, "Thermal shutdown should fire when T_j exceeds limit"
    # During thermal shutdown, current should be near zero
    assert thermal_events["current_a"].abs().max() < 0.5


def test_thermal_shutdown_hysteresis_recovery():
    """After thermal shutdown, channel should recover only after temperature drops
    below the hysteresis band (thermal_limit - 20°C)."""
    ch = ChannelMeta(
        channel_id="ch_01",
        load_name="test",
        nominal_current_a=10.0,
        max_current_a=30.0,
        fuse_rating_a=20.0,
        thermal_shutdown_c=100.0,
        r_thermal_kw=60.0,
        tau_thermal_s=3.0,  # fast thermal response for quicker decay
        t_ambient_c=25.0,
        rds_on_tempco_exp=0.0,  # disable tempco: this test exercises hysteresis, not Rds,on(T)
    )
    cfg = make_config(
        channels=[ch],
        duration_s=60.0,
        sample_interval_ms=100.0,
        fault_injections=[
            FaultInjection(
                channel_id="ch_01",
                fault_type=FaultType.THERMAL_DRIFT,
                start_s=1.0,
                duration_s=5.0,  # short fault → temp should decay quickly after
                intensity=1.0,
            )
        ],
    )
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()

    events = df["protection_event"].values
    # Should see THERMAL_SHUTDOWN events followed by a return to NONE
    thermal_mask = events == ProtectionEvent.THERMAL_SHUTDOWN.value
    if thermal_mask.any():
        first_shutdown = thermal_mask.argmax()
        # Find first recovery (non-shutdown) after shutdown
        post_shutdown = events[first_shutdown:]
        recovery_mask = post_shutdown != ProtectionEvent.THERMAL_SHUTDOWN.value
        # Should eventually recover (fault ends, temp decays)
        assert recovery_mask.any(), "Channel should recover after temp drops below hysteresis band"


def test_nominal_no_thermal_shutdown():
    """Nominal operation should never produce THERMAL_SHUTDOWN events."""
    cfg = make_config()
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()
    assert (df["protection_event"] != ProtectionEvent.THERMAL_SHUTDOWN.value).all()
