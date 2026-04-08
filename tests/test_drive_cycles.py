"""Tests for efuse_datagen.simulation.drive_cycles – DriveCyclePlanner & generate_multi_cycle."""

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from efuse_datagen.config.models import DriveCycleConfig, SimulationConfig
from efuse_datagen.schemas.telemetry import ChannelMeta, PowerClass
from efuse_datagen.simulation.drive_cycles import (
    DriveCycleEvent,
    DriveCyclePlanner,
    generate_multi_cycle,
)


BASE_TIME = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)


def _planner(seed: int = 42, **overrides) -> DriveCyclePlanner:
    defaults = dict(
        enabled=True,
        total_days=7,
        profile="mixed",
        mean_trips_per_day=2.0,
        max_trips_per_day=4,
        no_drive_day_probability=0.0,
    )
    defaults.update(overrides)
    cfg = DriveCycleConfig(**defaults)
    return DriveCyclePlanner(cfg, seed=seed)


class TestScheduleGeneration:
    def test_generates_cycles(self):
        planner = _planner()
        cycles = planner.generate_schedule(BASE_TIME)
        assert len(cycles) > 0

    def test_cycle_ids_unique(self):
        planner = _planner()
        cycles = planner.generate_schedule(BASE_TIME)
        ids = [c.cycle_id for c in cycles]
        assert len(ids) == len(set(ids))

    def test_cycles_chronological(self):
        planner = _planner()
        cycles = planner.generate_schedule(BASE_TIME)
        starts = [c.start_time for c in cycles]
        assert starts == sorted(starts)

    def test_duration_within_bounds(self):
        planner = _planner(min_trip_minutes=5.0, max_trip_minutes=240.0)
        cycles = planner.generate_schedule(BASE_TIME)
        for c in cycles:
            # duration_s includes pre-sleep, crank, post-settle overhead
            overhead = planner.PRE_SLEEP_S + planner.CRANK_S + planner.POST_SETTLE_S
            active_s = c.duration_s - overhead
            assert active_s >= 5.0 * 60 - 1  # min_trip_minutes in seconds (tolerance)
            assert active_s <= 240.0 * 60 + 1

    def test_no_overlapping_cycles(self):
        planner = _planner(mean_trips_per_day=4.0)
        cycles = planner.generate_schedule(BASE_TIME)
        for i in range(len(cycles) - 1):
            assert cycles[i].end_time <= cycles[i + 1].start_time

    def test_end_time_property(self):
        planner = _planner()
        cycles = planner.generate_schedule(BASE_TIME)
        for c in cycles:
            assert c.end_time == c.start_time + pd.Timedelta(seconds=c.duration_s)


class TestReproducibility:
    def test_same_seed_same_schedule(self):
        c1 = _planner(seed=99).generate_schedule(BASE_TIME)
        c2 = _planner(seed=99).generate_schedule(BASE_TIME)
        assert len(c1) == len(c2)
        for a, b in zip(c1, c2):
            assert a.cycle_id == b.cycle_id
            assert a.start_time == b.start_time
            assert a.duration_s == b.duration_s

    def test_different_seed_different_schedule(self):
        c1 = _planner(seed=1).generate_schedule(BASE_TIME)
        c2 = _planner(seed=2).generate_schedule(BASE_TIME)
        # With different seeds, schedules should differ (not guaranteed, but extremely likely)
        durations1 = [c.duration_s for c in c1]
        durations2 = [c.duration_s for c in c2]
        assert durations1 != durations2 or len(c1) != len(c2)


