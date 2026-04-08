# Onboarding & Handover

This document is for engineers joining the project or receiving a handover. It covers: what the tool does, why it exists, how to get productive quickly, and where to look when something breaks.

---

## What This Project Is

**eFuse Telemetry Generator** creates synthetic telemetry for automotive eFuse protection systems — the solid-state switches replacing traditional blade fuses in modern Battery Electric Vehicles (BEVs).

It generates realistic current, voltage, and temperature signals for up to 65 eFuse channels across 4 vehicle zones, with:
- Physically modelled noise, thermal dynamics, and sensing chain errors
- 16 injectable fault types with ground-truth labels
- Single-cycle (seconds to minutes) and multi-cycle (days to months) modes
- An interactive Streamlit dashboard for visual analysis

**Primary consumers:**
- ML/analytics teams training anomaly detection and degradation models
- Protection algorithm engineers validating SCP/F(i,t) threshold settings
- Test bench engineers needing stimulation data for HIL setups
- Product managers needing demo data for eFuse team reviews

---

## Getting Started

### 1. Clone & Install

```bash
git clone https://github.com/jayaprakash87/efuse-telemetry-generator.git
cd efuse-telemetry-generator
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,dashboard]"
```

### 2. Run the Demo

```bash
efuse-gen --config quick_demo
```

This generates a 3-channel, 60-second dataset in `output/quick_demo_<timestamp>/`. Takes under 2 seconds.

### 3. Explore the Output

```bash
efuse-dashboard
```

Select the run from the sidebar. Walk through each tab: Overview → Signals → Features → Fault & Protection → Config.

### 4. Run the Full Topology

```bash
efuse-gen --config single_drive
```

65 channels, 4 zones, 300 seconds, 21 fault injections. ~195K rows, takes ~10 seconds.

### 5. Generate a Month of Data

```bash
efuse-gen --config multi_day
```

30-day multi-cycle simulation. ~55 drive cycles, ~37 hours of driving, ~8.6M rows. Takes ~2 minutes.

### 6. Generate a Fleet

```bash
efuse-gen --config fleet --vehicles 3 --days 3
```

3 vehicles across 2 regions, 3 days of driving per vehicle. ~2.9M rows total. The dashboard shows a Fleet overview tab with vehicle manifest, archetype/region breakdowns, and regional weather.

### 7. Ingest Real Measurement Data

```bash
efuse-ingest bench_recording.csv \
  --map "I_ch01=current_a,U_bat=voltage_v,T_junc=temperature_c" \
  --channel ch_001
```

This creates a standard run directory from your bench CSV. The dashboard shows it alongside synthetic runs with a 🔬 Bench Recording badge.

### 8. Run Tests

```bash
pytest -v
```

92 tests covering generation, ADC quantization, protection logic, thermal model, CAN signal packing, current limiting, and ground faults.

---

## Key Concepts to Understand

### eFuse Protection

Each channel has three protection mechanisms running in parallel:
1. **SCP (Short Circuit Protection)** — fast comparator, trips in microseconds when current exceeds a hard threshold
2. **Current Limiting (I_CL)** — IC actively clamps output current at I_CL (default 1.5× fuse rating) while F(i,t) energy continues accumulating
3. **F(i,t) (Energy Integral)** — accumulates I² over time; trips when thermal energy exceeds the silicon's limit

After a trip, the eFuse:
1. Opens the gate (current → 0)
2. Waits `cooldown_s`
3. Retries up to `max_retries` times
4. If retries exhausted → **latch-off** (permanent shutdown until ECU reset)

See [domain-reference.md](domain-reference.md) for detailed hardware theory.

### Channel Topology

The default 65-channel topology mirrors a real BEV:
- **zone_front** (18 ch): lighting, HVAC, wipers, charger, horn, suspension
- **zone_rear** (17 ch): tail lights, seat heaters, defroster, dampers, radar
- **zone_body** (15 ch): door locks, windows, mirrors, sunroof, trunk, keyless
- **zone_central** (15 ch): main PDU, battery disconnect, DC/DC, inverter, ADAS

Each channel references an eFuse IC family from the **catalog** (`catalog.py`), which provides the electrical parameters (Rds_on, ISENSE ratio, ADC resolution, protection thresholds).

### Signal Pipeline

For each channel and each time step, the generator applies (in order):
1. Bus voltage (slow drift)
2. Nominal current + composite noise (1/f + ADC + thermal + EMI)
3. Load turn-on transient (inrush)
4. Voltage from bus − harness drop
5. Power-state gating (SLEEP/CRANK/ACTIVE)
6. Duty-cycle gating (on/off patterns for intermittent loads)
7. Fault waveform (if active) — 16 fault types
8. RC thermal model (junction temperature)
9. ISENSE chain + ADC quantization (sense current with tolerance/tempco errors)
10. CAN signal packing (0.01 A/bit, 0.01 V/bit for CAN-sourced channels)

### Multi-Cycle Mode

Single-cycle mode generates one continuous time series. Multi-cycle mode simulates many ignition cycles over days/weeks:
- Each cycle has its own ambient temperature, power-state sequence, and faults
- Faults are injected stochastically (Poisson rates)
- Aging faults intensify over accumulated driving hours
- Feature rolling windows respect cycle boundaries

See [drive-cycles.md](drive-cycles.md) for the full deep-dive.

---

## Codebase Walkthrough

