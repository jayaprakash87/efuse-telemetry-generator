# Configuration Guide

All VIP Data Generator behaviour is driven by YAML configuration files. This document is the complete field reference.

---

## Quick Start

```bash
# Use a built-in config
vip-gen --config configs/default.yaml

# Override specific fields via CLI
vip-gen --config configs/default.yaml --duration 120 --seed 99 --format csv
```

CLI flags override the corresponding YAML fields:
- `--duration` → `simulation.duration_s`
- `--seed` → `simulation.seed`
- `--format` → `storage.format`
- `--output` → `storage.output_dir`

---

## Top-Level Structure

```yaml
simulation:
  # ... scenario definition, channels, faults, drive cycle
features:
  # ... rolling window parameters
storage:
  # ... output format and directory
```

---

## `simulation`

The core scenario definition.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `scenario_id` | string | `"default"` | Unique scenario identifier (used in logging) |
| `name` | string | `"Default Scenario"` | Human-readable scenario name |
| `description` | string | `""` | Free-text description |
| `duration_s` | float | `60.0` | Simulation duration in seconds (single-cycle mode) |
| `sample_interval_ms` | float | `100.0` | Sample period in milliseconds. Use 100 for short runs, 1000 for month-long. |
| `seed` | int | `42` | Master random seed for reproducibility |
| `use_example_topology` | bool | `false` | When true, loads the built-in 65-channel 4-zone BEV topology instead of inline channels |
| `channels` | list | 3-ch demo | Inline channel definitions (see below) |
| `channel_specs` | list | `[]` | Compact channel specs referencing eFuse catalog (advanced) |
| `fault_injections` | list | `[]` | Manual fault placement (single-cycle mode) |
| `power_state_events` | list | `[]` | Power-state timeline. Empty = always ACTIVE. |
| `drive_cycle` | object | disabled | Multi-cycle configuration (see below) |

### `simulation.channels[]`

Each channel defines one eFuse output. These are the most commonly used fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `channel_id` | string | **required** | Unique ID, e.g. `ch_01` |
| `load_name` | string | `""` | Human-readable load name: `headlamp_left`, `seat_heater_driver` |
| `zone_id` | string | `""` | Zone assignment: `zone_front`, `zone_rear`, `zone_body`, `zone_central` |
| `system_cluster` | string | `""` | Functional group: `lighting`, `climate`, `chassis`, `powertrain` |
| `nominal_current_a` | float | `5.0` | Expected steady-state current (A) |
| `max_current_a` | float | `15.0` | Absolute max before protection trip (A) |
| `nominal_voltage_v` | float | `13.5` | Nominal bus voltage (V) |
| `fuse_rating_a` | float | `10.0` | Equivalent blade-fuse rating (A) |
| `load_type` | string | `"resistive"` | Load class: `resistive`, `motor`, `inductive`, `capacitive`, `led`, `ptc`, `solenoid` |
| `r_ds_on_ohm` | float | `0.010` | eFuse Rds,on at 25°C (Ω) |
| `r_thermal_kw` | float | `40.0` | Thermal resistance junction-to-ambient (K/W) |
| `tau_thermal_s` | float | `15.0` | RC thermal time constant (s) |
| `t_ambient_c` | float | `25.0` | Ambient temperature (°C) |
| `duty_cycle` | float | `1.0` | Fraction of time ON (0.0–1.0). 1.0 = always on. |
| `on_duration_s` | float | `null` | ON period for duty-cycling loads |
| `off_duration_s` | float | `null` | OFF period for duty-cycling loads |

**Advanced / less common fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `efuse_family` | string | `"CUSTOM"` | IC family from catalog (auto-fills electrical parameters) |
| `current_adc_bits` | int | `12` | ADC resolution for current sense |
| `voltage_adc_bits` | int | `12` | ADC resolution for voltage sense |
| `pink_noise_alpha` | float | `1.0` | 1/f noise spectral exponent |
| `emi_amplitude_a` | float | `0.05` | EMI burst amplitude (A) |
| `cooldown_s` | float | `1.0` | Protection cooldown before retry (s) |
| `max_retries` | int | `3` | Retry count before latch-off |
| `i2t_threshold` | float | `500.0` | F(i,t) energy threshold (A²s) |
| `scp_threshold_a` | float | `null` | SCP comparator threshold; null = auto from max_current_a |

### `simulation.fault_injections[]`

Manual fault placement for single-cycle scenarios:

| Field | Type | Description |
|-------|------|-------------|
| `channel_id` | string | Target channel (must match a channel_id in channels list) |
| `fault_type` | string | One of 14 fault types (see [data-model.md](data-model.md)) |
| `start_s` | float | Fault start time (seconds from scenario start) |
| `duration_s` | float | Fault duration (seconds) |
| `intensity` | float | Severity 0.0–1.0 (controls waveform amplitude) |

### `simulation.power_state_events[]`

Ordered power-state transitions (single-cycle mode):

| Field | Type | Description |
|-------|------|-------------|
| `time_s` | float | Seconds from scenario start |
| `state` | string | `SLEEP`, `CRANK`, `ACTIVE`, or `ACCESSORY` |

Example ignition cycle:
```yaml
power_state_events:
  - time_s: 0.0
    state: SLEEP
  - time_s: 5.0
    state: CRANK
  - time_s: 8.0
    state: ACTIVE
  - time_s: 55.0
    state: SLEEP
```

When empty (default), the entire simulation runs in ACTIVE state.

### `simulation.drive_cycle`

