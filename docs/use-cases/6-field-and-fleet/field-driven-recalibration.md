# Field-Driven Recalibration

## 1. Decision

Validate a proposed threshold or DTC-rule adjustment — prompted by field findings (warranty spike, nuisance-trip pattern, missed-detection report) — against the full scenario matrix before deploying the change to the fleet via OTA or workshop update.

## 2. Trigger

- Quality team reports a nuisance-trip pattern on a specific channel/variant combination in the field
- Warranty data shows missed detections: components failing without a prior DTC
- Customer complaint cluster (e.g., "heated seats turn off intermittently in cold weather")

## 3. Stakeholders

| Role | Who |
|---|---|
| **Decision owner** | eFuse Function Owner + quality team |
| **Data consumer** | OTA / software delivery (deploys the update), validation (confirms on bench if needed) |
| **Domain input** | Fleet analytics (field data analysis), controls SW (implements the change) |

## 4. Problem

Field findings create urgency: a nuisance-trip pattern affecting 2 % of vehicles in winter needs a fix before the next cold season. The natural response is to adjust the threshold or DTC debounce and push an OTA update.

The risk: **a fix for one problem creates another.** Raising the SCP threshold to eliminate winter nuisance trips on the heated seat may weaken short-circuit protection on the same channel in summer when connector resistance is lower. Loosening a DTC debounce to reduce false positives may delay detection of a real ground fault.

Today, field-driven recalibration is either:
1. **Cautious:** Full bench re-test of the changed parameter → takes weeks, delays the fix.
2. **YOLO:** Change deployed based on limited field-data analysis → risk of regression.

## 5. Why Synthetic Data

| Gap | How simulation fills it |
|---|---|
| **Full regression check** | Run the proposed change against the entire scenario matrix (all channels, all faults, all conditions); confirm no regression in hours instead of weeks |
| **Field-pattern replay** | Recreate the specific field pattern (e.g., "12 A heater channel at −25 °C with 30 mΩ connector aging during cold start") and confirm the fix addresses it |
| **Side-effect detection** | Automatically flag any scenario where the new calibration performs worse than the old one |
| **Speed** | Fix-validate-deploy cycle compressed from 6 weeks (bench) to 1–2 days (simulation + targeted bench confirmation) |

## 6. Scenario Design

| Element | Specification |
|---|---|
| **Field-pattern scenario** | Recreate the specific conditions from the field report: channel, load, ambient, supply, harness condition, fault type if known |
| **Baseline calibration** | Current production calibration (the one that has the problem) |
| **Proposed calibration** | Modified parameter(s) — e.g., SCP threshold raised by 1 A, DTC debounce extended by 200 ms |
| **Full regression matrix** | Same golden pack as [Release Regression Gating](../1-protection-design/release-regression-gating.md) — all channel families × all faults × 3 temperature corners |
| **Focus scenarios** | Channel/conditions adjacent to the field pattern: same channel at other temperatures, adjacent channels at the field-report temperature |

## 7. Required Signals

| Signal | Unit | Purpose |
|---|---|---|
| `trip_flag` | bool | Nuisance-trip regression detection |
| `protection_event` | enum | Event-type change |
| `fault_type` | label | Detection-rate regression |
| `retry_count` | int | Recovery-behaviour regression |
| `current_a` | A | Field-pattern reproduction fidelity |
| `voltage_v` | V | Field-pattern reproduction fidelity |
| `temperature_c` | °C | Thermal regression |
| `config_id` | str | Baseline vs. proposed calibration |

## 8. Key Metrics

| Metric | Direction | Target |
|---|---|---|
| Field-pattern reproduction: does the baseline calibration exhibit the reported problem in simulation? | ↑ (yes = valid reproduction) | Simulation reproduces the field symptom |
| Fix effectiveness: does the proposed calibration eliminate the field symptom? | ↑ | Problem eliminated in the field-pattern scenario |
| Regression: does the proposed calibration introduce any new nuisance trips or missed detections in the full matrix? | ↓ | 0 new regressions |
| Impact scope: how many other channels/conditions are affected by the parameter change? | report | Enumerate for targeted bench confirmation |

## 9. Decision Criteria

| Outcome | Action |
|---|---|
| Field pattern reproduced; fix eliminates it; zero regressions | Approve OTA deployment; bench-confirm the field-pattern channel only |
| Fix eliminates field pattern but introduces 1–2 regressions on other channels | Modify fix to be channel-specific; or add a temperature-dependent override |
| Fix partially addresses field pattern | Investigate further — the field pattern may have a different root cause than assumed |
| Cannot reproduce field pattern in simulation | Field-data analysis may be incomplete; request more field data or investigate operating conditions not modelled (e.g., aftermarket accessories, modified harness) |

## 10. Dependencies

| Direction | Artefact |
|---|---|
| **Upstream** | Field-data analysis from quality / fleet analytics team |
| **Upstream** | Current production calibration and golden pack from [Release Regression Gating](../1-protection-design/release-regression-gating.md) |
| **Downstream** | OTA software update with recalibrated parameters |
| **Downstream** | Updated golden baseline (if fix is deployed, the golden pack must be re-baselined) |
| **Related** | [Degradation Early Warning](degradation-early-warning.md) — field issues that degrade gradually may be better addressed by early-warning features than by threshold changes |

## 11. Limitations

- If the field pattern involves an operating condition not in the simulation model (e.g., aftermarket load on an unused channel, or a specific battery chemistry affecting crank profile), the simulation cannot reproduce it.
- Simulation validates the **parameter change**, not the **implementation.** A bug in the OTA deployment process or target mismatch (wrong variant receives the update) is outside simulation scope.
- Customer perception (e.g., "the heated seat now takes 2 seconds longer to reach full power" after SCP threshold increase) is not captured in simulation KPIs. Product-management review is recommended alongside technical validation.
