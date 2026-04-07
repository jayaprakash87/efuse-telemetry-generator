"""Wire harness resistance and connector aging tests."""

import pandas as pd

from efuse_datagen.config.models import SimulationConfig
from efuse_datagen.schemas.telemetry import ChannelMeta, FaultInjection, FaultType
from efuse_datagen.simulation.generator import TelemetryGenerator
from tests.conftest import make_config


def _make_ch_harness(
    harness_r_ohm: float = 0.020,
    connector_r_ohm: float = 0.010,
    rds_on_tempco_exp: float = 0.0,
) -> ChannelMeta:
    return ChannelMeta(
        channel_id="ch_harness",
        load_name="fog_light",
        nominal_current_a=6.0,
        max_current_a=20.0,
        fuse_rating_a=15.0,
        thermal_shutdown_c=150.0,
        r_thermal_kw=20.0,
        tau_thermal_s=10.0,
        t_ambient_c=25.0,
        harness_r_ohm=harness_r_ohm,
        connector_r_ohm=connector_r_ohm,
        rds_on_tempco_exp=rds_on_tempco_exp,
    )


def test_harness_r_raises_voltage_drop():
    """Higher harness resistance should produce a lower measured voltage."""
    ch_low = _make_ch_harness(harness_r_ohm=0.010, connector_r_ohm=0.005)
    ch_high = _make_ch_harness(harness_r_ohm=0.100, connector_r_ohm=0.050)

    def _gen(ch):
        cfg = SimulationConfig(
            scenario_id="test",
            name="T",
            duration_s=10.0,
            sample_interval_ms=100.0,
            seed=42,
            channels=[ch],
            fault_injections=[],
        )
        return TelemetryGenerator(cfg).generate()[0]

    df_low = _gen(ch_low)
    df_high = _gen(ch_high)
    assert df_high["voltage_v"].mean() < df_low["voltage_v"].mean(), (
        "Higher harness R should yield lower measured voltage"
    )


def test_connector_aging_drops_voltage_over_time():
    """CONNECTOR_AGING fault — voltage should fall progressively during the fault window."""
    ch = _make_ch_harness()
    cfg = make_config(
        duration_s=60.0,
        sample_interval_ms=200.0,
        channels=[ch],
        fault_injections=[
            FaultInjection(
                channel_id="ch_harness",
                fault_type=FaultType.CONNECTOR_AGING,
                start_s=10.0,
                duration_s=40.0,
                intensity=0.9,
            ),
        ],
    )
    gen = TelemetryGenerator(cfg)
    df, labels = gen.generate()
    fault_rows = df[
        (df["timestamp"] >= df["timestamp"].iloc[0] + pd.Timedelta(seconds=10))
        & (df["timestamp"] <= df["timestamp"].iloc[0] + pd.Timedelta(seconds=50))
    ].copy()
    # Voltage should trend downward through the fault window
    first_quarter = fault_rows.iloc[: len(fault_rows) // 4]["voltage_v"].mean()
    last_quarter = fault_rows.iloc[-len(fault_rows) // 4 :]["voltage_v"].mean()
    assert last_quarter < first_quarter, (
        f"Voltage should fall during connector aging fault: "
        f"first_q={first_quarter:.3f} V, last_q={last_quarter:.3f} V"
    )
    assert labels["fault_type"].iloc[0] == FaultType.CONNECTOR_AGING.value


def test_connector_aging_current_reduction():
    """Current should be slightly reduced at end of window vs start (resistive load, lower V)."""
    ch = _make_ch_harness()
    cfg = make_config(
        duration_s=60.0,
        sample_interval_ms=200.0,
        channels=[ch],
        fault_injections=[
            FaultInjection(
                channel_id="ch_harness",
                fault_type=FaultType.CONNECTOR_AGING,
                start_s=5.0,
                duration_s=50.0,
                intensity=1.0,
            ),
        ],
    )
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()
    fault_rows = df[df["timestamp"] >= df["timestamp"].iloc[0] + pd.Timedelta(seconds=5)]
    first_mean = fault_rows.iloc[:10]["current_a"].mean()
    last_mean = fault_rows.iloc[-10:]["current_a"].mean()
    assert last_mean <= first_mean * 1.05, (
        "Current should not increase with rising connector resistance"
    )


def test_connector_aging_no_trip():
    """Connector aging is a slow degradation — eFuse should not trip."""
    ch = _make_ch_harness()
    cfg = make_config(
        duration_s=30.0,
        sample_interval_ms=100.0,
        channels=[ch],
        fault_injections=[
            FaultInjection(
                channel_id="ch_harness",
                fault_type=FaultType.CONNECTOR_AGING,
                start_s=0.0,
                duration_s=30.0,
                intensity=0.8,
            ),
        ],
    )
    gen = TelemetryGenerator(cfg)
    df, _ = gen.generate()
    assert not df["trip_flag"].any(), "Connector aging should not trigger eFuse trip"
