# eFuse Telemetry Generator

Synthetic eFuse telemetry generator for Battery Electric Vehicle (BEV) Zone Controller architectures. Produces physics-grounded, labelled datasets for eFuse protection algorithm development, ML training, and validation — without lab hardware or OEM data.

Supports single-cycle quick runs and **month-long multi-cycle drive simulations** with stochastic fault injection, progressive aging, and realistic daily driving patterns.

The package is distributed as a **full runtime package**: library, CLI, built-in sample configs, and dashboard launcher.

> **Documentation:** See [`docs/`](docs/) for architecture deep-dive, data model reference, configuration guide, onboarding materials, [**eFuse domain reference**](docs/domain-reference.md) (for hardware engineers), [**signal-chain one-pager**](docs/signal-chain-one-pager.md) (for stakeholders), and [**use-case library**](docs/use-cases/README.md).

## What It Generates

| File | Contents |
|------|----------|
| `telemetry.parquet` | Per-sample eFuse signals: current, voltage, temperature, state, protection events |
| `features.parquet` | Rolling derived features: RMS current, spike score, temperature slope, trip frequency, degradation trend, voltage drop |
| `labels.parquet` | Ground-truth fault windows — channel_id, fault_type, severity, start/end timestamps |
| `channel_manifest.parquet` | Channel metadata: zone_id, load_name, eFuse family, nominal/max current, duty cycle |
| `drive_cycles.parquet` | Drive cycle metadata: cycle_id, day, start/end time, duration, ambient temp, drive type *(multi-cycle only)* |
| `config.yaml` | Full scenario config snapshot for exact reproducibility |

## Key Capabilities

### Physics Models

- **RC thermal model** — junction temperature with Rds,on positive feedback loop (PROFET+2 / VIPower tempco)
- **ISENSE sensing chain** — k_ILIS tempco + R_ILIS manufacturing tolerance (frozen per-unit scatter)
- **Dual protection + current limiting** — F(i,t) energy integral + SCP comparator + I_CL active current clamp → trip → cooldown → retry → latch-off
- **CAN signal packing** — second quantization layer (0.01 A/bit, 0.01 V/bit) models CAN-transported resolution loss
- **Composite noise** — 1/f pink noise + ADC quantization + thermal noise + sporadic EMI spikes
- **Bus voltage events** — jump-start (16–24 V), load dump (ISO 16750-2, ~40 V spike), cold crank (7–9 V sag)
- **Connector aging** — fretting corrosion model: R_c(t) = R_c0 × (1 + k × t²)
- **Die thermal coupling** — cross-channel substrate heat transfer for co-packaged eFuse ICs
- **Power-state gating** — SLEEP/CRANK/ACTIVE/ACCESSORY states with inrush and dark current
- **Duty-cycle gating** — periodic on/off cycling for intermittent loads (wiper motors, PTC heaters, etc.)

### eFuse IC Catalog (19 Families)

Parametric models for Infineon PROFET+2 (BTS7002, BTS7004, BTS7006, BTS7008, BTS70041, BTS70061, BTS70081), Infineon TLE multi-channel (TLE9104SH), Infineon high-current BTS (BTS81000), ST VIPower (VN7140AJ, VND7020AJ, VNH7013AY, VNL5050, VND5025), and CUSTOM. Each entry defines: Rds,on, I_max, I_trip ranges, ISENSE ratio, ADC resolution, blanking time, retry count, F(i,t) threshold, and thermal parameters.

### 16 Fault Types

