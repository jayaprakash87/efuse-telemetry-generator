# Pre-Trip Sequence Prediction

## 1. Decision

Build and validate a time-series model that predicts — from the last N seconds
of eFuse telemetry — whether a protection trip will occur in the next T seconds,
and if so, which fault type.

This enables pre-emptive load management (reduce current before SCP fires),
in-vehicle early warning, and proactive service scheduling.

---

## 2. Trigger

- Protection trips are causing nuisance shutdowns with recoverable root causes
  (e.g., motor inrush exceeding SCP threshold) that could be avoided if the ECU
  had 200–500 ms of forewarning
- Fleet analytics team wants a predictive maintenance signal with shorter lead
  time than degradation early warning (minutes to hours, not weeks)
- New variant requires pre-trip prediction as a functional safety mitigation

---

## 3. Stakeholders

| Role | Who |
|---|---|
| **Decision owner** | eFuse Function Owner (in-vehicle) or Fleet analytics lead (cloud) |
| **Data consumer** | ECU load-management strategy; cloud fleet alerting pipeline |
| **Domain input** | eFuse Function Owner (trip dynamics, recovery behaviour); safety team (intervention authority) |

---

## 4. Problem

A protection trip is the end event of a causal chain — current rise, thermal
buildup, or voltage instability — that preceded the trip by tens to hundreds of
milliseconds. If that causal chain is detectable early enough, the ECU can
reduce PWM duty, schedule load shedding, or send an early alert.

The challenge:

- **Short prediction horizon.** Pre-trip dynamics unfold over 50–500 ms — too
  fast for a human to label boundaries, but long enough for a sequence model if
  it has the right training examples.
- **Imbalanced sequences.** In normal operation, > 99 % of sequences do not
  lead to a trip. Without synthetic data, there are too few pre-trip sequences
  to train a reliable model.
- **Fault-dependent lead time.** A `short_circuit` pre-trip signature is
  different from a `thermal_runaway` pre-trip signature — the model needs
  examples of each.

---

## 5. Why Synthetic Data

| Gap | How simulation fills it |
|---|---|
| **Labels** | Exact trip timestamp and fault type known — allows precise window extraction |
| **Volume** | Generate thousands of pre-trip windows per fault type in minutes |
| **Horizon control** | Evaluate model at different prediction horizons (50 ms, 200 ms, 500 ms) by labelling the same sequence at multiple lead times |
| **Class balance** | Control ratio of pre-trip to normal sequences — impossible with real data |

---

## 6. Scenario Design

| Element | Specification |
|---|---|
| **Fault types** | `short_circuit`, `overload_hard`, `overload_soft`, `thermal_runaway`, `connector_aging` (late stage) |
| **Prediction horizons** | 50 ms, 100 ms, 200 ms, 500 ms — generate separate datasets per horizon |
| **Window length** | T_horizon + 2 s of pre-fault context |
| **Normal sequences** | Equal volume of non-trip windows sampled from the same channels / operating conditions |
| **Severity** | Low / medium / high severity per fault type — model must generalise across gradations |
| **Environmental sweep** | Ambient −20 °C to +85 °C; supply 11–14.5 V |
| **Sampling rate** | 10 ms (100 Hz) — fine enough to capture pre-trip dynamics |

---

## 7. Required Signals

| Signal | Unit | Purpose |
|---|---|---|
| `current_a` | A | Primary sequence feature (rate of change is predictive) |
| `voltage_v` | V | Supply drop pre-trip |
| `temperature_c` | °C | Thermal buildup trajectory |
| `trip_flag` | bool | Target label (trip occurs at T + horizon) |
| `fault_type` | label | Multi-class target label |
| `time_to_trip_s` | float | Regression target (continuous time-to-trip) |
| `channel_id` | str | Channel identity for normalisation |

---

## 8. Key Metrics

| Metric | Direction | Target |
|---|---|---|
| AUROC for binary trip / no-trip prediction at 200 ms horizon | ↑ | ≥ 0.92 |
| Recall for safety-critical trips (`short_circuit`, `thermal_runaway`) at 200 ms horizon | ↑ | ≥ 0.90 |
| False-alert rate on normal sequences | ↓ | ≤ 1 % |
| Mean absolute error on time-to-trip regression (for alerts with ≥ 200 ms predicted lead time) | ↓ | ≤ 50 ms |

---

## 9. Decision Criteria

| Outcome | Action |
|---|---|
| AUROC and recall targets met | Integrate model into ECU or cloud pipeline; run shadow mode for 2 weeks before enabling intervention |
| Recall below target for a fault type | Increase window length or add engineered features (di/dt, d²i/dt²) for that fault type |
| False-alert rate too high | Apply load-state conditioning (suppress prediction when load is in known inrush phase) |
| Time-to-trip MAE too large | Reduce to binary prediction only; drop regression target |

---

## 10. Dependencies

| Direction | Artefact |
|---|---|
| **Upstream** | Trip dynamics characterised by [Threshold & Retry Calibration](../1-protection-design/threshold-and-retry-calibration.md) |
| **Upstream** | CAN sampling rate from [CAN Telemetry Fidelity](../4-vehicle-integration/can-telemetry-fidelity.md) — 10 ms required |
| **Downstream** | ECU load-management strategy (intervention on prediction) |
| **Downstream** | [Field-Driven Recalibration](../6-field-and-fleet/field-driven-recalibration.md) — if prediction consistently fires without a trip, the protection threshold may need raising |
| **Related** | [Fault Classifier Training](fault-classifier-training.md) — pre-trip model and fault classifier can share feature extraction layers |

---

## 11. Limitations

- Pre-trip dynamics shorter than the CAN sampling interval (< 10 ms) are not
  captured. Very fast `short_circuit` events may be inherently unpredictable at
  CAN resolution. Consider raw ADC data if available on the ECU.
- The model predicts from the telemetry trajectory alone — it has no knowledge
  of external events (driver action, road conditions) that cause the load change.
  This limits prediction of externally-caused overloads.
- In-vehicle deployment requires meeting ECU compute and latency constraints.
  Model size and inference time must be validated separately from this use case.
