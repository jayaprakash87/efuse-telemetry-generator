# Configuration Guide

All eFuse Telemetry Generator behaviour is driven by YAML configuration files. This document is the complete field reference.

---

## Quick Start

```bash
# Use a built-in config
efuse-gen --config quick_demo

# Override specific fields via CLI
efuse-gen --config quick_demo --duration 120 --seed 99 --format csv
```

CLI flags override the corresponding YAML fields:
- `--duration` → `simulation.duration_s`
- `--seed` → `simulation.seed`
- `--format` → `storage.format`
- `--output` → `storage.output_dir`
- `--dry-run` — Preview generation (channel count, estimated rows, output path) without writing files
- `--json-log` — Emit structured JSON log lines instead of Rich pretty-printed output

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
| `scenario_id` | string | `"quick_demo"` | Unique scenario identifier (used in logging and output directory naming) |
| `name` | string | `"Quick Demo"` | Human-readable scenario name |
| `description` | string | `""` | Free-text description |
| `duration_s` | float | `60.0` | Simulation duration in seconds (single-cycle mode). Ignored when `drive_cycle.enabled` is true — total duration is determined by `drive_cycle.total_days`. |
| `sample_interval_ms` | float | `100.0` | Sample period in milliseconds. Use 100 for short runs, 1000 for month-long. |
| `seed` | int | `42` | Master random seed for reproducibility |
| `topology_file` | string | `""` | Path to a reusable topology YAML file (zones + channel_specs). Use a bundled name like `bev_4zone_65ch` or a file path like `./my_vehicle.yaml`. Parsed YAML is cached for fleet-mode performance. Paths with `..` are rejected to prevent directory traversal. |
| `channels` | list | 3-ch demo | Inline channel definitions (see below). For small topologies or full-explicit control. |
| `channel_specs` | list | `[]` | Compact channel specs referencing the bundled eFuse IC catalog. Used together with `zones`. Typically loaded via `topology_file`. |
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
| `current_limit_a` | float | `0.0` | IC current-limiting clamp (A). 0 = auto (1.5× fuse_rating_a) |
| `can_current_resolution_a` | float | `0.01` | CAN signal packing resolution for current (A/bit). 0 = skip |
| `can_voltage_resolution_v` | float | `0.01` | CAN signal packing resolution for voltage (V/bit). 0 = skip |
| `ground_offset_max_v` | float | `2.0` | Max GND node shift during GROUND_OFFSET fault (V) |
| `stg_resistance_ohm` | float | `0.05` | Short-to-GND fault path resistance (Ω) |

### `simulation.fault_injections[]`

Manual fault placement for single-cycle scenarios:

| Field | Type | Description |
|-------|------|-------------|
| `channel_id` | string | Target channel (must match a channel_id in channels list) |
| `fault_type` | string | One of 16 fault types (see [data-model.md](data-model.md)) |
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
| `ground_offset` | float | `0.02` | GND node potential shift (corroded bond) |
| `short_to_ground` | float | `0.01` | Wire-to-chassis short circuit |

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

### `quick_demo`

3-channel demo with 4 manual fault injections over 60 seconds. Good for quick smoke tests and learning the tool.

```bash
efuse-gen --config quick_demo
# → ~1,800 rows, 4 fault labels
```

Source YAML: [`efuse_datagen/config/templates/quick_demo.yaml`](../efuse_datagen/config/templates/quick_demo.yaml)

### `custom_topology`

User-defined 2-zone, 6-channel ZC architecture with fully explicit parameters. No catalog dependency. Start here when defining your own vehicle topology.

```bash
efuse-gen --config custom_topology
# → ~7,200 rows, 3 fault labels
```

Source YAML: [`efuse_datagen/config/templates/custom_topology.yaml`](../efuse_datagen/config/templates/custom_topology.yaml)

### `custom_topology_with_catalog`

User-defined 3-zone, 8-channel ZC architecture using IC catalog presets for electrical defaults. Demonstrates the hybrid approach: your zones and load mapping, catalog-sourced IC parameters.

```bash
efuse-gen --config custom_topology_with_catalog
# → ~14,400 rows, 4 fault labels
```

Source YAML: [`efuse_datagen/config/templates/custom_topology_with_catalog.yaml`](../efuse_datagen/config/templates/custom_topology_with_catalog.yaml)

### `single_drive`

Full 65-channel 4-zone **reference** topology with 21 manual faults over 300 seconds. Loads the bundled `bev_4zone_65ch` topology file — you only see the scenario config + faults in the template.

```bash
efuse-gen --config single_drive
# → ~195,000 rows, ~9,000 labels, 31 feature columns
```

Source YAML: [`efuse_datagen/config/templates/single_drive.yaml`](../efuse_datagen/config/templates/single_drive.yaml)

### `multi_day`

30-day multi-cycle simulation. Stochastic fault injection, progressive aging, mean-reverting ambient temperature. See [drive-cycles.md](drive-cycles.md) for details.

```bash
efuse-gen --config multi_day
# → ~55 cycles, ~37 h driving, ~8.6 M rows
```

Source YAML: [`efuse_datagen/config/templates/multi_day.yaml`](../efuse_datagen/config/templates/multi_day.yaml)

### `fleet`

Multiple vehicles over a shared timeline with regional weather. Population archetypes, age-dependent fault scaling, parallel generation.

```bash
efuse-gen --config fleet --vehicles 3 --days 3
# → 3 vehicles × 3 days, ~2.9 M rows total
```

Source YAML: [`efuse_datagen/config/templates/fleet.yaml`](../efuse_datagen/config/templates/fleet.yaml)