| File | What to Look At |
|------|-----------------|
| [`efuse_datagen/schemas/telemetry.py`](../efuse_datagen/schemas/telemetry.py) | All data types. Start here to understand the vocabulary. |
| [`efuse_datagen/config/catalog.py`](../efuse_datagen/config/catalog.py) | eFuse IC parameters + vehicle topology. Read `EFUSE_CATALOG` and `example_topology()`. |
| [`efuse_datagen/config/models.py`](../efuse_datagen/config/models.py) | Config hierarchy. Read `GeneratorConfig` to see what the YAML maps to. |
| [`efuse_datagen/simulation/generator.py`](../efuse_datagen/simulation/generator.py) | Core engine. Read `_generate_channel()` — it's the 8-stage pipeline. |
| [`efuse_datagen/simulation/drive_cycles.py`](../efuse_datagen/simulation/drive_cycles.py) | Multi-cycle planner. Read `generate_schedule()` and `distribute_faults()`. |
| [`efuse_datagen/features/engine.py`](../efuse_datagen/features/engine.py) | Feature computation. Read `compute()` — one method, 20+ features. |
| [`efuse_datagen/storage/writer.py`](../efuse_datagen/storage/writer.py) | Output layer. Straightforward Parquet/CSV writes. |
| [`efuse_datagen/cli.py`](../efuse_datagen/cli.py) | CLI orchestration. Single-cycle vs multi-cycle branching logic. |
| [`efuse_datagen/dashboard_app.py`](../efuse_datagen/dashboard_app.py) | Packaged Streamlit UI. [`dashboard/app.py`](../dashboard/app.py) is only a compatibility wrapper. |
| [`efuse_datagen/config/templates/multi_day.yaml`](../efuse_datagen/config/templates/multi_day.yaml) | Best example of full multi-cycle config. Read the comments. |
| [`tests/test_simulation.py`](../tests/test_simulation.py) | Test patterns — good examples of how to call the generator programmatically. |

**Suggested reading order:** `telemetry.py` → `catalog.py` → `models.py` → `generator.py` → `cli.py` → run the demo → read the dashboard code.

---

## Common Tasks

### Add a New Fault Type

1. Add entry to `FaultType` enum in `telemetry.py`
2. Add waveform generator method in `generator.py` (follow existing pattern, e.g. `_apply_overload_spike`)
3. Add dispatch case in the fault injection loop in `_generate_channel()`
4. Add Poisson rate field to `FaultRateConfig` in `models.py`
5. Add colour to `FAULT_PALETTE` in `dashboard/_shared.py`
6. Add test case in `tests/test_simulation.py`

### Add an eFuse IC Family

1. Add enum value to `EFuseFamily` in `telemetry.py`
2. Add `EFuseProfile` entry to `EFUSE_CATALOG` in `catalog.py`
3. (Optional) Reference it from a channel in a new or existing topology

### Add a Dashboard Tab

1. Create a module in `efuse_datagen/dashboard/tabs/` with a `render(**ctx)` function
2. Register it in `dashboard_app.py` — add to the tab labels list and render block
3. The `ctx` dict includes: `tel`, `feat`, `lab`, `manifest`, `dc_df`, `selected_channels`, `channels`, `selected_run`, `label_map`, `is_multi_cycle`, `fleet_mode`, `fleet_manifest`, `fleet_weather`, `selected_vehicle`

### Create a Custom Vehicle Topology

1. Write a function in `catalog.py` returning a list of channel spec dicts (follow `example_topology()`)
2. (Or) Define channels inline in your YAML config under `simulation.channels`
3. Reference eFuse families from `EFUSE_CATALOG` via the `efuse_family` field

### Debug a Specific Channel's Output

```python
from efuse_datagen.config.models import GeneratorConfig
from efuse_datagen.simulation.generator import TelemetryGenerator

config = GeneratorConfig(
    channels=[ChannelMeta(channel_id="ch_01", nominal_current_a=6.0)],
    fault_injections=[FaultInjection(channel_id="ch_01", fault_type="overload_spike", start_s=5.0, duration_s=3.0, intensity=0.8)],
    duration_s=30.0,
)
gen = TelemetryGenerator(config)
tel_df, label_df = gen.generate()
print(tel_df[tel_df["channel_id"] == "ch_01"][["timestamp", "current_a", "protection_event"]].to_string())
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `efuse-gen: command not found` | Not installed in editable mode | `pip install -e ".[dev]"` |
| `ModuleNotFoundError: efuse_datagen` | Wrong venv or not installed | Activate `.venv`, reinstall |
| Dashboard shows empty run list | No data in `output/` | Run `efuse-gen` first |
| Dashboard missing zone filter | No `channel_manifest.parquet` | Re-generate with current code |
| Multi-cycle takes very long | Too many days or fine sample interval | Use `sample_interval_ms: 1000` for long runs |
| `SeedSequence` error | NumPy < 1.24 | `pip install "numpy>=1.24"` |
| Protection never trips | Fault intensity too low, or channel max_current_a too high | Increase intensity or lower max_current_a |

---

## Documentation Index

| Document | Purpose |
|----------|---------|
| [README.md](../README.md) | Quick start, feature overview, usage examples |
| [docs/architecture.md](architecture.md) | System design, module responsibilities, data flow |
| [docs/data-model.md](data-model.md) | Output schema: every column, type, and enum |
| [docs/drive-cycles.md](drive-cycles.md) | Multi-cycle simulation deep-dive |
| [docs/configuration.md](configuration.md) | Complete YAML config reference |
| [docs/dashboard.md](dashboard.md) | Dashboard tabs, controls, and usage |
| [docs/onboarding.md](onboarding.md) | This document — getting started and handover |
