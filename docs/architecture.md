# Architecture

> **For hardware engineers:** See [domain-reference.md](domain-reference.md) for eFuse protection theory, the full 16-fault catalog with physics explanations, signal chain models, and a glossary of automotive eFuse terminology.

## Purpose

eFuse Telemetry Generator synthesises physically realistic eFuse telemetry for Battery Electric Vehicle (BEV) Zone Controller architectures. It exists because:

1. **Lab hardware is expensive and slow** — a single Zone Controller test bench costs €200k+ and produces data at real-time speed. This tool generates months of data in minutes.
2. **OEM data is access-restricted** — production field data requires NDA chains and anonymisation. Synthetic data has no legal constraints.
3. **ML/analytics teams need labelled data** — real faults are rare. The generator produces ground-truth fault labels with configurable frequency and severity.
4. **Protection algorithm development needs parametric sweeps** — vary eFuse IC parameters, fault intensities, ambient conditions, and wiring topologies programmatically.

## Domain Context

### Zone Controller Architecture

Modern BEVs replace the traditional central fuse box with distributed **Zone Controllers** (ZCs) — one per physical zone of the vehicle. Each ZC contains an array of solid-state **eFuse ICs** (e.g., Infineon PROFET+2, ST VIPower) that replace conventional blade fuses.

Each eFuse channel:
- Switches a specific load (headlamp, seat heater, wiper motor, etc.)
- Measures load current via an integrated sense output (ISENSE)
- Monitors its own die temperature via an on-die sensor
- Implements overcurrent protection — both a fast SCP (Short Circuit Protection) comparator and a slower F(i,t) thermal energy integral
- Reports status over the vehicle's CAN/LIN bus

A typical BEV has 50–80 eFuse channels across 3–5 zones. This tool models the default **65-channel, 4-zone** topology:

| Zone | Channels | Systems |
|------|----------|---------|
| `zone_front` | 18 | Headlamps, HVAC, wiper, washer, charger, horn, suspension, steering |
| `zone_rear` | 17 | Tail lights, seat heaters, defroster, dampers, ventilation, charge port, radar |
| `zone_body` | 15 | Door locks, windows, mirrors, sunroof, PDU, trunk, keyless entry, immobiliser |
| `zone_central` | 15 | Main PDU, battery disconnect, DC/DC, inverter, ADAS PSU, reserve rails, HVAC compressor |

### Why Synthetic Data Matters

eFuse protection failures are safety-relevant — an overloaded wire harness can ignite. But in real vehicles:
- Protection trips happen < 0.01% of running time
- Connector aging takes months/years to manifest
- Cold-crank and load-dump events are environmental and hard to reproduce on demand

The generator creates these scenarios on demand with precise ground-truth labels, enabling:
- Protection algorithm validation (F(i,t) thresholds, retry logic, latch-off policy)
- Anomaly detection model training (connector aging signature, thermal drift)
- Fleet analytics dashboard development
- Hardware-in-the-loop test bench stimulation

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     YAML Config                         │
│  (scenario, topology, faults, drive cycle, features)    │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│                      CLI (cli.py)                        │
│  Typer entry point — auto-detects single vs multi-cycle  │
└────────┬─────────────────────────────────┬───────────────┘
         │ single-cycle                    │ multi-cycle
         ▼                                 ▼