### `stress_test`

Single channel with 7 fault types injected sequentially over 120 seconds. Useful for validating that all fault waveform generators produce correct output.

```bash
efuse-gen --config stress_test
# → ~1,200 rows, 7 fault labels
```

Source YAML: [`efuse_datagen/config/templates/stress_test.yaml`](../efuse_datagen/config/templates/stress_test.yaml)

---

## Custom Topology — Bring Your Own Zone Controller

The generator is **topology-agnostic**. You define your Zone Controller architecture — zones, channels, load mapping — and the generator produces the data. The bundled reference topology and IC catalog are optional convenience features, not requirements.

### OEM Workflow

If your organisation (e.g., BMW, Mercedes, VW) wants to generate data for **your specific zone controller**, the typical workflow is:

1. **Export your channel list** — from your EE design tool, wire harness database, or DOORS export as CSV / Excel
2. **Import it** — `efuse-gen topology import channels.xlsx -o my_vehicle.yaml`  *(Excel requires: `pip install "efuse-telemetry-generator[excel]"`)*
3. **Write a scenario config** — reference the topology file, add faults, set duration
4. **Run the generator** — `efuse-gen --config ./my-scenario.yaml`

Don't have a spreadsheet yet? Generate a CSV template to fill in:

```bash
efuse-gen topology template -o my_channels.csv

# Or a minimal template with just the essential columns
efuse-gen topology template -o my_channels.csv --minimal

# Open in Excel / Google Sheets, fill in your channels, then:
efuse-gen topology import my_channels.csv -o my_vehicle.yaml
```

Need to edit an existing topology in a spreadsheet? Export it:

```bash
efuse-gen topology export my_vehicle.yaml -o channels.csv
```

### Ways to Define Your Topology

| Approach | When to use | Catalog needed? |
|----------|-------------|------------------|
| **`efuse-gen topology import`** (recommended) | Import from CSV / Excel — the way engineers actually work. | Depends on efuse_family column |
| **`topology_file`** | Reuse one topology YAML across many scenarios. | Depends on topology file |
| **`zones` + `channel_specs` with `efuse_family`** | Inline topology with catalog defaults. Good for self-contained config files. | Yes (as preset source) |
| **`zones` + inline `channels`** | Full explicit control from datasheets / SPICE. No catalog dependency. | No |

### Template: Full Custom Topology (no catalog)

```bash
efuse-gen --config custom_topology
```

This template defines 2 zones and 6 channels with fully explicit parameters. Copy it as a starting point:

```bash
# Export the template
efuse-gen --config custom_topology          # run it first to verify
# Copy to your project (adjust path as needed)
cp $(python -c "from importlib.resources import files; print(files('efuse_datagen').joinpath('config/templates/custom_topology.yaml'))") ./my-vehicle.yaml
```

Key structure:

```yaml
simulation:
  zones:
    - zone_id: zone_front
      name: "Front Zone Controller"
      location: front
      bus_interface: can
    - zone_id: zone_rear
      name: "Rear Zone Controller"
      location: rear
      bus_interface: can

  channels:
    - channel_id: ch_01
      zone_id: zone_front              # maps to your zone
      load_name: headlamp_left
      nominal_current_a: 6.0
      r_ds_on_ohm: 0.008              # from YOUR IC datasheet
      r_thermal_kw: 35.0
      tau_thermal_s: 20.0
      # ... all parameters explicit
```

### Template: Custom Zones + IC Catalog Presets

```bash
efuse-gen --config custom_topology_with_catalog
```

This template defines **your zones** but references IC families from the catalog for electrical defaults. Best when your vehicle uses standard production ICs (Infineon PROFET+2, ST VIPower, etc.):

```yaml
simulation:
  zones:
    - zone_id: zc_cockpit
      name: "Cockpit Zone Controller"
      location: body
      bus_interface: can

  channel_specs:
    - channel_id: ch_01
      zone_id: zc_cockpit
      efuse_family: inf_hs_14a        # BTS7008 — catalog fills Rds,on, thermal params, etc.
      load_name: instrument_cluster
      nominal_current_a: 5.0          # override catalog default
      t_ambient_c: 30.0               # override ambient for your environment
```

Any field you specify in the spec overrides the catalog default. Fields you omit are filled from the catalog entry.

### Zone Definition Reference

Each zone represents a physical Zone Controller ECU:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `zone_id` | string | **required** | Unique zone identifier (e.g., `zc_front`, `zone_body`) |
| `name` | string | `""` | Human-readable name |
| `location` | string | `"body"` | Physical placement: `body`, `front`, `rear`, `underhood` |
| `bus_interface` | string | `"can"` | Communication bus: `can`, `xcp`, `replay` |
| `cdd_read_cycle_ms` | float | `10.0` | CDD SPI poll frequency (ms) |

Channels assigned to a zone inherit its `bus_interface` as their `source_protocol`.

### The eFuse IC Catalog — a Preset Library

The bundled catalog contains electrical parameters for 19 production IC families (Infineon PROFET+2, ST VIPower, etc.) sourced from public datasheets. It's a **convenience library of component presets**, not a required input. Think of it like a parts database.

Use it when:
- You're building a large topology and want to reference IC families by name
- Your vehicle uses standard production ICs and you don't want to re-enter datasheet values
- You want to compare behaviour across different IC families

Skip it when:
- You have your own IC parameters (custom ASIC, internal datasheet values)
- You want full control over every electrical parameter
- You're simulating a non-automotive eFuse topology

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
  topology_file: bev_4zone_65ch  # or ./my_vehicle.yaml
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
