# Fault Classifier Training

## 1. Decision

Generate a labelled training dataset — with controlled class balance, fault
diversity, and channel coverage — to train a supervised multi-class fault
classifier that can run on eFuse CAN telemetry in fleet analytics or in-vehicle
diagnostics.

---

## 2. Trigger

- Data science team beginning a fault classification model for eFuse channels
- DTC precision / recall below acceptable threshold and rule-based approach is
  exhausted
- New fault type added to the FMEA that has no real field examples yet

---

## 3. Stakeholders

| Role | Who |
|---|---|
| **Decision owner** | Data science / ML team lead |
| **Data consumer** | Model training pipeline; DTC team validating classifier against rule-based baseline |
| **Domain input** | eFuse Function Owner (fault taxonomy, severity definitions) |

---

## 4. Problem

Training a fault classifier on real field data has three blockers:

- **Label scarcity.** Confirmed fault labels require a workshop diagnosis or
  engineering investigation after each event. Most field events are unlabelled.
- **Class imbalance.** Normal operation makes up > 99 % of real data. Rare but
  critical faults (latch-up, thermal runaway) may have fewer than 10 confirmed
  examples per year.
- **Fault coupling.** In real data, multiple fault types co-occur (e.g., a
  short-circuit fault also triggers an overtemperature event) making label
  isolation impossible without synthetic control.

---

## 5. Why Synthetic Data

| Gap | How simulation fills it |
|---|---|
| **Labels** | Every sample has an exact ground-truth label: `fault_type`, `severity`, injected at a known timestamp |
| **Class balance** | Generate exactly N samples per class by controlling the scenario config |
| **Fault isolation** | Inject one fault type at a time to build clean per-class decision boundaries |
| **Coverage** | Every FMEA fault type is reachable in simulation, including rare or dangerous faults |

---

## 6. Scenario Design

| Element | Specification |
|---|---|
| **Channels** | Full channel set: low-current (< 5 A), mid-current (5–20 A), high-current (> 20 A) — classifier must generalise across load types |
| **Fault types** | `short_circuit`, `overload_soft`, `overload_hard`, `open_circuit`, `connector_aging`, `ground_offset`, `thermal_runaway`, `nuisance_trip` (normal but high inrush) |
| **Class balance** | Minimum 1 000 labelled windows per fault type; 5 000 normal windows for baseline |
| **Window length** | 500 ms pre-fault + fault event + 500 ms post-trip — captures triggering dynamics |
| **Severity sweep** | Each fault type at low / medium / high severity to train a severity-aware classifier |
| **Environmental conditions** | Ambient −20 °C to +85 °C; supply voltage 11–14.5 V |

---

## 7. Required Signals

| Signal | Unit | Purpose |
|---|---|---|
| `current_a` | A | Primary classifier feature |
| `voltage_v` | V | Supply drop during fault |
| `temperature_c` | °C | Thermal context |
| `trip_flag` | bool | Protection activation label |
| `protection_event` | enum | SCP / OCP / OTP / latch |
| `fault_type` | label | **Ground-truth training label** |
| `severity` | float | Fault intensity (0–1) |
| `channel_id` | str | For channel-stratified splits |
| `pwm_duty_pct` | % | Load state at fault time |

---

## 8. Key Metrics

| Metric | Direction | Target |
|---|---|---|
| Macro-averaged F1 across all fault classes | ↑ | ≥ 0.85 on held-out synthetic test set |
| Recall for safety-critical faults (`short_circuit`, `thermal_runaway`) | ↑ | ≥ 0.95 |
| False-positive rate on normal windows | ↓ | ≤ 2 % |
| Performance drop on real bench data (transfer gap) | ↓ | ≤ 10 % F1 drop vs. synthetic test set |

---

## 9. Decision Criteria

| Outcome | Action |
|---|---|
| All targets met on synthetic test set | Deploy to shadow mode on fleet data; compare with DTC rule baseline |
| Safety-critical recall below target | Increase severity sweep density for those fault types; check feature window width |
| High false-positive rate on normal windows | Augment normal class with more operating-condition variation (temperatures, load profiles) |
| Large transfer gap to bench data | Trigger [Synthetic Pre-training + Real Fine-tuning](synthetic-pretraining-real-finetuning.md) |

---

## 10. Dependencies

| Direction | Artefact |
|---|---|
| **Upstream** | Fault taxonomy from eFuse FMEA |
| **Upstream** | CAN resolution constraints from [CAN Telemetry Fidelity](../4-vehicle-integration/can-telemetry-fidelity.md) |
| **Downstream** | Trained classifier deployed to fleet analytics pipeline |
| **Downstream** | [DTC Rule Engineering](../2-diagnostics/dtc-rule-engineering.md) — classifier used as evidence alongside rule-based DTCs |
| **Related** | [Synthetic Pre-training + Real Fine-tuning](synthetic-pretraining-real-finetuning.md) — next step if transfer gap is too large |

---

## 11. Limitations

- Synthetic fault waveforms are parameterised models. Real faults may have
  different rise times, noise characteristics, or coupling effects not captured
  in the simulator.
- The classifier trained here should be validated on bench data before fleet
  deployment. Synthetic performance is an upper bound.
- Multi-label cases (simultaneous fault types) are not covered by this use case.
  Train on isolated fault types first, then extend.
