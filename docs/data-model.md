# Data Model Reference

This document defines every output file, column, enum, and data type produced by eFuse Telemetry Generator. Use it as the contract between the generator and any downstream consumer (ML pipeline, dashboard, analytics notebook, HIL test bench).

---

## Output Directory Layout

Each run produces an isolated directory:

```
output/<run_id>/
├── telemetry.parquet          # Raw per-sample signals
├── features.parquet           # Rolling derived features
├── labels.parquet             # Ground-truth fault windows
├── channel_manifest.parquet   # Channel topology metadata
├── drive_cycles.parquet       # Drive cycle metadata (multi-cycle only)
└── config.yaml                # Full config snapshot
```

`<run_id>` format: `YYYYMMDD-HHMMSS-<6-char-random>`, e.g. `20260407-114810-dgldik`.

---

## telemetry.parquet

One row per sample per channel. At 1 s interval with 65 channels and 300 s, this is 19,500 rows. At 1 s with a 30-day multi-cycle run, expect 5–15 M rows.

| Column | Type | Unit | Description |
|--------|------|------|-------------|
| `timestamp` | datetime64[ns] | — | Sample timestamp (UTC) |
| `channel_id` | string | — | Unique channel identifier, e.g. `ch_01` |
| `current_a` | float64 | A | Sensed load current (after ISENSE chain + noise) |
| `voltage_v` | float64 | V | Bus voltage at channel (includes sag/dump events + noise) |
| `temperature_c` | float64 | °C | Die junction temperature (RC thermal model output) |
| `state_on_off` | int | 0/1 | Gate drive state: 1 = load energised, 0 = off (sleep, duty-cycle off, or tripped) |
| `trip_flag` | int | 0/1 | 1 when protection has tripped the channel |
| `protection_event` | string | — | Protection action this sample: `none`, `scp`, `i2t`, `latch_off`, `thermal_shutdown`, `open_load_diag`, `over_voltage` |
| `reset_counter` | int | — | Cumulative retry count since last latch-off clear |
| `device_status` | string | — | eFuse IC status: `ok`, `warning`, `fault`, `unknown` |
| `drive_cycle_id` | int | — | Cycle index (multi-cycle only; absent in single-cycle runs) |

### Notes

- `current_a` includes all noise sources (1/f, thermal, ADC quantization, EMI) and any active fault waveform. It is the "as-measured" signal, not the clean physical current.
- `voltage_v` reflects bus-level events (cold crank, load dump, jump start) plus connector resistance drop for aging channels.
- During `state_on_off = 0`, current drops to dark current (μA level). Fault injection is suppressed while off.
- `trip_flag` transitions from 0→1 when SCP or F(i,t) triggers, and 1→0 after cooldown + retry or after latch-off release (if retry count exceeded, stays latched).

---

## features.parquet

One row per sample per channel (same index as telemetry, minus edge samples consumed by rolling windows).

### Current Features

| Column | Type | Unit | Description |
|--------|------|------|-------------|
| `rolling_rms_current` | float64 | A | √(mean(I²)) over window |
| `rolling_mean_current` | float64 | A | Mean current over window |
| `rolling_max_current` | float64 | A | Max current over window |
| `rolling_min_current` | float64 | A | Min current over window |

### Temperature

| Column | Type | Unit | Description |
|--------|------|------|-------------|
| `temperature_slope` | float64 | °C/sample | Finite-difference rate of temperature change |

### Anomaly Detection

| Column | Type | Unit | Description |
|--------|------|------|-------------|
| `spike_score` | float64 | σ | (I − rolling_mean) / rolling_std, clipped ≥ 0. How many standard deviations above baseline. |
| `trip_frequency` | float64 | count | Rolling sum of trip_flag rising edges (2× window) |
| `recovery_time_s` | float64 | s | Seconds elapsed since last trip_flag falling edge |

### Degradation

| Column | Type | Unit | Description |
|--------|------|------|-------------|
| `degradation_trend` | float64 | A/sample | Linear slope of rolling_mean_current over 4× window. Positive = rising baseline current (aging). |

### Protection Event Rates

| Column | Type | Unit | Description |
|--------|------|------|-------------|
| `protection_event_rate` | float64 | fraction | Fraction of samples with non-NONE protection event (per window) |
| `scp_count` | int | count | SCP events in window |
| `i2t_count` | int | count | F(i,t) trip events in window |
| `latch_off_count` | int | count | Latch-off events in window |
| `thermal_shutdown_count` | int | count | Thermal shutdown events in window |
| `open_load_diag_count` | int | count | Open-load diagnostic events in window |
| `over_voltage_count` | int | count | Over-voltage events in window |

### Voltage

| Column | Type | Unit | Description |
|--------|------|------|-------------|
| `rolling_min_voltage` | float64 | V | Min bus voltage over window — under-voltage indicator |
| `rolling_max_voltage` | float64 | V | Max bus voltage over window |
| `rolling_voltage_drop` | float64 | V | mean(V_nominal − V) over window — connector aging surrogate |

