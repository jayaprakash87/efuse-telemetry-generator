# VIP Data Generator

Standalone synthetic eFuse telemetry generator for Zone Controller (ZC) architecture validation and eFuse team alignment.

Produces physically grounded, labelled datasets without requiring lab hardware or OEM data.

## What It Generates

| File | Contents |
|------|----------|
| `telemetry.parquet` | Raw per-sample eFuse signals: current, voltage, temperature, state, protection events |
| `features.parquet` | Rolling derived features: RMS current, spike score, temperature slope, trip frequency, degradation trend, voltage drop |
| `labels.parquet` | Ground-truth fault windows — channel_id, fault_type, severity, start/end timestamp |
| `config.yaml` | Full scenario config snapshot for exact reproducibility |

## Physics Models

- **RC thermal model** — junction temperature with PROFET+2 Rds,on positive feedback loop
- **ISENSE sensing chain** — k_ILIS tempco + R_ILIS manufacturing tolerance (frozen per-unit scatter)
- **Protection cycles** — F(i,t) energy integral + SCP comparator → trip → cooldown → retry → latch-off
- **Composite noise** — 1/f pink noise + ADC quantization + thermal noise + sporadic EMI spikes
- **Abnormal bus voltage** — jump-start (16–24 V), load dump (ISO 16750-2, ~40 V spike), cold crank (7–9 V sag)
- **Wire harness + connector aging** — fretting corrosion model: R_c(t) = R_c0 × (1 + k × t²)
- **Die thermal coupling** — cross-channel substrate heat transfer for co-packaged eFuse ICs
- **Sleep/wake power states** — KL30/KL15/KLR/KL50 gating with configurable inrush and quiescent dark current

## Fault Types

| Fault | Description |
|-------|-------------|
| `overload_spike` | Exponential rise to overcurrent, eFuse trips |
| `intermittent_overload` | Damped oscillation — repeated overcurrent bursts |
| `voltage_sag` | Exponential bus voltage drop (battery under heavy load) |
| `thermal_drift` | Gradual current increase from insulation breakdown |
| `noisy_sensor` | Burst EMI noise on current/voltage sense lines |
| `dropped_packet` | CAN frame loss — NaN samples (40% drop rate during window) |
| `gradual_degradation` | Slow exponential current ramp (aging load) |
| `connector_aging` | Fretting corrosion — rising contact resistance, falling load voltage |
| `open_load` | Wire break — near-zero current, gate ON, DIAG flag after blank time |
| `jump_start` | External booster → bus rises to 16–24 V |
| `load_dump` | Alternator field collapse → 40 V spike, exponential decay |
| `cold_crank` | Starter engaged → bus sags to 7–9 V |
| `thermal_coupling` | Die-neighbour heat injection — gentle temp rise, no trip |
| `wake_transient` | SLEEP→ACTIVE inrush spike above nominal |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"          # generator + tests
pip install -e ".[dev,dashboard]"  # also includes Streamlit dashboard
```

## Usage

```bash
# Default 3-channel mixed-fault demo
vip-gen

# Specific scenario config
vip-gen --config configs/default.yaml

# 65-channel full ZC topology
vip-gen --config configs/example_65ch.yaml

# Override duration and seed
vip-gen --config configs/default.yaml --duration 120 --seed 99

# CSV output
vip-gen --config configs/default.yaml --format csv

# Custom output directory
vip-gen --config configs/default.yaml --output /tmp/efuse_data/

# Structured JSON logs
vip-gen --config configs/default.yaml --json-log
```

Output is written to `output/<YYYYMMDD-HHMMSS-xxxx>/` — each run is isolated.

## Quickstart

```bash
python examples/quickstart.py
```

## Dashboard

Interactive Streamlit dashboard for exploring generated data — intended for eFuse team demos.

```bash
# Install dashboard dependencies (one-time)
pip install -e ".[dashboard]"

# Generate some data first
vip-gen --duration 120

# Launch
streamlit run dashboard/app.py
# Opens at http://localhost:8501
```

| Tab | Contents |
|-----|----------|
| **Overview** | KPI cards, fault-type distribution, per-channel fault exposure, channel summary table |
| **Telemetry** | Current / voltage / temperature time series with fault windows shaded by type |
| **Features** | Configurable rolling-feature plots (RMS, spike score, temp slope, trip frequency, …) |
| **Fault Analysis** | Gantt fault timeline, severity histogram, fault window table |
| **Protection Events** | Event rate over time, SCP/I2T/latch-off/thermal shutdown counts, multi-channel heatmap |

The sidebar lets you select any run from `output/` and filter to specific channels.

## Scenario Configs

| Config | Description |
|--------|-------------|
| `configs/default.yaml` | 3-channel mixed-fault demo (overload, thermal drift, degradation, voltage sag) |
| `configs/nominal.yaml` | Clean baseline — no faults injected |
| `configs/stress_test.yaml` | All fault types on a single channel |
| `configs/example_65ch.yaml` | Full 4-zone, 65-channel ZC topology |
| `configs/xcp_test_bench.yaml` | XCP dual-raster (10 ms current + 50 ms temperature) |
| `configs/production_can.yaml` | Production CAN rates (50–100 ms) |

## Tests

```bash
pytest tests/ -v      # 31 generator tests
```

## Project Structure

```
vip_datagen/
├── schemas/telemetry.py     # Pydantic models: ChannelMeta, FaultType, PowerState, ProtectionEvent, …
├── config/
│   ├── models.py            # SimulationConfig, FeatureConfig, PowerStateEvent, load_config()
│   └── catalog.py           # eFuse IC catalog (17 families), 4-zone vehicle topology factory
├── simulation/generator.py  # Physics-based telemetry generator
├── features/engine.py       # Rolling feature computation (RMS, spike score, temp slope, …)
├── storage/writer.py        # Parquet / CSV output
├── utils/logging.py         # Structured logging with run_id correlation
└── cli.py                   # vip-gen CLI (Typer)

dashboard/app.py             # Streamlit dashboard (5 tabs, Plotly charts)
configs/                     # Scenario YAML files
examples/                    # quickstart.py
tests/                       # 31 generator tests
```