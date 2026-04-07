"""Power-state (sleep / wake / crank) tests."""

import pandas as pd

from efuse_datagen.config.models import PowerStateEvent
from efuse_datagen.schemas.telemetry import ChannelMeta, PowerClass, PowerState
from efuse_datagen.simulation.generator import TelemetryGenerator
from tests.conftest import make_config


def _make_ch_kl15(**extra) -> ChannelMeta:
    """KL15 (IGNITION) channel for sleep/wake tests."""
    kw: dict = dict(wake_inrush_factor=2.5, wake_inrush_duration_ms=100.0)
    kw.update(extra)
    return ChannelMeta(
        channel_id="ch_ign",
        load_name="headlamp",
        nominal_current_a=6.0,
        max_current_a=20.0,
        fuse_rating_a=15.0,
        thermal_shutdown_c=150.0,
        r_thermal_kw=20.0,
        tau_thermal_s=10.0,
        t_ambient_c=25.0,
        rds_on_tempco_exp=0.0,
        power_class=PowerClass.IGNITION,
        **kw,
    )


def _make_ch_kl30(**extra) -> ChannelMeta:
    """KL30 (ALWAYS_ON) channel for dark-current sleep tests."""
    return ChannelMeta(
        channel_id="ch_kl30",
        load_name="clock_memory",
        nominal_current_a=0.05,
        max_current_a=1.0,
        fuse_rating_a=2.0,
        thermal_shutdown_c=150.0,
        r_thermal_kw=20.0,
        tau_thermal_s=10.0,
        t_ambient_c=25.0,
        rds_on_tempco_exp=0.0,
        power_class=PowerClass.ALWAYS_ON,
        sleep_quiescent_ua=300.0,
        can_current_resolution_a=0.0,  # disable CAN packing; dark current < CAN LSB
        **extra,
    )


def test_ignition_channel_off_during_sleep():
    """KL15 IGNITION channel should have near-zero current during SLEEP state."""
    ch = _make_ch_kl15()
    cfg = make_config(
        duration_s=20.0,
        sample_interval_ms=100.0,
        channels=[ch],
        fault_injections=[],
        power_state_events=[
            PowerStateEvent(time_s=0.0, state=PowerState.SLEEP),
            PowerStateEvent(time_s=10.0, state=PowerState.ACTIVE),
        ],
    )
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()
    sleep_rows = df[df["timestamp"] < df["timestamp"].iloc[0] + pd.Timedelta(seconds=9.9)]
    assert sleep_rows["current_a"].abs().max() < 0.005, (
        "Ignition channel current should be < 5 mA during SLEEP"
    )
    assert not sleep_rows["state_on_off"].any(), (
        "Ignition channel state_on_off should be False during SLEEP"
    )


def test_always_on_channel_dark_current_during_sleep():
    """KL30 ALWAYS_ON channel should draw quiescent dark current during SLEEP."""
    ch = _make_ch_kl30()
    cfg = make_config(
        duration_s=20.0,
        sample_interval_ms=100.0,
        channels=[ch],
        fault_injections=[],
        power_state_events=[
            PowerStateEvent(time_s=0.0, state=PowerState.SLEEP),
        ],
    )
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()
    assert df["state_on_off"].all(), "ALWAYS_ON channel should remain ON during SLEEP"
    assert df["current_a"].mean() < 0.002, (
        "ALWAYS_ON sleep current should be < 2 mA (quiescent only)"
    )
    assert df["current_a"].mean() > 0.0001, (
        "ALWAYS_ON sleep current should be above zero (dark current)"
    )


def test_ignition_channel_nominal_during_active():
    """KL15 channel should carry nominal current when power state is ACTIVE."""
    ch = _make_ch_kl15()
    cfg = make_config(
        duration_s=10.0,
        sample_interval_ms=100.0,
        channels=[ch],
        fault_injections=[],
        power_state_events=[
            PowerStateEvent(time_s=0.0, state=PowerState.ACTIVE),
        ],
    )
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()
    assert df["current_a"].mean() > ch.nominal_current_a * 0.5, (
        "Current should be near nominal during ACTIVE state (0.5x accounts for ISENSE gain error)"
    )