| Fault | Description |
|-------|-------------|
| `overload_spike` | Exponential rise to overcurrent, triggers SCP/F(i,t) trip |
| `intermittent_overload` | Damped oscillation — repeated overcurrent bursts |
| `voltage_sag` | Exponential bus voltage drop (battery under heavy load) |
| `thermal_drift` | Gradual current increase from insulation breakdown |
| `noisy_sensor` | Burst EMI noise on current/voltage sense lines |
| `dropped_packet` | CAN frame loss — NaN samples (40% drop rate) |
| `gradual_degradation` | Slow exponential current ramp (aging load) |
| `connector_aging` | Fretting corrosion — rising contact resistance, falling load voltage |
| `open_load` | Wire break — near-zero current, gate ON, DIAG flag |
| `jump_start` | External booster → bus rises to 16–24 V |
| `load_dump` | Alternator field collapse → 40 V spike, exponential decay |
| `cold_crank` | Starter engaged → bus sags to 7–9 V |
| `thermal_coupling` | Die-neighbour heat injection — gentle temp rise |
| `wake_transient` | SLEEP→ACTIVE inrush spike above nominal |
| `ground_offset` | Corroded GND bond — V/I biased high (measurement offset) |
| `short_to_ground` | Wire-to-chassis short — I spike + V collapse, protection trips |

### Multi-Cycle Drive Simulation

Generate month-long datasets with realistic driving patterns:

- **Poisson trip scheduling** — configurable mean trips/day, no-drive-day probability
- **Log-normal trip durations** — median, min, max trip length tuning
- **Mean-reverting ambient temperature** — daily/seasonal variation
- **Stochastic fault injection** — Poisson rate per vehicle-hour per fault type
- **Progressive aging** — connector_aging and gradual_degradation intensify with accumulated driving hours
- **Cold-crank gating** — only fires when ambient < 5°C

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"            # generator + tests
pip install -e ".[dev,dashboard]"  # includes packaged Streamlit dashboard
```

Requires Python ≥ 3.10.

## Usage

### Single-Cycle Mode

```bash
# Default 3-channel mixed-fault demo (60 s)
efuse-gen

# List packaged configs
efuse-gen --list-configs

# 65-channel full ZC topology (300 s, 21 fault injections)
efuse-gen --config single_drive

# Override duration and seed
efuse-gen --config quick_demo --duration 120 --seed 99

# CSV output
efuse-gen --config quick_demo --format csv

# Filesystem paths still work too
efuse-gen --config ./my-custom-scenario.yaml
```

### Multi-Cycle Mode

```bash
# 30-day mixed driving profile (~55 cycles, ~37 h driving, ~8.6 M rows)
efuse-gen --config multi_day
```

Multi-cycle mode is auto-detected when the config has `drive_cycle.enabled: true`. The CLI accepts either a filesystem path or a packaged config name (`quick_demo`, `single_drive`, `multi_day`, `fleet`, `stress_test`).

### Common Options

```
--config, -c PATH     YAML scenario config
--output, -o DIR      Root output directory (default: output/)
--format, -f FORMAT   parquet | csv (default: parquet)
--duration, -d FLOAT  Override duration in seconds (single-cycle only)
--seed, -s INT        Override random seed
--json-log            Structured JSON logging
```

Output is written to `output/<config>_<YYYYMMDD-HHMMSS>/` — each run is isolated and named after the config used.

## Quickstart

```bash
python examples/quickstart.py
```

## Dashboard

Interactive Streamlit dashboard for exploring generated data.

```bash
pip install -e ".[dashboard]"
efuse-dashboard
# Opens at http://localhost:8501 and reads ./output by default
```

Alternative repo-local launch:

```bash
streamlit run dashboard/app.py
```

The dashboard reads `output/` from the current working directory by default. Set `EFUSE_TELEMETRY_OUTPUT_DIR=/path/to/output` to point it elsewhere.

| Tab | Contents |
|-----|----------|
| **📊 Overview** | KPI cards, drive cycle Gantt timeline, fault distribution pie, channel summary table |
| **📡 Signals** | Current / voltage / temperature time series with fault shading and power-off grey ribbons |
| **🔬 Features** | Rolling RMS, spike score, temperature slope, trip frequency plots with fault overlay |
| **🛡️ Fault & Protection** | Fault timeline Gantt, severity histogram, fault table, protection event rates, event heatmap |
| **📋 Config** | YAML config viewer, channel inventory table, zone distribution chart |

**Sidebar:** Run selector, data source banner (synthetic / bench / HIL / production), zone filter (from channel manifest), day filter (multi-cycle), channel multi-select with load name labels.

## Measurement Data Ingestion

Ingest real bench, HIL, or production recordings into the same run format the generator produces — so the dashboard and analysis pipeline work identically on real data.

```bash
# Single file with column mapping
efuse-ingest recording.csv \
  --map "I_ch01=current_a,U_bat=voltage_v,T_junc=temperature_c" \
  --channel ch_001