class TestFaultDistribution:
    def test_distribute_faults_returns_dict(self):
        planner = _planner()
        cycles = planner.generate_schedule(BASE_TIME)
        ch = ChannelMeta(
            channel_id="ch_01",
            load_name="headlamp",
            nominal_current_a=6.0,
            power_class=PowerClass.IGNITION,
        )
        faults = planner.distribute_faults(cycles, [ch])
        assert isinstance(faults, dict)
        assert set(faults.keys()) == {c.cycle_id for c in cycles}

    def test_fault_channel_ids_valid(self):
        planner = _planner()
        cycles = planner.generate_schedule(BASE_TIME)
        ch = ChannelMeta(
            channel_id="ch_01",
            load_name="headlamp",
            nominal_current_a=6.0,
            power_class=PowerClass.IGNITION,
        )
        faults = planner.distribute_faults(cycles, [ch])
        for cycle_faults in faults.values():
            for f in cycle_faults:
                assert f.channel_id == "ch_01"


class TestBuildPowerEvents:
    def test_power_event_sequence(self):
        cycle = DriveCycleEvent(
            cycle_id=0,
            day=0,
            start_time=BASE_TIME,
            duration_s=600.0,
            ambient_temp_c=22.0,
            drive_type="commute",
        )
        events = DriveCyclePlanner.build_power_events(cycle)
        assert len(events) == 4
        states = [e.state for e in events]
        assert states == ["sleep", "crank", "active", "sleep"]

    def test_power_event_timing(self):
        cycle = DriveCycleEvent(
            cycle_id=0, day=0, start_time=BASE_TIME,
            duration_s=600.0, ambient_temp_c=22.0, drive_type="commute",
        )
        events = DriveCyclePlanner.build_power_events(cycle)
        assert events[0].time_s == 0.0
        assert events[1].time_s == DriveCyclePlanner.PRE_SLEEP_S
        assert events[2].time_s == DriveCyclePlanner.PRE_SLEEP_S + DriveCyclePlanner.CRANK_S
        assert events[3].time_s == 600.0 - DriveCyclePlanner.POST_SETTLE_S


class TestTemperatureTrajectory:
    def test_trajectory_length_matches_days(self):
        planner = _planner(total_days=14)
        temps = planner._temp_trajectory()
        assert len(temps) == 14

    def test_trajectory_starts_at_mean(self):
        planner = _planner(ambient_temp_mean_c=25.0)
        temps = planner._temp_trajectory()
        assert temps[0] == 25.0


class TestMultiCycleGeneration:
    def test_generate_multi_cycle_produces_data(self):
        planner = _planner(total_days=3)
        cycles = planner.generate_schedule(BASE_TIME)
        ch = ChannelMeta(
            channel_id="ch_01",
            load_name="lamp",
            nominal_current_a=5.0,
            power_class=PowerClass.IGNITION,
        )
        sim_cfg = SimulationConfig(
            scenario_id="mc_test",
            duration_s=60.0,
            sample_interval_ms=100.0,
            seed=42,
            channels=[ch],
        )
        faults = planner.distribute_faults(cycles, [ch])
        telem, labels = generate_multi_cycle(sim_cfg, cycles, faults)
        assert not telem.empty
        assert "drive_cycle_id" in telem.columns
        # Should have data for multiple cycles
        assert telem["drive_cycle_id"].nunique() >= 2

    def test_multi_cycle_reproducible(self):
        planner = _planner(total_days=2, seed=77)
        cycles = planner.generate_schedule(BASE_TIME)
        ch = ChannelMeta(
            channel_id="ch_01", load_name="lamp", nominal_current_a=5.0,
            power_class=PowerClass.IGNITION,
        )
        sim_cfg = SimulationConfig(
            scenario_id="mc_repro", duration_s=60.0,
            sample_interval_ms=200.0, seed=77, channels=[ch],
        )
        faults = planner.distribute_faults(cycles, [ch])
        t1, _ = generate_multi_cycle(sim_cfg, cycles, faults)

        planner2 = _planner(total_days=2, seed=77)
        cycles2 = planner2.generate_schedule(BASE_TIME)
        faults2 = planner2.distribute_faults(cycles2, [ch])
        t2, _ = generate_multi_cycle(sim_cfg, cycles2, faults2)

        assert len(t1) == len(t2)
        np.testing.assert_array_almost_equal(
            t1["current_a"].values, t2["current_a"].values, decimal=6
        )
