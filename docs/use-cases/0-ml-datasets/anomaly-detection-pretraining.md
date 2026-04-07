# Anomaly Detection Pre-training

## 1. Decision

Generate a large, clean "normal operations" dataset — covering the full
operating envelope — to pre-train an anomaly or novelty detection model that
can flag unusual eFuse behaviour in fleet data without requiring any fault
labels.

---

## 2. Trigger

- Fleet analytics team needs an always-on alerting layer below DTC threshold
- New vehicle variant deployed with no historical baseline; need to establish
  "what normal looks like" before faults accumulate
- fault classifier (use case 0.1) is unavailable because fault labels don't
  exist for a specific channel or market yet

---

## 3. Stakeholders

| Role | Who |
|---|---|
| **Decision owner** | Fleet analytics / data science team lead |
| **Data consumer** | Cloud anomaly detection service; real-time in-vehicle monitoring (if compute budget allows) |
| **Domain input** | eFuse Function Owner (normal operating envelope); powernet team (supply voltage variation) |

---

## 4. Problem

Anomaly detection models require a comprehensive definition of "normal" — but
"compehensive" is the problem:

- **Incomplete envelope.** Real fleet data collected over 3–6 months may not
  cover all ambient temperatures, load combinations, and supply voltage ranges.
  A model trained on an incomplete normal envelope will generate false alerts
  for perfectly valid but unseen operating conditions.
- **Contaminated baseline.** If the fleet already has degraded channels, the
  "normal" baseline includes early degradation — teaching the model that
  degradation is normal.
- **No ground truth for normality.** Unlike fault classification, there's no
  label saying "this window is definitely normal." Simulation provides that
  guarantee.

---

## 5. Why Synthetic Data

| Gap | How simulation fills it |
|---|---|
| **Complete envelope** | Sweep all combinations of ambient temperature, load profile, supply voltage, and channel type in a controlled grid |
| **Clean baseline guarantee** | No degradation, no fault injection — pure normal operation by construction |
| **Volume** | Generate millions of normal windows in hours; real fleet normal data takes months to accumulate |
| **Reproducibility** | Re-generate the baseline if the operating envelope changes (new variant, new market) |

---

## 6. Scenario Design

| Element | Specification |
|---|---|
| **Fault injection** | **None** — normal operation only |
| **Channels** | All load families: resistive (heater), inductive (motor), capacitive (actuator) — model must generalise across load types |
| **Ambient temperature** | −30 °C to +85 °C in 5 °C steps |
| **Supply voltage** | 10.5 V to 14.5 V in 0.25 V steps |
| **Load profiles** | Continuous on, PWM duty 20–100 %, cyclic on/off (door, seat heater patterns) |
| **Duration** | ≥ 1 000 drive cycles of normal operation per channel type |
| **Degradation** | Not included — generate separately if semi-supervised approach is needed |

---

## 7. Required Signals

| Signal | Unit | Purpose |
|---|---|---|
| `current_a` | A | Primary normality feature |
| `voltage_v` | V | Supply variation |
| `temperature_c` | °C | Thermal operating context |
| `state_on_off` | bool | Load state for conditional normality |
| `pwm_duty_pct` | % | Load command — normality depends on duty cycle |
| `channel_id` | str | Channel-stratified model or channel-specific baseline |

---

## 8. Key Metrics

| Metric | Direction | Target |
|---|---|---|
| False-alert rate on held-out synthetic normal data | ↓ | ≤ 0.5 % |
| Detection rate on synthetic degradation injected at 25 % severity | ↑ | ≥ 80 % |
| Detection rate on synthetic degradation injected at 50 % severity | ↑ | ≥ 95 % |
| Envelope coverage gap (fraction of real fleet conditions not in training set) | ↓ | ≤ 5 % of observed operating points |

---

## 9. Decision Criteria

| Outcome | Action |
|---|---|
| All targets met | Deploy model to fleet analytics; monitor false-alert rate on live data for first 30 days |
| High false-alert rate | Expand normal training envelope (add missing temperature or load-profile combinations) |
| Degradation detection below target | Add semi-supervised examples: train on normal + lightly degraded windows with known labels |
| Envelope coverage gap too large | Extend sweep grid; or use transfer from a related channel family already covered |

---

## 10. Dependencies

| Direction | Artefact |
|---|---|
| **Upstream** | eFuse operating envelope spec (temperature range, voltage range, load types) |
| **Downstream** | Fleet anomaly alerting service |
| **Downstream** | [Degradation Early Warning](../6-field-and-fleet/degradation-early-warning.md) — anomaly model provides the unsupervised layer; early-warning features provide the supervised layer |
| **Related** | [Fault Classifier Training](fault-classifier-training.md) — anomaly model flags unknowns; classifier identifies known fault types |

---

## 11. Limitations

- A synthetic normal baseline cannot model measurement artefacts introduced by
  the CAN bus, ECU sleep/wake transitions, or OBD tool interactions. Expect a
  tuning pass on real fleet data to adjust the anomaly threshold.
- The model detects deviation from the synthetic normal envelope, not deviation
  from fleet-specific normal. First-deployment false-alert rates may be higher
  until the threshold is tuned on real data.
- Highly load-dependent channels (e.g., seat heaters with occupancy-dependent
  profiles) may need per-channel or per-cluster models rather than a single
  universal model.