┌──────────────────┐       ┌──────────────────────────────┐
│ TelemetryGenerator│      │   DriveCyclePlanner           │
│  (generator.py)   │      │   (drive_cycles.py)           │
│                   │      │                               │
│  Per-channel:     │      │  1. Schedule trips over N days│
│  • Bus voltage    │      │  2. Distribute stochastic     │
│  • Power gating   │      │     faults across cycles      │
│  • Duty cycling   │      │  3. Build per-cycle           │
│  • Composite noise│      │     power-state sequences     │
│  • RC thermal     │      │  4. Orchestrate per-cycle     │
│  • ISENSE chain   │      │     TelemetryGenerator calls  │
│  • Fault waveforms│      │  5. Shift timestamps,         │
│  • Protection     │      │     concatenate all cycles    │
│    (SCP + F(i,t)) │      └──────────────────────────────┘
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│                FeatureEngine (engine.py)                  │
│  Rolling windows grouped by (channel_id, drive_cycle_id) │
│  → RMS, mean, spike_score, trip_frequency, protection    │
│    event rates, voltage drop, degradation trend          │
└────────┬─────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│                StorageWriter (writer.py)                  │
│  output/<config>_<YYYYMMDD-HHMMSS>/                      │
│  ├── telemetry.parquet                                   │
│  ├── features.parquet                                    │
│  ├── labels.parquet                                      │
│  ├── channel_manifest.parquet                            │
│  ├── drive_cycles.parquet   (multi-cycle only)           │
│  └── config.yaml                                         │
│                                                          │
│  Fleet mode: output/fleet_<timestamp>/                   │
│  ├── fleet_manifest.parquet  (vehicle summary)           │
│  ├── fleet_config.yaml                                   │
│  ├── regions/*_weather.parquet                           │
│  └── vehicles/v0001...vNNNN/ (per-vehicle files)         │
└────────┬─────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│              Streamlit Dashboard (dashboard_app.py)     │
│  6-tab modular UI: Fleet, Overview, Signals, Features,  │
│  Fault & Protection, Config                              │
│  Data-source aware: synthetic / bench / HIL / production │
└──────────────────────────────────────────────────────────┘
```

---

## Module Responsibilities

### `efuse_datagen/schemas/telemetry.py` — Data Contracts

All Pydantic models and enums that define the vocabulary of the system. Nothing in the codebase creates a DataFrame column or injects a fault without referencing a type defined here.

Key types:
- **`EFuseFamily`** — 18 supported IC families (enum)
- **`EFuseProfile`** — Electrical/thermal parameters for one IC: Rds_on, I_max, ISENSE ratio, ADC bits, protection thresholds
- **`ChannelMeta`** — ~50 fields defining one eFuse channel: which IC, what load, duty cycle, ambient temp, noise profile
- **`FaultType`** — 16 fault categories (enum)
- **`FaultInjection`** — fault placement: channel, type, start time, duration, intensity
- **`ProtectionEvent`** — SCP, I2T, LATCH_OFF, THERMAL_SHUTDOWN, OPEN_LOAD_DIAG, OVER_VOLTAGE
- **`TelemetryRecord`** — one sample: timestamp, channel_id, current_a, voltage_v, temperature_c, state_on_off, protection_event, …

### `efuse_datagen/config/catalog.py` — eFuse IC Library

`EFUSE_CATALOG` is a dict of 19 `EFuseProfile` instances — the parametric database of real eFuse ICs. `example_topology()` returns the 65-channel 4-zone BEV specification. `build_channels()` expands compact topology specs into full `ChannelMeta` objects with catalog lookup and per-channel randomisation.

### `efuse_datagen/config/models.py` — Configuration Hierarchy

Pydantic models for YAML config parsing:
- `GeneratorConfig` — top-level: wraps simulation, features, storage, and optional fleet config
- `SimulationConfig` — scenario_id, duration, sample interval, channels, faults, power states, seed
- `DriveCycleConfig` — multi-cycle scheduling parameters (days, trip distribution, ambient, fault rates)
- `FleetConfig` — fleet-level settings: archetypes, regions, vehicle count, days
- `FaultRateConfig` — per-fault-type Poisson rates (events per vehicle-hour)
- `FeatureConfig` — rolling window tuning
- `StorageConfig` — output format and directory

### `efuse_datagen/simulation/generator.py` — Signal Synthesis Engine

The core of the system. `TelemetryGenerator.generate()` loops over channels and time steps, applying a 10-stage pipeline:

1. **Bus voltage** — slow drift (mHz correlated noise) around 13.8 V nominal
2. **Nominal current + composite noise** — 1/f pink + ADC quantization + thermal (Johnson-Nyquist) + EMI burst
3. **Load turn-on transient** — load-type-specific inrush (motor 5×, capacitive 8×, etc.)
4. **Voltage from bus − harness drop** — V_load = V_bus − I × (R_harness + R_connector)
5. **Power-state gating** — SLEEP → dark current (μA), CRANK → reduced voltage, ACTIVE → normal
6. **Duty-cycle gating** — periodic on/off for loads like wiper motors or PTC heaters
7. **Fault waveform injection** — 16 fault-type-specific waveform generators
8. **RC thermal model** — T_junction tracks I²×Rds_on with Rds_on tempco feedback loop
9. **ISENSE chain + ADC quantization** — k_ILIS(T) × I × R_ILIS (±tolerance) then round-to-LSB
10. **CAN signal packing** — second quantization layer (0.01 A/bit, 0.01 V/bit) for CAN-sourced channels

**Protection model** runs in parallel with fault injection:
- **SCP comparator** → immediate trip when I > threshold
- **Current limiting (I_CL)** → IC clamps output at I_CL before F(i,t) trips
- **F(i,t) energy integral** → trip after ∫I²dt exceeds threshold
- Retry N times → then latch-off

### `efuse_datagen/simulation/drive_cycles.py` — Multi-Cycle Orchestrator

`DriveCyclePlanner` creates a realistic month-long driving calendar:
- Poisson process for daily trip count
- Log-normal trip durations
- Mean-reverting temperature trajectory (seasonal variation)
- Automatic power-state sequences per cycle (SLEEP → CRANK → ACTIVE → SLEEP)

`distribute_faults()` assigns stochastic faults to cycles via Poisson rates, with progressive wear scaling for aging fault types.

`generate_multi_cycle()` orchestrates per-cycle `TelemetryGenerator` calls with `SeedSequence`-derived child seeds for reproducibility, then shifts timestamps and concatenates into a single DataFrame.

### `efuse_datagen/features/engine.py` — Feature Extraction

Rolling-window statistics grouped by `(channel_id, drive_cycle_id)`:
- Current: RMS, mean, max, min
- Temperature: slope (rate of change)
- Anomaly: spike_score (σ above baseline), trip_frequency, recovery_time_s
- Degradation: linear slope of rolling mean current
- Protection: per-mechanism event counts (SCP, I²T, latch-off, thermal shutdown, open load, over-voltage)
- Voltage: rolling min/max, voltage drop (connector aging surrogate)

Grouping by drive_cycle_id prevents rolling windows from spanning across ignition boundaries.

### `efuse_datagen/storage/writer.py` — Output Persistence

Writes Parquet (default), CSV, or JSON. Handles:
- List column serialisation (→ JSON strings) for Parquet round-trip fidelity
- `channel_manifest.parquet` — topology metadata for dashboard consumption
- `drive_cycles.parquet` — cycle-level metadata
- Disk space check before writes

### `efuse_datagen/cli.py` — CLI Entry Points

Typer-based. Entry points:
- **`efuse-gen`** — Synthetic data generation. Auto-detects single-cycle, multi-cycle, or fleet from config. Fleet mode generates multiple vehicles in parallel. Output directories are named `<config>_<YYYYMMDD-HHMMSS>`.
- **`efuse-ingest`** — Measurement data ingestion. Accepts a file or directory with column mapping, writes standard run directory.

### `efuse_datagen/ingestion/` — Measurement Data Ingestion

`MeasurementAdapter` loads real-world recordings (CSV, Parquet, MDF/MF4, BLF/ASC CAN logs) and maps them into the standard telemetry schema via configurable column mapping. `save_as_run()` writes the result in the same run directory format the generator produces, so the dashboard and all analysis tools work without modification.

`DataSource.detect()` inspects a run directory and returns `synthetic`, `bench`, `hil`, or `production` — used by the dashboard to display a data-source badge.

### `efuse_datagen/analysis/hardware_harness.py` — Hardware Analysis

Data-agnostic analysis functions that work on any telemetry (synthetic or real):
- **IC benchmarking** — per-channel thermal headroom, power dissipation, trip counts
- **Wiring/connector sizing** — voltage drop vs harness resistance, gauge adequacy
- **Thermal headroom** — peak junction temperature vs thermal shutdown threshold

### `dashboard/app.py` — Visualisation

6-tab modular Streamlit dashboard (5 standard + Fleet tab for fleet runs). Slim orchestrator `dashboard_app.py` delegates to tab modules in `efuse_datagen/dashboard/tabs/`. Shared utilities (data loaders, fault palette, data-source detection) live in `_shared.py`. Sidebar: run selector (with 🚛 prefix for fleet runs), data-source badge, vehicle selector (fleet mode), zone filter, day filter (multi-cycle), channel multi-select with load name labels.

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Pydantic for all data models | Strict validation at config load time; catches invalid eFuse parameters before simulation starts |
| Parquet as default output | Columnar, compressed, type-preserving; efficient for pandas/Spark/DuckDB downstream |
| Per-channel loop (not vectorised matrix) | Each channel has different eFuse profile, fault timing, protection state machine; vectorising would obscure the physics |
| SeedSequence for multi-cycle | Each cycle gets a deterministic child seed — reproducible even if cycle count changes |
| Rolling features grouped by cycle boundary | Prevents false anomaly signals from window spanning sleep→active transition |
| Channel manifest as separate file | Decouples topology metadata from time-series data; dashboard reads manifest once, filters efficiently |
| 1 s default sample interval for month-long runs | 100 ms would produce ~100 M rows for 30 days; 1 s balances fidelity vs tractability |

---

## Extensibility Points

- **Add an eFuse IC:** Add entry to `EFUSE_CATALOG` in `catalog.py`
- **Add a fault type:** Add enum to `FaultType`, add waveform method to `TelemetryGenerator`, add to `FaultRateConfig`
- **Add a vehicle topology:** Create new `*_topology()` function in `catalog.py`
- **Add a feature:** Add computation in `FeatureEngine.compute()`
- **Add a dashboard tab:** Create a module in `efuse_datagen/dashboard/tabs/`, add a `render(**ctx)` function, register in `dashboard_app.py` tab list
- **Add an output format:** Extend `StorageWriter` format dispatch
- **Add a measurement format:** Add a `_read_*` method to `MeasurementAdapter` in `ingestion/`
