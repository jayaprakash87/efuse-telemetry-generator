"""Basic generation tests: nominal, faults, reproducibility, multi-channel."""

import pandas as pd

from efuse_datagen.schemas.telemetry import ChannelMeta, FaultInjection, FaultType
from efuse_datagen.simulation.generator import TelemetryGenerator
from tests.conftest import make_config


def test_generate_nominal():
    cfg = make_config()
    gen = TelemetryGenerator(cfg)
    telem_df, labels_df = gen.generate()
    assert len(telem_df) == 100  # 10s / 0.1s
    assert "current_a" in telem_df.columns
    assert len(labels_df) == 0  # no faults


def test_generate_with_fault():
    cfg = make_config(
        fault_injections=[
            FaultInjection(
                channel_id="ch_01",
                fault_type=FaultType.OVERLOAD_SPIKE,
                start_s=2.0,
                duration_s=2.0,
                intensity=0.8,
            )
        ]
    )
    gen = TelemetryGenerator(cfg)
    telem_df, labels_df = gen.generate()
    assert len(labels_df) > 0
    assert labels_df["fault_type"].iloc[0] == FaultType.OVERLOAD_SPIKE.value


def test_reproducible_with_seed():
    cfg = make_config(seed=99)
    gen1 = TelemetryGenerator(cfg)
    gen2 = TelemetryGenerator(cfg)
    df1, _ = gen1.generate()
    df2, _ = gen2.generate()
    # Timestamps differ because they use datetime.now(); compare signal columns only
    cols = [c for c in df1.columns if c != "timestamp"]
    pd.testing.assert_frame_equal(df1[cols], df2[cols])


def test_multiple_channels():
    cfg = make_config(
        channels=[
            ChannelMeta(channel_id="ch_01", load_name="a", nominal_current_a=5.0),
            ChannelMeta(channel_id="ch_02", load_name="b", nominal_current_a=10.0),
        ]
    )
    gen = TelemetryGenerator(cfg)
    telem_df, _ = gen.generate()
    assert set(telem_df["channel_id"].unique()) == {"ch_01", "ch_02"}
    assert len(telem_df) == 200  # 100 per channel
