"""Drive-cycle planning and multi-cycle orchestration.

Generates a calendar of ignition cycles (SLEEP → CRANK → ACTIVE → SLEEP)
spread over N days with:
    - variable trips per day (Poisson-distributed, profile-dependent)
    - log-normal trip durations (short errands to long highway drives)
    - mean-reverting ambient temperature trajectory with per-trip diurnal variation
    - stochastic fault injection (Poisson rate per vehicle-hour)
    - progressive wear for connector aging and gradual degradation
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from efuse_datagen.config.models import DriveCycleConfig, SimulationConfig
from efuse_datagen.schemas.telemetry import (
    ChannelMeta,
    FaultInjection,
    FaultType,
    PowerClass,
)
from efuse_datagen.utils.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class DriveCycleEvent:
    """One ignition cycle: SLEEP → CRANK → ACTIVE → SLEEP."""

    cycle_id: int
    day: int
    start_time: datetime
    duration_s: float
    ambient_temp_c: float
    drive_type: str  # commute | errand | highway

    @property
    def end_time(self) -> datetime:
        return self.start_time + timedelta(seconds=self.duration_s)


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


class DriveCyclePlanner:
    """Generate a realistic multi-day schedule of drive cycles."""

    # Per-cycle power-state overhead (seconds)
    PRE_SLEEP_S = 2.0  # Pre-drive sleep window before crank
    CRANK_S = 3.0  # Starter engaged
    POST_SETTLE_S = 5.0  # Post-drive settle before returning to sleep

    # Fault duration bounds per type (seconds)
    FAULT_DURATION: dict[FaultType, tuple[float, float]] = {
        FaultType.OVERLOAD_SPIKE: (1.0, 5.0),
        FaultType.INTERMITTENT_OVERLOAD: (10.0, 60.0),
        FaultType.VOLTAGE_SAG: (2.0, 15.0),
        FaultType.THERMAL_DRIFT: (30.0, 180.0),
        FaultType.NOISY_SENSOR: (10.0, 60.0),
        FaultType.CONNECTOR_AGING: (60.0, 300.0),
        FaultType.OPEN_LOAD: (30.0, 120.0),
        FaultType.GRADUAL_DEGRADATION: (60.0, 300.0),
        FaultType.COLD_CRANK: (3.0, 8.0),
        FaultType.JUMP_START: (2.0, 10.0),
        FaultType.LOAD_DUMP: (0.3, 2.0),
        FaultType.THERMAL_COUPLING: (20.0, 90.0),
        FaultType.WAKE_TRANSIENT: (1.0, 5.0),
    }

    def __init__(self, config: DriveCycleConfig, seed: int = 42) -> None:
        self.cfg = config
        self.rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_schedule(self, base_time: datetime) -> list[DriveCycleEvent]:
        """Return a chronological list of drive cycles across *total_days*."""
        cycles: list[DriveCycleEvent] = []
        cycle_id = 0
        daily_temps = self._temp_trajectory()

        for day in range(self.cfg.total_days):
            day_start = base_time + timedelta(days=day)

            if self.rng.random() < self.cfg.no_drive_day_probability:
                continue

            n_trips = self._trips_for_day(day)
            if n_trips == 0:
                continue

            trips = self._day_trips(n_trips, day_start, daily_temps[day])
            for trip in trips:
                trip.cycle_id = cycle_id
                trip.day = day
                cycles.append(trip)
                cycle_id += 1

        log.info(
            "Planned %d drive cycles over %d days (%.1f h total driving)",
            len(cycles),
            self.cfg.total_days,
            sum(c.duration_s for c in cycles) / 3600,
        )
        return cycles

    def distribute_faults(
        self,
        cycles: list[DriveCycleEvent],
        channels: list[ChannelMeta],
    ) -> dict[int, list[FaultInjection]]:
        """Stochastically assign faults to channels across all cycles.

        Returns ``{cycle_id: [FaultInjection, ...]}``.
        """
        faults: dict[int, list[FaultInjection]] = {c.cycle_id: [] for c in cycles}
        acc_hours = 0.0
        rates = self._fault_rate_dict()

        for cycle in cycles:
            cycle_h = cycle.duration_s / 3600
            active_start = self.PRE_SLEEP_S + self.CRANK_S
            active_end = cycle.duration_s - self.POST_SETTLE_S
            active_dur = active_end - active_start

            if active_dur <= 10:
                acc_hours += cycle_h
                continue

            for ft, rate in rates.items():
                # Environmental gate: cold_crank only below 5 °C
                if ft == FaultType.COLD_CRANK and cycle.ambient_temp_c > 5.0:
                    continue

                effective_rate = rate
                # Progressive wear: connector aging / degradation worsen over time
                if ft in (FaultType.CONNECTOR_AGING, FaultType.GRADUAL_DEGRADATION):
                    effective_rate *= 1 + min(acc_hours / 200, 3.0)

                n_events = int(self.rng.poisson(effective_rate * cycle_h))
                for _ in range(min(n_events, 3)):  # cap per-type per cycle
                    eligible = self._eligible(channels, ft)
                    if not eligible:
                        continue
                    ch = eligible[int(self.rng.integers(len(eligible)))]

                    dur_lo, dur_hi = self.FAULT_DURATION.get(ft, (5.0, 30.0))
                    dur = float(self.rng.uniform(dur_lo, min(dur_hi, active_dur * 0.8)))

                    # Place fault in the active window
                    if ft == FaultType.WAKE_TRANSIENT:
                        start = active_start + float(self.rng.uniform(0, min(5, active_dur - dur)))
                    elif ft == FaultType.COLD_CRANK:
                        start = self.PRE_SLEEP_S  # during crank phase
                    else:
                        max_start = max(active_start, active_end - dur)
                        start = float(self.rng.uniform(active_start, max_start))

                    # Intensity: base random + progressive component
                    base_int = float(self.rng.uniform(0.3, 0.9))
                    if ft in (FaultType.CONNECTOR_AGING, FaultType.GRADUAL_DEGRADATION):
                        base_int = min(base_int + min(acc_hours / 500, 0.3), 1.0)

                    faults[cycle.cycle_id].append(
                        FaultInjection(
                            channel_id=ch.channel_id,
                            fault_type=ft,
                            start_s=round(start, 1),
                            duration_s=round(dur, 1),
                            intensity=round(base_int, 2),
                        )
                    )

            acc_hours += cycle_h

        total = sum(len(v) for v in faults.values())
        log.info("Distributed %d fault injections across %d cycles", total, len(cycles))
        return faults

    @staticmethod
    def build_power_events(cycle: DriveCycleEvent) -> list:
        """Return power-state events for a single ignition cycle."""
        from efuse_datagen.config.models import PowerStateEvent

        return [
            PowerStateEvent(time_s=0.0, state="sleep"),
            PowerStateEvent(time_s=DriveCyclePlanner.PRE_SLEEP_S, state="crank"),
            PowerStateEvent(
                time_s=DriveCyclePlanner.PRE_SLEEP_S + DriveCyclePlanner.CRANK_S,
                state="active",
            ),
            PowerStateEvent(
                time_s=cycle.duration_s - DriveCyclePlanner.POST_SETTLE_S,
                state="sleep",
            ),
        ]

    # ------------------------------------------------------------------
    # Internals — schedule generation
    # ------------------------------------------------------------------

    def _trips_for_day(self, day: int) -> int:
        weekday = day % 7  # 0 = Mon, 6 = Sun
        profile = self.cfg.profile

        if profile == "commuter":
            if weekday < 5:  # Mon–Fri
                base = 2 + int(self.rng.random() < 0.3)
            else:
                base = int(self.rng.choice([0, 1, 2], p=[0.2, 0.5, 0.3]))
        elif profile == "heavy":
            if weekday < 6:  # Mon–Sat
                base = int(self.rng.poisson(5))
            else:
                base = int(self.rng.choice([0, 1], p=[0.4, 0.6]))
        else:  # mixed
            base = int(self.rng.poisson(self.cfg.mean_trips_per_day))

        return max(0, min(base, self.cfg.max_trips_per_day))

    def _day_trips(
        self, n: int, day_start: datetime, temp_base: float
    ) -> list[DriveCycleEvent]:
        slots = sorted(self._time_slots(n))
        trips: list[DriveCycleEvent] = []

        for hour in slots:
            minute = int(self.rng.uniform(0, 50))
            trip_start = day_start + timedelta(hours=hour, minutes=minute)

            # Log-normal trip duration (minutes)
            raw_min = float(
                self.rng.lognormal(np.log(self.cfg.median_trip_minutes), 0.7)
            )
            dur_min = float(
                np.clip(raw_min, self.cfg.min_trip_minutes, self.cfg.max_trip_minutes)
            )

            total_s = self.PRE_SLEEP_S + self.CRANK_S + dur_min * 60 + self.POST_SETTLE_S

            # Ambient: daily base + diurnal cosine + noise
            diurnal = -np.cos(2 * np.pi * (hour - 4) / 24) * 4  # ±4 °C
            ambient = temp_base + diurnal + float(self.rng.normal(0, 1.5))

            drive_type = (
                "highway" if dur_min > 90 else ("errand" if dur_min < 15 else "commute")
            )

            trips.append(
                DriveCycleEvent(
                    cycle_id=0,
                    day=0,
                    start_time=trip_start,
                    duration_s=round(total_s, 1),
                    ambient_temp_c=round(ambient, 1),
                    drive_type=drive_type,
                )
            )

        # Resolve overlaps — push later trips forward
        valid: list[DriveCycleEvent] = []
        for trip in sorted(trips, key=lambda t: t.start_time):
            if valid:
                prev_end = valid[-1].end_time
                if trip.start_time < prev_end + timedelta(minutes=5):
                    trip.start_time = prev_end + timedelta(minutes=5)
            valid.append(trip)
        return valid

    def _time_slots(self, n: int) -> list[float]:
        """Pick *n* hour-of-day slots weighted towards morning / evening."""
        windows = [
            (6.0, 10.0, 0.35),
            (10.0, 15.0, 0.20),
            (16.0, 21.0, 0.35),
            (21.0, 24.0, 0.10),
        ]
        probs = np.array([w[2] for w in windows])
        probs /= probs.sum()
        out: list[float] = []
        for _ in range(n):
            idx = int(self.rng.choice(len(windows), p=probs))
            lo, hi, _ = windows[idx]
            out.append(round(float(self.rng.uniform(lo, hi)), 2))
        return out

    def _temp_trajectory(self) -> list[float]:
        """Daily mean ambient temperatures — mean-reverting random walk."""
        temps = np.zeros(self.cfg.total_days)
        temps[0] = self.cfg.ambient_temp_mean_c
        for i in range(1, len(temps)):
            dev = temps[i - 1] - self.cfg.ambient_temp_mean_c
            temps[i] = temps[i - 1] - 0.1 * dev + self.rng.normal(
                0, self.cfg.ambient_temp_std_c * 0.3
            )
        return temps.tolist()

    def _fault_rate_dict(self) -> dict[FaultType, float]:
        fr = self.cfg.fault_rates
        return {
            FaultType.OVERLOAD_SPIKE: fr.overload_spike,
            FaultType.INTERMITTENT_OVERLOAD: fr.intermittent_overload,
            FaultType.VOLTAGE_SAG: fr.voltage_sag,
            FaultType.THERMAL_DRIFT: fr.thermal_drift,
            FaultType.NOISY_SENSOR: fr.noisy_sensor,
            FaultType.CONNECTOR_AGING: fr.connector_aging,
            FaultType.OPEN_LOAD: fr.open_load,
            FaultType.GRADUAL_DEGRADATION: fr.gradual_degradation,
            FaultType.COLD_CRANK: fr.cold_crank,
            FaultType.JUMP_START: fr.jump_start,
            FaultType.LOAD_DUMP: fr.load_dump,
            FaultType.THERMAL_COUPLING: fr.thermal_coupling,
            FaultType.WAKE_TRANSIENT: fr.wake_transient,
        }

    @staticmethod
    def _eligible(channels: list[ChannelMeta], ft: FaultType) -> list[ChannelMeta]:
        """Return channels eligible for a given fault type."""
        if ft in (FaultType.COLD_CRANK, FaultType.JUMP_START, FaultType.LOAD_DUMP):
            return [
                c
                for c in channels
                if c.power_class in (PowerClass.ALWAYS_ON, PowerClass.IGNITION)
            ]
        if ft == FaultType.WAKE_TRANSIENT:
            return [
                c
                for c in channels
                if c.power_class in (PowerClass.IGNITION, PowerClass.ACCESSORY)
            ]
        if ft == FaultType.OPEN_LOAD:
            return [
                c
                for c in channels
                if c.duty_cycle > 0 and c.power_class != PowerClass.ALWAYS_ON
            ]
        if ft == FaultType.THERMAL_DRIFT:
            return [c for c in channels if c.nominal_current_a >= 3.0]
        # Default: any channel that is not a squib / always-off monitor
        return [c for c in channels if c.duty_cycle > 0]


# ---------------------------------------------------------------------------
# Multi-cycle generation orchestrator
# ---------------------------------------------------------------------------


def generate_multi_cycle(
    sim_cfg: SimulationConfig,
    cycles: list[DriveCycleEvent],
    faults_per_cycle: dict[int, list[FaultInjection]],
    progress_callback=None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate telemetry for every cycle and concatenate.

    Each cycle gets its own ``TelemetryGenerator`` with an isolated seed
    derived via ``SeedSequence`` so results are fully reproducible.

    Args:
        sim_cfg: Base simulation config (channels, sample_interval, etc.)
        cycles: Planned drive cycle events.
        faults_per_cycle: ``{cycle_id: [FaultInjection, ...]}``.
        progress_callback: Optional ``(done, total) -> None`` for progress.

    Returns:
        ``(telemetry_df, labels_df)`` spanning all cycles.  Both contain a
        ``drive_cycle_id`` column.
    """
    from efuse_datagen.simulation.generator import TelemetryGenerator

    seed_seq = np.random.SeedSequence(sim_cfg.seed)
    child_seeds = seed_seq.spawn(len(cycles))

    all_telem: list[pd.DataFrame] = []
    all_labels: list[pd.DataFrame] = []

    for i, cycle in enumerate(cycles):
        # Override per-cycle: ambient, duration, power states, faults, seed
        cycle_channels = [
            ch.model_copy(update={"t_ambient_c": cycle.ambient_temp_c})
            for ch in sim_cfg.channels
        ]
        cycle_cfg = sim_cfg.model_copy(
            update={
                "duration_s": cycle.duration_s,
                "channels": cycle_channels,
                "power_state_events": DriveCyclePlanner.build_power_events(cycle),
                "fault_injections": faults_per_cycle.get(cycle.cycle_id, []),
                "seed": int(child_seeds[i].entropy % (2**31))
                if isinstance(child_seeds[i].entropy, int)
                else int(child_seeds[i].entropy[0] % (2**31)),
            }
        )

        gen = TelemetryGenerator(cycle_cfg)
        telem_df, labels_df = gen.generate()

        if telem_df.empty:
            continue

        # Shift timestamps to the cycle's absolute start time
        t0_gen = telem_df["timestamp"].iloc[0]
        offset = pd.Timestamp(cycle.start_time) - pd.Timestamp(t0_gen)
        telem_df["timestamp"] += offset
        telem_df["drive_cycle_id"] = cycle.cycle_id

        if not labels_df.empty:
            labels_df["timestamp"] += offset
            labels_df["drive_cycle_id"] = cycle.cycle_id

        all_telem.append(telem_df)
        all_labels.append(labels_df)

        if progress_callback:
            progress_callback(i + 1, len(cycles))

    telem = pd.concat(all_telem, ignore_index=True) if all_telem else pd.DataFrame()
    labels = pd.concat(all_labels, ignore_index=True) if all_labels else pd.DataFrame()
    return telem, labels
