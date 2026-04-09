# Quickstart — Installing from PyPI

This guide is for users installing the published package from PyPI. For contributor/developer setup, see the [README](../README.md) or [onboarding guide](onboarding.md).

---

## 1. Install

```bash
pip install efuse-telemetry-generator
```

To include the interactive Streamlit dashboard:

```bash
pip install "efuse-telemetry-generator[dashboard]"
```

Requires **Python ≥ 3.10**.

---

## 2. Generate Your First Dataset

The package installs three CLI commands: `efuse-gen`, `efuse-ingest`, and `efuse-dashboard`.

Run a quick 3-channel demo (60 seconds of synthetic telemetry):

```bash
efuse-gen --config quick_demo
```

Output lands in `output/quick_demo_<YYYYMMDD-HHMMSS>/` with these files:

| File | Contents |
|------|----------|
| `telemetry.parquet` | Per-sample eFuse signals: current, voltage, temperature, state, protection events |
| `features.parquet` | Rolling derived features: RMS current, spike score, temperature slope, etc. |
| `labels.parquet` | Ground-truth fault windows with fault type, severity, and timestamps |
| `channel_manifest.parquet` | Channel metadata: zone, load name, eFuse family, nominal/max current |
| `config.yaml` | Full config snapshot for reproducibility |

---

## 3. Explore the Data

Launch the dashboard (requires the `[dashboard]` extra):

```bash
efuse-dashboard
```

Opens at `http://localhost:8501`. Select your run from the sidebar and walk through the tabs: Overview → Signals → Features → Fault & Protection → Config.

Or load the data directly in Python:

```python
import pandas as pd

run = "output/quick_demo_20260409-120000"   # adjust to your actual run path
telem = pd.read_parquet(f"{run}/telemetry.parquet")
labels = pd.read_parquet(f"{run}/labels.parquet")

print(telem.head())
print(labels)
```

---

## 4. Built-In Configs

List all packaged scenarios:

```bash
efuse-gen --list-configs
```

| Config | Description |
|--------|-------------|
| `quick_demo` | 3-channel mixed-fault demo (60 s) |
| `single_drive` | 65-channel 4-zone topology, 300 s, 21 fault injections |
| `multi_day` | 30-day multi-cycle simulation (~8.6 M rows) |
| `fleet` | 100 vehicles × 90 days, parallel generation with regional weather |
| `stress_test` | All fault types on a single channel (120 s) |

Run any of them:

```bash
efuse-gen --config single_drive
efuse-gen --config multi_day
efuse-gen --config fleet --vehicles 3 --days 3
```

---

## 5. Common CLI Options

```
efuse-gen [OPTIONS]

--config, -c NAME     Built-in config name or path to a custom YAML file
--output, -o DIR      Root output directory (default: output/)
--format, -f FORMAT   parquet | csv (default: parquet)
--duration, -d FLOAT  Override duration in seconds (single-cycle only)
--seed, -s INT        Override random seed for reproducibility
--json-log            Emit structured JSON logs
--list-configs        List available built-in configs and exit
```

---

## 6. Ingest Real Measurement Data

Bring in bench, HIL, or production recordings so they appear alongside synthetic runs in the dashboard:

```bash
efuse-ingest recording.csv \
  --map "I_ch01=current_a,U_bat=voltage_v,T_junc=temperature_c" \
  --channel ch_001
```

Supported formats: CSV/TSV, Parquet, MDF/MF4 (requires `asammdf`), BLF/ASC CAN logs (requires `python-can` + `cantools`).

---

## 7. Use as a Python Library

```python
from efuse_datagen.config.builtin import load_bundled_config
from efuse_datagen.features.engine import FeatureEngine
from efuse_datagen.simulation.generator import TelemetryGenerator

# Load a scenario
platform = load_bundled_config("quick_demo")

# Generate telemetry + fault labels
gen = TelemetryGenerator(platform.simulation)
telemetry_df, labels_df = gen.generate()

# Compute rolling features
engine = FeatureEngine(platform.features)
features_df = engine.compute(telemetry_df)

print(f"Telemetry: {len(telemetry_df):,} rows")
print(f"Features:  {len(features_df):,} rows")
print(f"Faults:    {len(labels_df):,} labelled windows")
```

---

## 8. Custom Scenarios

Create your own YAML config and pass it to the CLI:

```bash
efuse-gen --config ./my-scenario.yaml
```

See the [configuration guide](configuration.md) for the full schema reference, and inspect the [built-in templates](../efuse_datagen/config/templates/) for working examples.

---

## Further Reading

- [Configuration Guide](configuration.md) — full YAML schema and parameter reference
- [Data Model](data-model.md) — column definitions for every output file
- [Architecture](architecture.md) — how the signal chain and simulation pipeline work
- [Drive Cycles](drive-cycles.md) — multi-cycle and fleet simulation details
- [Domain Reference](domain-reference.md) — eFuse hardware background for engineers
- [Dashboard Guide](dashboard.md) — detailed dashboard tab walkthrough
