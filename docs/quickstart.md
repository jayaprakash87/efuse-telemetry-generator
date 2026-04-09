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

To import topologies from Excel (.xlsx) files:

```bash
pip install "efuse-telemetry-generator[excel]"
```

Requires **Python ≥ 3.10**.

---

## 2. Generate Your First Dataset

The package installs two CLI commands: `efuse-gen` (generator + ingestion) and `efuse-dashboard` (interactive dashboard).

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
| `custom_topology` | 2-zone, 6-channel user-defined ZC — fully explicit, no catalog (120 s) |
| `custom_topology_with_catalog` | 3-zone, 8-channel user-defined ZC with IC catalog presets (180 s) |
| `single_drive` | 65-channel 4-zone reference topology, 300 s, 21 fault injections |
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
--format, -f FORMAT   parquet | csv | json (default: parquet)
--duration, -d FLOAT  Override duration in seconds (single-cycle only)
--seed, -s INT        Override random seed for reproducibility
--dry-run             Preview what would be generated without writing files
--json-log            Emit structured JSON logs
--list-configs        List available built-in configs and exit

Fleet-only options (requires a config with a fleet: section):
--vehicles, -n INT    Override fleet vehicle count
--days INT            Override fleet duration in days
--workers, -w INT     Override fleet parallel workers
--combined            Write combined fleet_telemetry.parquet
```

### Subcommands

```
efuse-gen info <CONFIG>           Show scenario summary without generating data
efuse-gen topology import <FILE>  Import CSV/Excel/Parquet → YAML topology
efuse-gen topology export <FILE>  Export YAML topology → CSV for editing
efuse-gen topology template       Generate a CSV template with example rows
efuse-gen topology new             Scaffold a topology from a bundled preset
efuse-gen ingest <SOURCE>         Ingest real measurement data into run format
```

---

## 6. Preview a Config Without Generating

Use `efuse-gen info` to inspect what a scenario contains without writing any files:

```bash
efuse-gen info quick_demo
efuse-gen info ./my_scenario.yaml
```

Shows: scenario name, mode (single/multi-cycle/fleet), channel count, zone breakdown, load types, fault injections, drive-cycle settings, fleet configuration, and output format.

---

## 7. Define Your Own Zone Controller

The generator is **topology-agnostic** — you define your zone controller architecture once, then reuse it across any number of scenarios.

### Recommended: Import from CSV / Excel

Engineers typically have their channel list in a spreadsheet. Import it directly:

```bash
# Step 1: Generate a CSV template (open in Excel / Google Sheets)
efuse-gen topology template -o my_channels.csv

# Or a minimal template with just the essential columns
efuse-gen topology template -o my_channels.csv --minimal

# Step 2: Fill in your channels in the spreadsheet, then import
efuse-gen topology import my_channels.csv -o my_vehicle.yaml
```

You can also scaffold a topology from a bundled preset:

```bash
# Compact: 2 zones, 12 channels
efuse-gen topology new -t compact -o my_prototype.yaml

# Full: 4 zones, 65 channels
efuse-gen topology new -t full -o my_production.yaml
```

Export an existing topology back to CSV for spreadsheet editing:

```bash
efuse-gen topology export my_vehicle.yaml -o channels.csv
```

The CSV has one row per eFuse channel with columns like:

| channel_id | zone_id | efuse_family | load_name | load_type | nominal_current_a | wire_gauge_mm2 | ... |
|---|---|---|---|---|---|---|---|
| ch_01 | zc_front | inf_hs_14a | headlamp_left | resistive | 6.0 | 1.0 | ... |
| ch_02 | zc_front | st_hs_30a | blower_motor | motor | 15.0 | 2.5 | ... |
| ch_03 | zc_rear | inf_hs_9a | seat_heater | ptc | 8.0 | 1.5 | ... |

Zone definitions are auto-generated from the `zone_id` column. Add optional `zone_name`, `zone_location`, `zone_bus` columns for richer metadata.

Column headers are flexible — `Ch`, `Zone`, `IC`, `Consumer`, `Gauge mm2` all work.

### Use the topology in a scenario

```yaml
# my_scenario.yaml
simulation:
  scenario_id: my_test
  topology_file: ./my_vehicle.yaml    # ← points to your imported topology
  duration_s: 300
  fault_injections:
    - channel_id: ch_01
      fault_type: overload_spike
      start_s: 20.0
      duration_s: 3.0
      intensity: 0.8
