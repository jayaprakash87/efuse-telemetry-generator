# Multi-Cycle Drive Simulation

## Problem Statement

A single 60–300 second simulation captures the steady-state behaviour of eFuse channels and can validate protection logic for discrete fault events. But real-world failure modes — connector aging, gradual insulation degradation, thermal fatigue — evolve over **weeks to months** of cumulative vehicle operation.

The multi-cycle drive simulation generates a realistic calendar of ignition cycles spanning days to months, with:
- Variable trip counts and durations per day
- Ambient temperature variation (seasonal, diurnal)
- Stochastic fault injection scaled by driving hours
- Progressive wear accumulation across cycles

This enables training and validation of:
- **Degradation detection models** — catch slow connector aging before wire ignition
- **Fleet analytics** — simulate thousands of vehicle-months of operation
- **Lifetime prediction** — project time-to-failure from observed trends

---

## How It Works

### 1. Schedule Generation

`DriveCyclePlanner.generate_schedule()` creates a list of `DriveCycleEvent` objects:

```
Day 1:  ├── cycle_0: 7:30–8:05 (35 min, 22°C) ──── commute to work
        └── cycle_1: 17:15–17:55 (40 min, 24°C) ── commute home

Day 2:  └── cycle_2: 10:00–12:15 (135 min, 21°C) ─ weekend road trip

Day 3:  (no-drive day)

Day 4:  ├── cycle_3: 6:45–7:10 (25 min, 19°C)
        ├── cycle_4: 12:00–12:20 (20 min, 22°C) ── lunch errand
        └── cycle_5: 18:30–19:45 (75 min, 18°C)
...
```

**Trip count** per day is drawn from a Poisson distribution:
- `mean_trips_per_day` (default 2.5 for "mixed" profile)
- Capped at `max_trips_per_day` (default 6)
- `no_drive_day_probability` (default 10%) — some days the vehicle sits

**Trip duration** is log-normal:
- `median_trip_minutes` (default 30)
- Bounded by `min_trip_minutes` (5) and `max_trip_minutes` (240)

**Ambient temperature** follows a mean-reverting random walk:
- $T_i = T_{i-1} - 0.1 \times (T_{i-1} - \mu) + \mathcal{N}(0, \sigma)$
- `ambient_temp_mean_c` (default 18°C), `ambient_temp_std_c` (default 8°C)
- Captures seasonal variation and day-to-day weather changes

### 2. Power-State Sequences

Each cycle automatically gets a power-state sequence:

```
t=0          t=PRE_SLEEP   t=PRE_SLEEP+CRANK   t=duration-POST_SETTLE
 │   SLEEP    │   CRANK     │      ACTIVE        │      SLEEP
 ▼            ▼             ▼                     ▼
 ─────────────┼─────────────┼─────────────────────┼────────────
```

- **PRE_SLEEP** (5 s) — vehicle is parked, all channels at dark current
- **CRANK** (3 s) — starter motor engagement, bus voltage sags to ~10 V
- **ACTIVE** — normal driving, channels follow duty-cycle and load profiles
- **POST_SETTLE** (5 s) — engine off, loads wind down, return to sleep

### 3. Stochastic Fault Distribution

`DriveCyclePlanner.distribute_faults()` assigns faults to cycles using Poisson rates:

For each cycle and each fault type:
1. Compute expected count: $\lambda = \text{rate\_per\_hour} \times \text{cycle\_driving\_hours}$
2. Draw actual count from $\text{Poisson}(\lambda)$
3. Place each fault at a random time within the active window

**Environmental gating:**
- `cold_crank` only fires when `ambient_temp_c < 5°C`
- `wake_transient` is placed in the first seconds after CRANK→ACTIVE

**Progressive wear:**
For `connector_aging` and `gradual_degradation`:
- Rate scales up with accumulated driving hours: $\text{rate} \times (1 + \min(\text{hours}/200, 3))$
- Intensity has a progressive component: base random (0.3–0.9) + wear factor
- This means early cycles have few aging faults; later cycles have more frequent and more severe ones

### 4. Per-Cycle Generation

`generate_multi_cycle()` orchestrates the generation:

```python
for cycle in schedule:
    child_seed = seed_sequence.spawn(1)   # deterministic child seed
    
    # Override config with cycle-specific parameters
    config.duration_s = cycle.duration_s
    config.ambient_temp_c = cycle.ambient_temp_c
    config.power_states = build_power_events(cycle)
    config.faults = cycle_faults[cycle.id]
    
    # Generate
    telemetry, labels = TelemetryGenerator(config, child_seed).generate()
    
    # Shift timestamps to absolute calendar time
    telemetry['timestamp'] += cycle.start_time
    telemetry['drive_cycle_id'] = cycle.id
```