### Grouping

Features are computed per `(channel_id, drive_cycle_id)` group when multi-cycle, or per `channel_id` alone for single-cycle runs. This prevents rolling windows from spanning across ignition off→on boundaries, which would produce false anomaly signals.

---

## labels.parquet

One row per fault injection event. Ground-truth for supervised ML training.

| Column | Type | Unit | Description |
|--------|------|------|-------------|
| `channel_id` | string | — | Target channel |
| `fault_type` | string | — | One of the 14 `FaultType` enum values |
| `start_time` | datetime64[ns] | — | Fault window start |
| `end_time` | datetime64[ns] | — | Fault window end |
| `duration_s` | float64 | s | Fault duration |
| `severity` | float64 | 0.0–1.0 | Fault severity (dimensionless). Controls waveform amplitude. |
| `drive_cycle_id` | int | — | Cycle index (multi-cycle only) |

### Fault Types

| Value | Waveform | Typical Trigger |
|-------|----------|-----------------|
| `overload_spike` | Exponential rise to I_trip × intensity | Stalled motor, short circuit |
| `intermittent_overload` | Damped oscillation bursts | Loose connector under vibration |
| `voltage_sag` | Exponential voltage drop | Heavy auxiliary load, weak battery |
| `thermal_drift` | Gradual current ramp (insulation breakdown) | Aging wire harness |
| `noisy_sensor` | High-frequency noise burst on I/V sense | EMI from nearby inverter |
| `dropped_packet` | 40% NaN injection on telemetry | CAN bus overload |
| `gradual_degradation` | Slow exponential current increase | Component aging |
| `connector_aging` | Rising R_contact → falling V_load | Fretting corrosion |
| `open_load` | Current → ~0 A, DIAG flag set | Wire break |
| `jump_start` | Bus voltage → 16–24 V | External booster connected |
| `load_dump` | Bus voltage → ~40 V spike, exp decay | Alternator field collapse |
| `cold_crank` | Bus voltage → 7–9 V sag | Starter motor engagement |
| `thermal_coupling` | Gentle temperature rise (neighbour die) | Adjacent high-power channel |
| `wake_transient` | Current spike above nominal at SLEEP→ACTIVE | Inrush from capacitive load |

---

## channel_manifest.parquet

One row per channel. Written once per run.

| Column | Type | Description |
|--------|------|-------------|
| `channel_id` | string | Unique ID |
| `zone_id` | string | Zone: `zone_front`, `zone_rear`, `zone_body`, `zone_central` |
| `load_name` | string | Human-readable load: "headlamp_left", "seat_heater_driver", etc. |
| `system_cluster` | string | Functional group: "lighting", "climate", "chassis", "powertrain", etc. |
| `efuse_family` | string | IC family from catalog |
| `nominal_current_a` | float64 | Expected steady-state current |
| `max_current_a` | float64 | Absolute max before protection trip |
| `duty_cycle` | float64 | 0.0–1.0, fraction of time ON (1.0 = always on) |
| `on_duration_s` | float64 | Duty-cycle ON period (NaN if duty_cycle = 1.0) |
| `off_duration_s` | float64 | Duty-cycle OFF period (NaN if duty_cycle = 1.0) |

Used by the dashboard to display load names, zone filters, and topology summaries.

---

## drive_cycles.parquet

One row per drive cycle. Only written in multi-cycle mode.

| Column | Type | Description |
|--------|------|-------------|
| `cycle_id` | int | Sequential cycle index |
| `day` | int | Day number (1-based) |
| `start_time` | datetime64[ns] | Cycle start timestamp |
| `end_time` | datetime64[ns] | Cycle end timestamp |
| `duration_s` | float64 | Total cycle duration including sleep/crank margins |
| `ambient_temp_c` | float64 | Ambient temperature for this cycle |
| `drive_type` | string | Profile tag: "commuter", "heavy", "mixed" |

---

## config.yaml

Exact copy of the resolved `SimulationConfig` used for the run, including any CLI overrides. Enables exact reproduction:

```bash
efuse-gen --config output/20260407-114810-dgldik/config.yaml
```

---

## Enums Reference

### EFuseFamily

```
inf_hs_2a, inf_hs_5a, inf_hs_9a, inf_hs_11a, inf_hs_14a, inf_hs_18a, inf_hs_28a,
inf_multi_10a, inf_hs_100a,
st_hs_14a, st_hs_30a, st_hs_50a,
st_dual_14a, st_hb_30a, st_ls_50a,
custom
```

### PowerState

```
SLEEP, CRANK, ACTIVE, ACCESSORY
```

### DeviceStatus

```
ok, warning, fault, unknown
```

### ProtectionEvent

```
none, scp, i2t, latch_off, thermal_shutdown, open_load_diag, over_voltage
```

### FaultType

```
overload_spike, intermittent_overload, voltage_sag, thermal_drift,
noisy_sensor, dropped_packet, gradual_degradation, connector_aging,
open_load, jump_start, load_dump, cold_crank, thermal_coupling,
wake_transient
```