def test_wake_transition_inrush():
    """On SLEEP->ACTIVE transition, wake_inrush_factor should create a current spike."""
    ch = _make_ch_kl15(wake_inrush_factor=3.0, wake_inrush_duration_ms=200.0)
    cfg = make_config(
        duration_s=30.0,
        sample_interval_ms=100.0,
        channels=[ch],
        fault_injections=[],
        power_state_events=[
            PowerStateEvent(time_s=0.0, state=PowerState.SLEEP),
            PowerStateEvent(time_s=10.0, state=PowerState.ACTIVE),
        ],
    )
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()
    wake_time = df["timestamp"].iloc[0] + pd.Timedelta(seconds=10)
    post_wake = df[
        (df["timestamp"] >= wake_time)
        & (df["timestamp"] <= wake_time + pd.Timedelta(milliseconds=300))
    ]
    assert post_wake["current_a"].max() > ch.nominal_current_a * 1.5, (
        "Wake inrush should produce a current spike above 1.5x nominal"
    )
    settled = df[df["timestamp"] > wake_time + pd.Timedelta(milliseconds=500)]
    assert settled["current_a"].mean() < ch.nominal_current_a * 1.5, (
        "Current should settle to near nominal after inrush ends (1.5x accounts for ISENSE gain)"
    )


def test_start_channel_only_active_during_crank():
    """KL50 START channel should only carry current during CRANK state."""
    ch = ChannelMeta(
        channel_id="ch_start",
        load_name="starter_relay",
        nominal_current_a=2.0,
        max_current_a=10.0,
        fuse_rating_a=8.0,
        thermal_shutdown_c=150.0,
        r_thermal_kw=20.0,
        tau_thermal_s=10.0,
        t_ambient_c=25.0,
        rds_on_tempco_exp=0.0,
        power_class=PowerClass.START,
    )
    cfg = make_config(
        duration_s=20.0,
        sample_interval_ms=100.0,
        channels=[ch],
        fault_injections=[],
        power_state_events=[
            PowerStateEvent(time_s=0.0, state=PowerState.ACTIVE),
            PowerStateEvent(time_s=5.0, state=PowerState.CRANK),
            PowerStateEvent(time_s=10.0, state=PowerState.ACTIVE),
        ],
    )
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()
    t0 = df["timestamp"].iloc[0]
    pre_crank = df[df["timestamp"] < t0 + pd.Timedelta(seconds=4.9)]
    crank = df[
        (df["timestamp"] >= t0 + pd.Timedelta(seconds=5.1))
        & (df["timestamp"] <= t0 + pd.Timedelta(seconds=9.9))
    ]
    post_crank = df[df["timestamp"] > t0 + pd.Timedelta(seconds=10.1)]
    assert pre_crank["current_a"].abs().max() < 0.005, "START channel off before crank"
    assert crank["current_a"].mean() > ch.nominal_current_a * 0.5, "START channel on during crank"
    assert post_crank["current_a"].abs().max() < 0.005, "START channel off after crank"


def test_power_state_events_in_config():
    """SimulationConfig should accept power_state_events and they should be accessible."""
    from efuse_datagen.config.models import SimulationConfig

    cfg = SimulationConfig(
        scenario_id="ps_test",
        name="Power State Test",
        duration_s=30.0,
        sample_interval_ms=100.0,
        seed=1,
        channels=[_make_ch_kl15()],
        power_state_events=[
            PowerStateEvent(time_s=0.0, state=PowerState.SLEEP),
            PowerStateEvent(time_s=15.0, state=PowerState.ACTIVE),
        ],
    )
    assert len(cfg.power_state_events) == 2
    assert cfg.power_state_events[0].state == PowerState.SLEEP
    assert cfg.power_state_events[1].state == PowerState.ACTIVE
    assert cfg.power_state_events[1].time_s == 15.0