Multi-day drive cycle scheduler. When `enabled: true`, this overrides `duration_s`, `fault_injections`, and `power_state_events`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `false` | Activate multi-cycle mode |
| `total_days` | int | `30` | Simulation span in calendar days |
| `profile` | string | `"mixed"` | Driving profile: `commuter`, `mixed`, `heavy` |
| `mean_trips_per_day` | float | `2.5` | Poisson λ for daily trip count |
| `max_trips_per_day` | int | `6` | Cap on trips per day |
| `no_drive_day_probability` | float | `0.10` | Probability of zero trips on a given day |
| `min_trip_minutes` | float | `5.0` | Minimum trip duration (minutes) |
| `max_trip_minutes` | float | `240.0` | Maximum trip duration (minutes) |
| `median_trip_minutes` | float | `30.0` | Log-normal median trip duration |
| `ambient_temp_mean_c` | float | `22.0` | Seasonal baseline ambient temperature (°C) |
| `ambient_temp_std_c` | float | `8.0` | Day-to-day temperature variation σ (°C) |
| `fault_rates` | object | see below | Per-fault-type Poisson rates |

### `simulation.drive_cycle.fault_rates`

Probability per vehicle-hour of driving. When a Poisson draw fires, one random eligible channel is selected.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `overload_spike` | float | `0.05` | Overcurrent events |
| `intermittent_overload` | float | `0.03` | Oscillatory overcurrent |
| `voltage_sag` | float | `0.04` | Battery sag events |
| `thermal_drift` | float | `0.02` | Insulation degradation |
| `noisy_sensor` | float | `0.03` | EMI bursts |
| `connector_aging` | float | `0.01` | Fretting corrosion (progressive) |
| `open_load` | float | `0.005` | Wire break |
| `gradual_degradation` | float | `0.01` | Load aging (progressive) |
| `cold_crank` | float | `0.50` | Only fires when ambient < 5°C |
| `jump_start` | float | `0.002` | External booster events |
| `load_dump` | float | `0.02` | Alternator collapse |
| `thermal_coupling` | float | `0.03` | Die neighbour heating |
| `wake_transient` | float | `0.15` | Inrush current at wake |

---

## `features`

Rolling window parameters for the feature engine.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `window_duration_s` | float | `5.0` | Rolling window duration in seconds |
| `min_duration_s` | float | `1.0` | Minimum data before features are valid |
| `window_size` | int | `0` | Override: fixed window in samples (0 = auto from duration) |
| `min_periods` | int | `0` | Override: fixed min_periods (0 = auto from duration) |

Auto-computation: `window_size = max(window_duration_s / sample_interval_s, 2)`

---

## `storage`

Output persistence settings.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `output_dir` | string | `"output"` | Root output directory |
| `format` | string | `"parquet"` | File format: `parquet`, `csv`, `json` |

---

## Included Configs

### `configs/default.yaml`

3-channel demo with 4 manual fault injections over 60 seconds. Good for quick smoke tests and learning the tool.

```bash
vip-gen --config configs/default.yaml
# → ~1,800 rows, 4 fault labels
```

### `configs/zone_controller_full.yaml`

Full 65-channel 4-zone topology with 21 manual faults over 300 seconds. Uses `use_example_topology: true` to load the built-in BEV topology from the eFuse catalog.

```bash
vip-gen --config configs/zone_controller_full.yaml
# → ~195,000 rows, ~9,000 labels, 31 feature columns
```

### `configs/one_month.yaml`

30-day multi-cycle simulation. Stochastic fault injection, progressive aging, mean-reverting ambient temperature. See [drive-cycles.md](drive-cycles.md) for details.

```bash
vip-gen --config configs/one_month.yaml
# → ~55 cycles, ~37 h driving, ~8.6 M rows
```

### `configs/stress_test.yaml`

Single channel with 7 fault types injected sequentially over 120 seconds. Useful for validating that all fault waveform generators produce correct output.

```bash
vip-gen --config configs/stress_test.yaml
# → ~1,200 rows, 7 fault labels
```

---

## Writing Custom Configs

### Minimal Single-Cycle

```yaml
simulation:
  scenario_id: my_test
  duration_s: 30.0
  channels:
    - channel_id: ch_01
      load_name: test_load
      nominal_current_a: 5.0
```

### With Faults

```yaml
simulation:
  scenario_id: my_fault_test
  duration_s: 60.0
  seed: 123
  channels:
    - channel_id: ch_01
      load_name: headlamp
      nominal_current_a: 6.0
      max_current_a: 15.0
  fault_injections:
    - channel_id: ch_01
      fault_type: overload_spike
      start_s: 10.0
      duration_s: 3.0
      intensity: 0.8
```

### With Power States

```yaml
simulation:
  scenario_id: ignition_cycle
  duration_s: 60.0
  channels:
    - channel_id: ch_01
      load_name: headlamp
      nominal_current_a: 6.0
  power_state_events:
    - time_s: 0.0
      state: SLEEP
    - time_s: 5.0
      state: CRANK
    - time_s: 8.0
      state: ACTIVE
    - time_s: 55.0
      state: SLEEP
  fault_injections:
    - channel_id: ch_01
      fault_type: wake_transient
      start_s: 8.0
      duration_s: 2.0
      intensity: 0.6
```

### Multi-Cycle (7-Day Commuter)

```yaml
simulation:
  scenario_id: weekly_commuter
  sample_interval_ms: 1000.0
  seed: 77
  use_example_topology: true
  drive_cycle:
    enabled: true
    total_days: 7
    profile: commuter
    mean_trips_per_day: 2.0
    median_trip_minutes: 25
    ambient_temp_mean_c: 15.0
    fault_rates:
      overload_spike: 0.03
      connector_aging: 0.02

features:
  window_duration_s: 5.0

storage:
  output_dir: output
```
