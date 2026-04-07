# DTC Rule Engineering

## 1. Decision

Define, tune, and validate diagnostic trouble code (DTC) detection rules — thresholds, debounce timers, and confirmation logic — so each rule achieves measurable precision and recall targets before deployment.

## 2. Trigger

- New eFuse function or channel family needs a diagnostics concept
- Field returns indicate false-positive or missed-detection problems with existing rules
- Software release includes DTC logic changes requiring re-validation

## 3. Stakeholders

| Role | Who |
|---|---|
| **Decision owner** | Diagnostics / DTC team lead |
| **Data consumer** | Controls SW (implements rules), QA (validates), Aftersales (consumes DTCs) |
| **Domain input** | eFuse Function Owner (fault behaviour), safety team (detection requirements for safety-relevant faults) |

## 4. Problem

DTC rules for eFuse faults are notoriously difficult to get right:

- **Same symptom, different cause:** A current drop could be `open_load`, `connector_aging`, or a legitimate load-off command. Debounce alone cannot distinguish them.
- **Different symptom, same cause:** `ground_offset` can appear as elevated current on one channel and depressed voltage on another, depending on the load impedance.
- **No ground truth in real data:** Bench or field data rarely carries a confirmed root-cause label. DTC designers tune rules against ambiguous examples.

The result: rules are either too broad (high false-positive rate → service noise, unnecessary part replacements) or too narrow (missed detections → customer-visible failures without a stored DTC).

**Cost:** Each false DTC in the field triggers a workshop visit (€150–400). Each missed DTC delays fault discovery and increases warranty cost by 3–5× compared to early detection.

## 5. Why Synthetic Data

| Gap | How simulation fills it |
|---|---|
| **Labels** | Every simulated fault carries a ground-truth label (type, severity, start time) — the single most valuable property for rule development |
| **Coverage** | Can generate thousands of labelled fault episodes across all fault families; field data may have <10 confirmed examples per fault type per year |
| **Controlled comparison** | Same channel, same load, healthy vs. faulty — isolates the fault signature from operating-point variation |
| **Edge cases** | Can systematically test boundary conditions: "fault severity just at detection threshold" or "two faults overlapping in time" |

## 6. Scenario Design

| Element | Specification |
|---|---|
| **Channels** | Representative of each load family: resistive (heater), inductive (motor/relay), PWM (blower), low-current (LED/sensor) |
| **Faults** | `open_load`, `short_to_ground`, `ground_offset` (+50/+100/+200 mΩ), `connector_aging` (gradual, 0.5–5 mΩ/day), `intermittent_overload`, `voltage_sag` |
| **Baseline** | Each fault scenario paired with a healthy baseline on the same channel, same operating point |
| **Severity sweep** | Each fault at 3+ severity levels: below detection threshold, at threshold, clearly above |
| **Rule candidates** | Encode 2–3 candidate rules per fault (different threshold/debounce/confirmation combinations) and evaluate each against the full fault matrix |
| **Environment** | Nominal (+25 °C), hot (+85 °C — affects baseline current), cold (−40 °C — affects connector resistance) |
| **Duration** | Per episode: 10–30 s (enough for debounce + confirmation); per evaluation: full matrix of episodes |

## 7. Required Signals

| Signal | Unit | Purpose |
|---|---|---|
| `current_a` | A | Primary detection signal for most rules |
| `voltage_v` | V | Needed for ground-offset and voltage-sag rules |
| `temperature_c` | °C | Temperature-dependent threshold compensation |
| `trip_flag` | bool | Protection interaction (did the rule trigger before protection tripped?) |
| `protection_event` | enum | Correlation between DTC and protection path |
| `fault_type` | label | Ground-truth for precision/recall calculation |
| `severity` | float | Ground-truth for threshold sensitivity analysis |
| `fault_start_s` | float | Ground-truth for detection-latency measurement |
| `state_on_off` | bool | Distinguish load-off from open-load |

## 8. Key Metrics

| Metric | Direction | Target |
|---|---|---|
| Detection recall per fault family | ↑ | ≥ 95 % for safety-relevant faults (`short_to_ground`, `open_load`); ≥ 85 % for progressive faults (`connector_aging`, `ground_offset`) |
| False-positive rate under normal operation (including inrush, PWM, power-state transitions) | ↓ | < 0.1 % of operating cycles |
| Detection latency (time from fault start to DTC confirmation) | ↓ | < 2 s for hard faults; < 3 drive cycles for progressive faults |
| Ambiguous classifications (fault detected but wrong type assigned) | ↓ | < 5 % of detected faults |

## 9. Decision Criteria

| Outcome | Action |
|---|---|
| All fault families meet recall + FP targets | Approve rule set for SW release; generate confusion matrix as release documentation |
| Individual fault types fail recall but others pass | Iterate: tighten debounce, add secondary signal (e.g., voltage confirmation for current-only rule) |
| Systematic FP problem (e.g., all inrush-heavy channels false-trigger) | Add operating-point guard (e.g., suppress DTC for 500 ms after load-on command) |
| Fundamental ambiguity (two fault types indistinguishable with available signals) | Escalate to [CAN Telemetry Fidelity](../4-vehicle-integration/can-telemetry-fidelity.md) — may need higher resolution or additional signals |

## 10. Dependencies

| Direction | Artefact |
|---|---|
| **Upstream** | Protection event definitions from [Threshold Calibration](../1-protection-design/threshold-and-retry-calibration.md) |
| **Upstream** | Load specifications and expected operating profiles |
| **Downstream** | [Workshop Fault Isolation](workshop-fault-isolation.md) — validated rules are the basis for service playbooks |
| **Downstream** | [Release Regression Gating](../1-protection-design/release-regression-gating.md) — DTC precision/recall become regression metrics |
| **Related** | [Degradation Early Warning](../6-field-and-fleet/degradation-early-warning.md) — progressive-fault detection overlaps with fleet analytics feature engineering |

## 11. Limitations

- Simulation DTC evaluation assumes the rule is applied to raw telemetry. In production, CAN quantisation, sampling rate, and message scheduling may degrade signal fidelity — test with realistic CAN constraints or validate via [CAN Telemetry Fidelity](../4-vehicle-integration/can-telemetry-fidelity.md).
- Multi-fault scenarios (two faults on different channels simultaneously) are not covered unless explicitly configured. Real-world coincidence is rare but possible.
- DTC confirmation logic that depends on external inputs (e.g., load-command state from body controller) cannot be fully validated in the simulation unless those inputs are modelled.