# Directory of per-channel CSVs (channel_id derived from filenames)
efuse-ingest bench_data/ --glob "*.csv"

# Tag the data source
efuse-ingest hil_capture.parquet --source-tag hil
```

Supported formats: CSV/TSV, Parquet, MDF/MF4 (requires `asammdf`), BLF/ASC CAN logs (requires `python-can` + `cantools`).

Ingested runs appear in the dashboard alongside synthetic runs, with a data-source badge in the sidebar.

## Built-In Configs

| Config | Description |
|--------|-------------|
| [`quick_demo`](efuse_datagen/config/templates/quick_demo.yaml) | 3-channel mixed-fault demo (60 s) |
| [`single_drive`](efuse_datagen/config/templates/single_drive.yaml) | 65-channel 4-zone topology, 300 s, 21 fault injections |
| [`multi_day`](efuse_datagen/config/templates/multi_day.yaml) | 30-day multi-cycle simulation (~8.6 M rows) |
| [`fleet`](efuse_datagen/config/templates/fleet.yaml) | 100 vehicles × 90 days, parallel generation with regional weather |
| [`stress_test`](efuse_datagen/config/templates/stress_test.yaml) | All fault types on a single channel (120 s) |

## Project Structure

```
efuse_datagen/
├── schemas/telemetry.py      # Pydantic data models (ChannelMeta, EFuseProfile, FaultInjection, …)
├── config/
│   ├── models.py             # SimulationConfig, DriveCycleConfig, FaultRateConfig, FeatureConfig
│   ├── catalog.py            # eFuse IC catalog (19 families) + 65-channel BEV topology factory
│   ├── builtin.py            # Built-in config loader and registry
│   └── templates/*.yaml      # Canonical packaged scenario configs
├── dashboard_app.py          # Slim Streamlit orchestrator (delegates to tab modules)
├── dashboard_launcher.py     # efuse-dashboard entry point
├── dashboard/
│   ├── _shared.py            # Data loaders, fault palette, data-source detection
│   └── tabs/                 # One module per tab: overview, signals, features, protection, config
├── simulation/
│   ├── generator.py          # TelemetryGenerator — signal synthesis, fault waveforms, protection
│   └── drive_cycles.py       # DriveCyclePlanner — schedule, fault distribution, multi-cycle orchestration
├── features/engine.py        # FeatureEngine — rolling statistics, anomaly scores
├── storage/writer.py         # StorageWriter — Parquet/CSV/JSON output + manifest
├── ingestion/                # MeasurementAdapter — load real bench/HIL/production data
├── analysis/
│   └── hardware_harness.py   # IC benchmarking, wiring sizing, thermal headroom (data-agnostic)
├── cli.py                    # Typer CLI: efuse-gen + efuse-ingest entry points
└── utils/logging.py          # Logging configuration
dashboard/
└── app.py                    # Repo compatibility wrapper for the packaged dashboard
docs/                         # Architecture, data model, configuration, and onboarding docs
tests/                        # 92 pytest tests
examples/
└── quickstart.py             # Minimal end-to-end example
```

## Tests

```bash
pytest                  # Run all 92 tests
pytest -v               # Verbose
pytest --cov=efuse_datagen  # With coverage
```

## License

MIT License. See [LICENSE](LICENSE) for details.