Each cycle gets an independent child seed via `numpy.random.SeedSequence.spawn()`, ensuring:
- **Reproducibility** — same master seed → same output, always
- **Independence** — adding/removing cycles doesn't change other cycles' noise

### 5. Output

After all cycles are generated:
- Telemetry DataFrames are concatenated into a single file with `drive_cycle_id` column
- Labels are concatenated with the same `drive_cycle_id`
- `drive_cycles.parquet` records cycle-level metadata (day, start/end time, ambient, drive type)
- Feature engine groups by `(channel_id, drive_cycle_id)` to respect ignition boundaries

---

## Configuration

Multi-cycle mode is activated by setting `drive_cycle.enabled: true` in the YAML config:

```yaml
simulation:
  use_example_topology: true
  sample_interval_ms: 1000.0
  seed: 42

  drive_cycle:
    enabled: true
    total_days: 30
    profile: mixed

    # Schedule
    mean_trips_per_day: 2.5
    max_trips_per_day: 6
    no_drive_day_probability: 0.10

    # Trip duration (log-normal, minutes)
    min_trip_minutes: 5
    max_trip_minutes: 240
    median_trip_minutes: 30

    # Ambient temperature
    ambient_temp_mean_c: 18.0
    ambient_temp_std_c: 8.0

    # Fault rates (per vehicle-hour)
    fault_rates:
      overload_spike: 0.05
      intermittent_overload: 0.03
      voltage_sag: 0.04
      thermal_drift: 0.02
      connector_aging: 0.01
      gradual_degradation: 0.01
      cold_crank: 0.50          # only fires when T < 5°C
      wake_transient: 0.15
      ground_offset: 0.02
      short_to_ground: 0.01
      # ... (all 16 types supported)
```

See [configuration.md](configuration.md) for full field reference.

---

## Profiles

The `profile` field selects a driving pattern preset:

| Profile | Mean Trips/Day | Median Duration | Typical Use Case |
|---------|----------------|-----------------|------------------|
| `commuter` | 2.0 | 25 min | Daily work commute, short errands |
| `heavy` | 3.5 | 45 min | Delivery vehicle, ride-share |
| `mixed` | 2.5 | 30 min | Blend of commuter + occasional long trips |

All parameters are still individually tunable — the profile just sets defaults.

---

## Typical Output Scale

| Config | Days | Cycles | Driving Hours | Rows | Labels |
|--------|------|--------|---------------|------|--------|
| `multi_day.yaml` (seed 42) | 30 | 55 | 36.8 h | 8.6 M | 142 |
| 7-day commuter | 7 | ~14 | ~6 h | ~1.4 M | ~25 |
| 90-day fleet unit | 90 | ~180 | ~100 h | ~24 M | ~500 |

Generation time scales roughly linearly with row count. The 30-day config takes ~2 minutes on a modern laptop.

---

## Analysing Multi-Cycle Data

### In the Dashboard

The dashboard auto-detects multi-cycle runs:
- **Day filter** appears in the sidebar (multi-select)
- **Drive Cycle Gantt** chart shows the timeline on the Overview tab
- All telemetry/feature plots respect the `drive_cycle_id` grouping

### In Code

```python
import pandas as pd

tel = pd.read_parquet("output/<run_id>/telemetry.parquet")
cycles = pd.read_parquet("output/<run_id>/drive_cycles.parquet")

# Merge cycle metadata onto telemetry
merged = tel.merge(cycles, left_on="drive_cycle_id", right_on="cycle_id")

# Filter to a specific day
day_5 = merged[merged["day"] == 5]

# Aggregate per cycle
cycle_stats = (
    tel.groupby(["channel_id", "drive_cycle_id"])
    .agg(mean_current=("current_a", "mean"), max_temp=("temperature_c", "max"))
)
```

### Degradation Analysis

The key value of multi-cycle data is observing trends **across** cycles:

```python
# Track connector aging: rising voltage drop over cycles
features = pd.read_parquet("output/<run_id>/features.parquet")
aging_trend = (
    features.groupby(["channel_id", "drive_cycle_id"])
    ["rolling_voltage_drop"].mean()
    .reset_index()
    .sort_values("drive_cycle_id")
)
```

Channels with `connector_aging` faults will show a monotonically increasing voltage drop across cycles, mirroring real-world fretting corrosion progression.
