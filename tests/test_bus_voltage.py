"""Bus voltage event tests: jump start, load dump, cold crank."""

import pandas as pd

from efuse_datagen.schemas.telemetry import (
    ChannelMeta,
    FaultInjection,
    FaultType,
    ProtectionEvent,
)
from efuse_datagen.simulation.generator import TelemetryGenerator
from tests.conftest import make_config


def _make_ch_bus(rds_on_tempco_exp: float = 0.0) -> ChannelMeta:
    """Minimal ChannelMeta for bus-voltage scenario tests (tempco off for simplicity)."""
    return ChannelMeta(
        channel_id="ch_bus",
        load_name="seat_heater",
        nominal_current_a=8.0,
        max_current_a=30.0,
        fuse_rating_a=20.0,
        thermal_shutdown_c=150.0,
        r_thermal_kw=20.0,
        tau_thermal_s=10.0,
        t_ambient_c=25.0,
        rds_on_tempco_exp=rds_on_tempco_exp,
    )


def test_jump_start_elevates_bus_voltage():
    """JUMP_START fault — bus voltage should rise above 16 V and current increases."""
    ch = _make_ch_bus()
    cfg = make_config(
        duration_s=20.0,
        sample_interval_ms=100.0,
        channels=[ch],
        fault_injections=[
            FaultInjection(
                channel_id="ch_bus",
                fault_type=FaultType.JUMP_START,
                start_s=5.0,
                duration_s=10.0,
                intensity=0.8,
            ),
        ],
    )
    gen = TelemetryGenerator(cfg)
    df, labels = gen.generate()
    fault_rows = df[
        df["timestamp"].between(
            df["timestamp"].iloc[0] + pd.Timedelta(seconds=6),
            df["timestamp"].iloc[0] + pd.Timedelta(seconds=14),
        )
    ]
    assert fault_rows["voltage_v"].max() > 16.0, "Jump-start should push bus above 16 V"
    ov_rows = fault_rows[fault_rows["protection_event"] == ProtectionEvent.OVER_VOLTAGE.value]
    assert len(ov_rows) > 0, "OVER_VOLTAGE protection event should be set during jump-start"
    assert labels["fault_type"].iloc[0] == FaultType.JUMP_START.value


def test_jump_start_current_scales_with_voltage():
    """During jump-start, resistive-load current should be higher than nominal."""
    ch = _make_ch_bus()
    cfg_nominal = make_config(duration_s=10.0, channels=[ch], fault_injections=[])
    cfg_jump = make_config(
        duration_s=10.0,
        channels=[ch],
        fault_injections=[
            FaultInjection(
                channel_id="ch_bus",
                fault_type=FaultType.JUMP_START,
                start_s=0.0,
                duration_s=10.0,
                intensity=0.9,
            ),
        ],
    )
    gen_n = TelemetryGenerator(cfg_nominal)
    gen_j = TelemetryGenerator(cfg_jump)
    df_n, _ = gen_n.generate()
    df_j, _ = gen_j.generate()
    # Median current should be higher during jump-start
    med_jump = df_j["current_a"].median()
    med_nom = df_n["current_a"].median()
    assert med_jump > med_nom * 1.05, "Current should be elevated during jump-start"


def test_load_dump_spikes_and_shuts_off():
    """LOAD_DUMP fault — brief voltage spike to ~40 V, IC shuts gate off."""
    ch = _make_ch_bus()
    cfg = make_config(
        duration_s=10.0,
        sample_interval_ms=50.0,
        channels=[ch],
        fault_injections=[
            FaultInjection(
                channel_id="ch_bus",
                fault_type=FaultType.LOAD_DUMP,
                start_s=3.0,
                duration_s=2.0,
                intensity=1.0,
            ),
        ],
    )
    gen = TelemetryGenerator(cfg)
    df, labels = gen.generate()
    fault_rows = df[
        df["timestamp"].between(
            df["timestamp"].iloc[0] + pd.Timedelta(seconds=3),
            df["timestamp"].iloc[0] + pd.Timedelta(seconds=5),
        )
    ]
    # Bus should spike above 30 V
    assert fault_rows["voltage_v"].max() > 30.0, "Load dump should produce > 30 V spike"
    # Trip flag should be set (IC over-voltage protection fires)
    assert fault_rows["trip_flag"].any(), "Load dump should trigger eFuse trip"
    # Protection event
    assert (fault_rows["protection_event"] == ProtectionEvent.OVER_VOLTAGE.value).any()
    assert labels["fault_type"].iloc[0] == FaultType.LOAD_DUMP.value


def test_cold_crank_sags_bus_voltage():
    """COLD_CRANK fault — bus sags to < 9 V and current drops proportionally."""
    ch = _make_ch_bus()
    cfg = make_config(
        duration_s=20.0,
        sample_interval_ms=100.0,
        channels=[ch],
        fault_injections=[
            FaultInjection(
                channel_id="ch_bus",
                fault_type=FaultType.COLD_CRANK,
                start_s=5.0,
                duration_s=8.0,
                intensity=0.9,
            ),
        ],
    )
    gen = TelemetryGenerator(cfg)
    df, labels = gen.generate()
    fault_rows = df[
        df["timestamp"].between(
            df["timestamp"].iloc[0] + pd.Timedelta(seconds=6),
            df["timestamp"].iloc[0] + pd.Timedelta(seconds=12),
        )
    ]
    min_v = fault_rows["voltage_v"].min()
    assert min_v < 9.0, f"Cold-crank should sag bus below 9 V, got {min_v:.2f} V"
    # Current should also be reduced from nominal
    assert fault_rows["current_a"].median() < ch.nominal_current_a, (
        "Current should be reduced during cold crank"
    )
    assert labels["fault_type"].iloc[0] == FaultType.COLD_CRANK.value


def test_cold_crank_recovers_after_window():
    """After the cold-crank window bus voltage should recover to ~13.5 V."""
    ch = _make_ch_bus()
    cfg = make_config(
        duration_s=30.0,
        sample_interval_ms=100.0,
        channels=[ch],
        fault_injections=[
            FaultInjection(
                channel_id="ch_bus",
                fault_type=FaultType.COLD_CRANK,
                start_s=5.0,
                duration_s=8.0,
                intensity=0.9,
            ),
        ],
    )
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()
    post_crank = df[df["timestamp"] > df["timestamp"].iloc[0] + pd.Timedelta(seconds=14)]
    assert post_crank["voltage_v"].mean() > 12.0, (
        "Bus voltage should recover above 12 V after cold-crank ends"
    )
