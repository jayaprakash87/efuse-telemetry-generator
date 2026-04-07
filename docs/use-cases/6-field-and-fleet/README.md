# 6 — Field & Fleet

> **Core question:** *What is happening in the field — and how do I use that knowledge to improve?*

Once the zone controller ships, the function owner's job shifts from design to continuous improvement. Field data reveals patterns that no pre-launch simulation anticipated: connector degradation rates differ by climate zone, specific load combinations trigger nuisance trips at temperatures that bench never tested, warranty spikes appear on a variant that "passed everything."

Synthetic data's role changes too: instead of replacing missing bench data, it now **amplifies scarce field data** — generating thousands of labelled degradation trajectories to train early-warning models, and replaying field-observed patterns to test recalibration candidates before deploying them to the fleet.

## Use Cases

| # | Use Case | Decision |
|---|---|---|
| 1 | [Degradation Early Warning](degradation-early-warning.md) | Engineer predictive features from labelled degradation data that fleet analytics can deploy |
| 2 | [Field-Driven Recalibration](field-driven-recalibration.md) | Validate threshold adjustments prompted by field findings before pushing them to vehicles |

## Who uses this

- Fleet analytics / data science team (early-warning models)
- eFuse Function Owner (recalibration decisions)
- Quality / warranty team (field-issue input)
- OTA / software delivery (deploys recalibrated SW)