```

```bash
efuse-gen --config ./my_scenario.yaml
```

The built-in configs (`single_drive`, `multi_day`, `fleet`) use the bundled reference topology `bev_4zone_65ch` the same way.

### Alternative: Hand-written YAML topologies

For small topologies or full-explicit control, you can also define channels directly in YAML:

- **`custom_topology`** — fully explicit parameters, no catalog dependency
- **`custom_topology_with_catalog`** — uses IC catalog presets for defaults

> **Tip:** For production use, always extract the topology into a separate file so it can be shared across scenarios.

---

## 8. Ingest Real Measurement Data

Bring in bench, HIL, or production recordings so they appear alongside synthetic runs in the dashboard:

```bash
# Single file with column mapping
efuse-gen ingest recording.csv \
  --map "I_ch01=current_a,U_bat=voltage_v,T_junc=temperature_c" \
  --channel ch_001

# Directory of per-channel CSVs (channel_id derived from filenames)
efuse-gen ingest bench_data/ --glob "*.csv"

# Tag the data source
efuse-gen ingest hil_capture.parquet --source-tag hil
```

All ingest options:

```
efuse-gen ingest <SOURCE> [OPTIONS]

--output, -o DIR      Root output directory (default: output/)
--map, -m MAPPING     Column mapping as key=value pairs, e.g. 'I_ch01=current_a,U_bat=voltage_v'
--time-col NAME       Timestamp column name (default: timestamp)
--channel ID          Override channel_id (default: derived from filename)
--glob PATTERN        Glob pattern for directory sources (default: *.csv)
--source-tag TAG      Data source tag: bench, hil, or production (default: bench)
```

Supported formats: CSV/TSV, Parquet, MDF/MF4 (requires `asammdf`), BLF/ASC CAN logs (requires `python-can` + `cantools`).

---

## 9. Use as a Python Library

### One-liner: `generate()`

The top-level `generate()` function runs the full pipeline (config → simulation → features → storage) in a single call:

```python
from efuse_datagen import generate

result = generate("quick_demo")                        # built-in config name
result = generate("quick_demo", duration_s=10, seed=42) # with overrides
result = generate("./my_scenario.yaml", format="csv")   # custom YAML

# result is a dict of Path objects:
# {"telemetry": Path, "features": Path, "labels": Path,
#  "channel_manifest": Path, "config": Path}
```

You can also pass an already-loaded config object:

```python
from efuse_datagen import generate, load_bundled_config

cfg = load_bundled_config("quick_demo")
cfg.simulation.seed = 99
result = generate(cfg, output_dir="/tmp/my_run")
```

### Full control: use the building blocks directly

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

## 10. Next Steps

- Browse the [built-in templates](../efuse_datagen/config/templates/) for working config examples
- Read the [configuration guide](configuration.md) for the full YAML schema reference
- Use `efuse-gen --list-configs` to see all available built-in scenarios

---

## Further Reading

- [Configuration Guide](configuration.md) — full YAML schema and parameter reference
- [Data Model](data-model.md) — column definitions for every output file
- [Architecture](architecture.md) — how the signal chain and simulation pipeline work
- [Drive Cycles](drive-cycles.md) — multi-cycle and fleet simulation details
- [Domain Reference](domain-reference.md) — eFuse hardware background for engineers
- [Dashboard Guide](dashboard.md) — detailed dashboard tab walkthrough
