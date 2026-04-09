# Built-In Config Templates

## Which template should I use?

```
I want to…
├─ See the pipeline run in < 10 seconds       → quick_demo
├─ Test protection logic on a full vehicle     → single_drive
├─ Generate 30 days of realistic driving data  → multi_day
├─ Simulate a fleet of 50–100 vehicles         → fleet
├─ Hammer one channel with all 16 fault types  → stress_test
└─ Define my own vehicle architecture          → custom_topology or custom_topology_with_catalog
```

## Template Summary

| Template | Channels | Duration | Best For |
|----------|----------|----------|----------|
| **quick_demo** | 3 | 60 s | First run, CI smoke tests, tutorials |
| **single_drive** | 65 | 300 s | Full-vehicle single ignition cycle |
| **multi_day** | 65 | 30 days | Long-term aging, fleet analytics prep |
| **fleet** | 65 × 100 vehicles | 90 days | Fleet-scale studies, regional correlation |
| **stress_test** | 1 | 120 s | Fault coverage validation, waveform review |
| **custom_topology** | 6 (example) | 120 s | OEM teams defining explicit channels |
| **custom_topology_with_catalog** | 8 (example) | 180 s | OEM teams using IC catalog presets |

## Progression

Start simple and scale up:

```
quick_demo → single_drive → multi_day → fleet
```

## custom_topology vs custom_topology_with_catalog

Both let you define your own vehicle architecture. The difference:

- **custom_topology** — you specify all electrical parameters per channel (`r_ds_on_ohm`, `r_thermal_kw`, etc.). Use when you have exact values from datasheets.
- **custom_topology_with_catalog** — you reference an `efuse_family` (e.g. `inf_hs_14a`) and the catalog fills in the electrical parameters. Use when you want realistic defaults without looking up datasheets.

**Not sure?** Start with `custom_topology_with_catalog` — you can always override individual parameters.

## Creating Your Own Config

```bash
# Option 1: Copy and edit an existing template
cp quick_demo.yaml my_scenario.yaml
efuse-gen --config ./my_scenario.yaml

# Option 2: Start from a CSV spreadsheet
efuse-gen topology template -o channels.csv --minimal
# Fill in channels.csv, then:
efuse-gen topology import channels.csv -o my_topology.yaml
# Reference in your scenario YAML:
#   simulation:
#     topology_file: ./my_topology.yaml
```
