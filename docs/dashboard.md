# Dashboard Guide

The Streamlit dashboard provides interactive visualisation of generated eFuse telemetry data. It is designed for eFuse team demos, protection algorithm validation reviews, and fault analysis walkthroughs.

---

## Launch

```bash
# Install dashboard dependencies (one-time)
pip install -e ".[dashboard]"

# Generate data first
vip-gen --config configs/zone_controller_full.yaml

# Launch
streamlit run dashboard/app.py
# Opens at http://localhost:8501
```

---

## Sidebar Controls

### Run Selector

Dropdown listing all runs in the `output/` directory, sorted by recency (newest first). Select a run to load its telemetry, features, labels, and metadata.

### Zone Filter

When a `channel_manifest.parquet` is present (all current configs produce one), a zone multi-select appears. Select one or more zones to filter all tabs to channels in those zones. Available zones: `zone_front`, `zone_rear`, `zone_body`, `zone_central`.

### Day Filter (Multi-Cycle Only)

For runs produced with `drive_cycle.enabled: true`, a day multi-select appears. Filter telemetry and features to specific days of the simulation. Useful for comparing early-life vs late-life behaviour (connector aging progression).

### Channel Selector

Multi-select listing all channels (after zone filtering), displaying load names from the manifest (e.g., "ch_01 — headlamp_left"). First 4 channels are selected by default. Maximum 8 channels displayed simultaneously for browser performance.

---

## Tabs

### 📊 Overview

Top-level summary of the selected run.

**KPI Cards:**
- Total drive cycles (multi-cycle) or "1" (single-cycle)
- Number of channels
- Total telemetry samples
- Fault label count
- Trip event count

**Drive Cycle Timeline** (multi-cycle only):
Gantt chart showing each drive cycle as a horizontal bar, colored by day. X-axis is absolute time, Y-axis is cycle index. Hover for cycle duration and ambient temperature.

**Fault Distribution:**
Pie chart of fault type counts across all labels.

**Fault Exposure per Channel:**
Stacked horizontal bar chart — each bar is a channel, stacked by fault type. Quickly identifies which channels are under the most stress.

**Channel Summary Table:**
Mean current, max current, mean temperature, max temperature, and trip count per channel.

### 📡 Telemetry

Time-series exploration of raw signals.

For each selected channel, a 3-panel subplot:
1. **Current (A)** — blue line with fault windows shaded by colour
2. **Voltage (V)** — green line
3. **Temperature (°C)** — orange line

**Overlays:**
- **Fault shading** — semi-transparent coloured regions matching fault type (colour legend in sidebar)
- **Trip markers** — red X markers at trip_flag rising edges
- **Power-off regions** — grey ribbon where `state_on_off = 0` (sleep, duty-cycle off, or tripped)

Zoom and pan via Plotly's built-in tools. Double-click to reset axes.

### 🔬 Features

Derived feature time series, overlaid against fault windows.

Plots for each selected channel:
- `rolling_rms_current` — baseline current level + transients
- `rolling_mean_current` — smoothed current trend
- `temperature_slope` — rate of temperature change (positive = heating)
- `spike_score` — σ above baseline (spikes are visible here even when masked by noise in raw telemetry)
- `trip_frequency` — rolling count of protection trips
- `recovery_time_s` — time since last protection trip

Fault windows are shaded for visual correlation between features and ground truth.

### ⚠️ Fault Analysis

Deep dive into fault characteristics.

**Fault Heatmap:**
Channel × time grid coloured by active fault type. Shows temporal clustering and which channels experience simultaneous faults.

**Severity Distribution:**
Histogram of fault intensity values (0.0–1.0). Useful for verifying the stochastic fault distribution in multi-cycle runs.

**Intensity vs. Protection Correlation:**
Scatter plot of fault intensity against protection response category. Validates that high-intensity faults consistently trigger protection.

### 🛡️ Protection Events

Protection system performance analysis.

**Per-Mechanism Timeline:**
One subplot per protection type (SCP, I²T, LATCH_OFF, THERMAL_SHUTDOWN, OPEN_LOAD_DIAG, OVER_VOLTAGE). Shows event occurrence over time for selected channels. Edge-counted from raw telemetry (not windowed), so each marker represents a genuine state transition.

**Reset Counter Scatter:**
`reset_counter` vs. fault intensity for samples where protection is active. Higher retry counts at higher intensities indicate correct F(i,t) → SCP escalation behaviour.

### 📋 Config

Run configuration inspection.

**YAML Viewer:**
The full `config.yaml` snapshot from the run, displayed as read-only formatted YAML. Includes all resolved defaults and CLI overrides.

**Channel Inventory Table:**
Table of all channels with zone_id, load_name, efuse_family, nominal/max current, duty_cycle. Sourced from `channel_manifest.parquet`.

**Zone Distribution Chart:**
Bar chart showing channel count per zone. Verifies the topology is loaded correctly.

---

## Colour Palette

Fault types are mapped to consistent colours across all tabs:

| Fault Type | Colour |
|------------|--------|
| `overload_spike` | Red `#ef4444` |
| `intermittent_overload` | Orange `#f97316` |
| `voltage_sag` | Amber `#f59e0b` |
| `thermal_drift` | Purple `#a855f7` |
| `noisy_sensor` | Cyan `#06b6d4` |
| `dropped_packet` | Grey `#6b7280` |
| `gradual_degradation` | Rose `#f43f5e` |
| `connector_aging` | Brown `#92400e` |
| `open_load` | Pink `#ec4899` |
| `jump_start` | Lime `#84cc16` |
| `load_dump` | Emerald `#10b981` |
| `cold_crank` | Blue `#3b82f6` |
| `thermal_coupling` | Violet `#8b5cf6` |
| `wake_transient` | Teal `#14b8a6` |

---

## Performance Notes

- The dashboard uses `@st.cache_data` to cache Parquet loads. Switching filters is fast; switching runs reloads data.
- Channel display is capped at 8 to keep the browser responsive with Plotly rendering.
- For month-long multi-cycle runs (~8 M rows), the Overview tab loads quickly; Telemetry and Features tabs may take a few seconds on first render. Use the Day filter to narrow the time range.
- The dashboard reads directly from `output/` — no database or server required.
