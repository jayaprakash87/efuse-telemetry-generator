# VIP Data Generator

Synthetic eFuse telemetry generator for Battery Electric Vehicle (BEV) Zone Controller architectures. Produces physics-grounded, labelled datasets for eFuse protection algorithm development, ML training, and validation — without lab hardware or OEM data.

Supports single-cycle quick runs and **month-long multi-cycle drive simulations** with stochastic fault injection, progressive aging, and realistic daily driving patterns.

> **Documentation:** See [`docs/`](docs/) for architecture deep-dive, data model reference, configuration guide, and onboarding materials.

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
- **Dual protection** — F(i,t) energy integral + SCP comparator → trip → cooldown → retry → latch-off
- **Composite noise** — 1/f pink noise + ADC quantization + thermal noise + sporadic EMI spikes
- **Bus voltage events** — jump-start (16–24 V), load dump (ISO 16750-2, ~40 V spike), cold crank (7–9 V sag)
- **Connector aging** — fretting corrosion model: R_c(t) = R_c0 × (1 + k × t²)
- **Die thermal coupling** — cross-channel substrate heat transfer for co-packaged eFuse ICs
- **Power-state gating** — SLEEP/CRANK/ACTIVE/ACCESSORY states with inrush and dark current
- **Duty-cycle gating** — periodic on/off cycling for intermittent loads (wiper motors, PTC heaters, etc.)

### eFuse IC Catalog (19 Families)

Parametric models for Infineon PROFET+2 (BTS7002, BTS7004, BTS7006, BTS7008, BTS70041, BTS70061, BTS70081), Infineon TLE multi-channel (TLE9104SH), Infineon high-current BTS (BTS81000), ST VIPower (VN7140AJ, VND7020AJ, VNH7013AY, VNL5050, VND5025), and CUSTOM. Each entry defines: Rds,on, I_max, I_trip ranges, ISENSE ratio, ADC resolution, blanking time, retry count, F(i,t) threshold, and thermal parameters.

### 14 Fault Types

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
pip install -e ".[dev,dashboard]"  # includes Streamlit dashboard
```

Requires Python ≥ 3.10.

## Usage

### Single-Cycle Mode

```bash
# Default 3-channel mixed-fault demo (60 s)
vip-gen

# 65-channel full ZC topology (300 s, 21 fault injections)
vip-gen --config configs/zone_controller_full.yaml

# Override duration and seed
vip-gen --config configs/default.yaml --duration 120 --seed 99

# CSV output
vip-gen --config configs/default.yaml --format csv
```

### Multi-Cycle Mode

```bash
# 30-day mixed driving profile (~55 cycles, ~37 h driving, ~8.6 M rows)
vip-gen --config configs/one_month.yaml
```

Multi-cycle mode is auto-detected when the config has `drive_cycle.enabled: true`. The CLI shows a Rich progress bar during generation.

### Common Options

```
--config, -c PATH     YAML scenario config
--output, -o DIR      Root output directory (default: output/)
--format, -f FORMAT   parquet | csv (default: parquet)
--duration, -d FLOAT  Override duration in seconds (single-cycle only)
--seed, -s INT        Override random seed
--json-log            Structured JSON logging
```

Output is written to `output/<YYYYMMDD-HHMMSS-xxxxx>/` — each run is isolated.

## Quickstart

```bash
python examples/quickstart.py
```

## Dashboard

Interactive Streamlit dashboard for exploring generated data.

```bash
pip install -e ".[dashboard]"
streamlit run dashboard/app.py
# Opens at http://localhost:8501
```

| Tab | Contents |
|-----|----------|
| **📊 Overview** | KPI cards, drive cycle Gantt timeline, fault distribution pie, per-channel fault exposure, channel summary table |
| **📡 Telemetry** | Current / voltage / temperature time series with fault shading and power-off grey ribbons |
| **🔬 Features** | Rolling RMS, spike score, temperature slope, trip frequency, recovery time plots |
| **⚠️ Fault Analysis** | Fault heatmap by channel/time, severity histogram, intensity correlation |
| **🛡️ Protection Events** | Per-mechanism timeline (SCP, I²T, latch-off, thermal shutdown), reset counter scatter |
| **📋 Config** | YAML config viewer, channel inventory table, zone distribution chart |

**Sidebar:** Run selector, zone filter (from channel manifest), day filter (multi-cycle), channel multi-select with load name labels. Limits display to 8 channels for performance.

## Scenario Configs

| Config | Description |
|--------|-------------|
| [`configs/default.yaml`](configs/default.yaml) | 3-channel mixed-fault demo (60 s) |
| [`configs/zone_controller_full.yaml`](configs/zone_controller_full.yaml) | 65-channel 4-zone topology, 300 s, 21 fault injections |
| [`configs/one_month.yaml`](configs/one_month.yaml) | 30-day multi-cycle simulation (~8.6 M rows) |
| [`configs/stress_test.yaml`](configs/stress_test.yaml) | All fault types on a single channel (120 s) |

## Project Structure

```
vip_datagen/
├── schemas/telemetry.py      # Pydantic data models (ChannelMeta, EFuseProfile, FaultInjection, …)
├── config/
│   ├── models.py             # SimulationConfig, DriveCycleConfig, FaultRateConfig, FeatureConfig
│   └── catalog.py            # eFuse IC catalog (19 families) + 65-channel BEV topology factory
├── simulation/
│   ├── generator.py          # TelemetryGenerator — signal synthesis, fault waveforms, protection
│   └── drive_cycles.py       # DriveCyclePlanner — schedule, fault distribution, multi-cycle orchestration
├── features/engine.py        # FeatureEngine — rolling statistics, anomaly scores
├── storage/writer.py         # StorageWriter — Parquet/CSV/JSON output + manifest
├── cli.py                    # Typer CLI entry point
└── utils/logging.py          # Logging configuration
dashboard/
└── app.py                    # Streamlit 6-tab dashboard
configs/                      # YAML scenario configs
docs/                         # Architecture, data model, configuration, and onboarding docs
tests/                        # 31 pytest tests
examples/
└── quickstart.py             # Minimal end-to-end example
```

## Tests

```bash
pytest                  # Run all 31 tests
pytest -v               # Verbose
pytest --cov=vip_datagen  # With coverage
```

## License

MIT License. See [LICENSE](LICENSE) for details.