"""Multi-channel die thermal coupling tests."""

import pandas as pd

from efuse_datagen.schemas.telemetry import ChannelMeta
from efuse_datagen.simulation.generator import TelemetryGenerator
from tests.conftest import make_config


def _make_die_channels(
    die_id: str = "die_A",
    coupling: float = 0.20,
) -> list[ChannelMeta]:
    """Two channels sharing a die: ch_hot (high current) and ch_cold (low current)."""
    common = dict(
        max_current_a=20.0,
        fuse_rating_a=15.0,
        thermal_shutdown_c=150.0,
        r_thermal_kw=30.0,
        tau_thermal_s=5.0,
        t_ambient_c=25.0,
        rds_on_tempco_exp=0.0,
        die_id=die_id,
        thermal_coupling_coeff=coupling,
    )
    ch_hot = ChannelMeta(
        channel_id="ch_hot",
        load_name="seat_heater",
        nominal_current_a=12.0,
        r_ds_on_ohm=0.006,
        **common,
    )
    ch_cold = ChannelMeta(
        channel_id="ch_cold",
        load_name="mirror_adjust",
        nominal_current_a=1.5,
        r_ds_on_ohm=0.010,
        **common,
    )
    return [ch_hot, ch_cold]


def _make_isolated_cold() -> ChannelMeta:
    return ChannelMeta(
        channel_id="ch_cold",
        load_name="mirror_adjust",
        nominal_current_a=1.5,
        r_ds_on_ohm=0.010,
        max_current_a=20.0,
        fuse_rating_a=15.0,
        thermal_shutdown_c=150.0,
        r_thermal_kw=30.0,
        tau_thermal_s=5.0,
        t_ambient_c=25.0,
        rds_on_tempco_exp=0.0,
        die_id="",  # isolated
    )


def test_coupled_channel_runs_hotter_than_isolated():
    """ch_cold on shared die should be hotter than an isolated ch_cold with same current."""
    ch_coupled, ch_cold_coupled = _make_die_channels()
    ch_isolated = _make_isolated_cold()

    cfg_coupled = make_config(
        duration_s=30.0,
        sample_interval_ms=100.0,
        channels=[ch_coupled, ch_cold_coupled],
        fault_injections=[],
    )
    cfg_isolated = make_config(
        duration_s=30.0,
        sample_interval_ms=100.0,
        channels=[ch_isolated],
        fault_injections=[],
    )
    gen_c = TelemetryGenerator(cfg_coupled)
    gen_i = TelemetryGenerator(cfg_isolated)
    df_c, _ = gen_c.generate()
    df_i, _ = gen_i.generate()

    # Steady-state temperature (last 10 s) for ch_cold in each scenario
    t0_c = df_c["timestamp"].min()
    t0_i = df_i["timestamp"].min()
    cold_coupled_temp = df_c[
        (df_c["channel_id"] == "ch_cold") & (df_c["timestamp"] > t0_c + pd.Timedelta(seconds=20))
    ]["temperature_c"].mean()
    cold_isolated_temp = df_i[df_i["timestamp"] > t0_i + pd.Timedelta(seconds=20)][
        "temperature_c"
    ].mean()

    assert cold_coupled_temp > cold_isolated_temp, (
        f"Coupled channel ({cold_coupled_temp:.2f}°C) should be hotter than "
        f"isolated ({cold_isolated_temp:.2f}°C)"
    )


def test_hot_channel_does_not_affect_temperature_with_zero_coupling():
    """With thermal_coupling_coeff=0, co-die channel should not receive any extra heat."""
    channels = _make_die_channels(coupling=0.0)
    ch_isolated = _make_isolated_cold()

    cfg_zero = make_config(
        duration_s=20.0, sample_interval_ms=100.0, channels=channels, fault_injections=[]
    )
    cfg_iso = make_config(
        duration_s=20.0, sample_interval_ms=100.0, channels=[ch_isolated], fault_injections=[]
    )

    df_zero, _ = TelemetryGenerator(cfg_zero).generate()
    df_iso, _ = TelemetryGenerator(cfg_iso).generate()

    t0_z = df_zero["timestamp"].min()
    t0_i = df_iso["timestamp"].min()
    temp_zero = df_zero[
        (df_zero["channel_id"] == "ch_cold")
        & (df_zero["timestamp"] > t0_z + pd.Timedelta(seconds=15))
    ]["temperature_c"].mean()
    temp_iso = df_iso[df_iso["timestamp"] > t0_i + pd.Timedelta(seconds=15)]["temperature_c"].mean()

    assert abs(temp_zero - temp_iso) < 1.0, (
        f"Zero coupling should produce same temp as isolated: "
        f"zero_coupling={temp_zero:.2f}°C, isolated={temp_iso:.2f}°C"
    )


def test_isolated_channels_not_affected_by_coupling():
    """Channels with different die_ids should not thermally interact."""
    ch_a = ChannelMeta(
        channel_id="ch_a",
        load_name="load_a",
        nominal_current_a=12.0,
        r_ds_on_ohm=0.006,
        max_current_a=20.0,
        fuse_rating_a=15.0,
        thermal_shutdown_c=150.0,
        r_thermal_kw=30.0,
        tau_thermal_s=5.0,
        t_ambient_c=25.0,
        rds_on_tempco_exp=0.0,
        die_id="die_X",
    )
    ch_b = ChannelMeta(
        channel_id="ch_b",
        load_name="load_b",
        nominal_current_a=1.5,
        r_ds_on_ohm=0.010,
        max_current_a=20.0,
        fuse_rating_a=15.0,
        thermal_shutdown_c=150.0,
        r_thermal_kw=30.0,
        tau_thermal_s=5.0,
        t_ambient_c=25.0,
        rds_on_tempco_exp=0.0,
        die_id="die_Y",  # different die
    )
    ch_b_iso = ChannelMeta(
        channel_id="ch_b",
        load_name="load_b",
        nominal_current_a=1.5,
        r_ds_on_ohm=0.010,
        max_current_a=20.0,
        fuse_rating_a=15.0,
        thermal_shutdown_c=150.0,
        r_thermal_kw=30.0,
        tau_thermal_s=5.0,
        t_ambient_c=25.0,
        rds_on_tempco_exp=0.0,
        die_id="",
    )

    df_diff, _ = TelemetryGenerator(
        make_config(
            duration_s=20.0,
            sample_interval_ms=100.0,
            channels=[ch_a, ch_b],
            fault_injections=[],
        )
    ).generate()
    df_iso, _ = TelemetryGenerator(
        make_config(
            duration_s=20.0,
            sample_interval_ms=100.0,
            channels=[ch_b_iso],
            fault_injections=[],
        )
    ).generate()

    t0_d = df_diff["timestamp"].min()
    t0_i = df_iso["timestamp"].min()
    temp_diff = df_diff[
        (df_diff["channel_id"] == "ch_b") & (df_diff["timestamp"] > t0_d + pd.Timedelta(seconds=15))
    ]["temperature_c"].mean()
    temp_iso = df_iso[df_iso["timestamp"] > t0_i + pd.Timedelta(seconds=15)]["temperature_c"].mean()

    assert abs(temp_diff - temp_iso) < 1.0, "Different-die channels should not thermally interact"
