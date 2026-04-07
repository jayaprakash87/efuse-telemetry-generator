# Threshold Search via Simulation Sweeps

## 1. Decision

Use automated parameter sweeps across the generator's config space to find the
protection threshold combination (SCP, OCP, I²T, retry count, retry delay) that
maximises fault detection recall while minimising nuisance trips — replacing
or augmenting a purely manual bench-based calibration process.

---

## 2. Trigger

- New load or IC variant requires calibration and the bench queue is weeks away
- Existing thresholds produce nuisance trips in a new operating environment
  (e.g., new ambient temperature range, new motor load with higher inrush)
- Protection strategy needs to be validated across a larger parameter space than
  bench time allows

---

## 3. Stakeholders

| Role | Who |
|---|---|
| **Decision owner** | eFuse Function Owner |
| **Data consumer** | Calibration dataset to seed bench confirmation; or direct OTA config if confidence is high |
| **Domain input** | Load characterisation team (inrush profiles, load types); safety team (minimum detection recall requirements) |

---

## 4. Problem

Protection threshold calibration is currently manual:

- An engineer proposes a threshold based on analysis and domain knowledge
- The threshold is tested on bench against a set of representative fault and
  normal scenarios
- Repeat until nuisance-trip rate and detection recall are both acceptable

This is slow (days to weeks per variant), under-explores the parameter space
(typically 5–10 combinations tested), and cannot easily account for
interactions between parameters (e.g., increasing OCP threshold allows a
slower I²T to catch overloads).

Simulation sweeps can explore hundreds of parameter combinations in minutes,
identify the Pareto frontier of fault detection vs. nuisance trips, and produce
a ranked shortlist of candidates for bench confirmation.

---

## 5. Why Synthetic Data

| Gap | How simulation fills it |
|---|---|
| **Speed** | 500-point parameter grid runs in minutes on a laptop; equivalent bench test takes weeks |
| **Parameter interaction** | Fully crossed grid captures threshold interactions missed by one-at-a-time manual tuning |
| **Rare fault coverage** | Every fault type and severity is exercised at every parameter combination |
| **Objective scoring** | Nuisance-trip rate and recall are computed automatically from labelled simulation output |

---

## 6. Scenario Design

| Element | Specification |
|---|---|
| **Parameter axes** | `scp_threshold_a` (range from load spec), `ocp_threshold_a`, `i2t_limit_a2s`, `retry_count` (0–5), `retry_delay_ms` (50–2 000 ms) |
| **Sweep strategy** | Latin hypercube sampling (500 points) for initial exploration; Bayesian optimisation for refinement around Pareto frontier |
| **Fault scenarios** | All fault types at low / medium / high severity — scored against each parameter combination |
| **Normal scenarios** | Representative inrush profiles (motor start, heater turn-on, actuator extend) — nuisance-trip rate measured here |
| **Channels** | Target channel family (e.g., 40 A PTC heater); one load type per sweep run |
| **Environmental conditions** | Worst-case combination for nuisance trips (low ambient — high inrush) and worst case for fault detection (high ambient — thermal degradation) |

---

## 7. Required Signals

| Signal | Unit | Purpose |
|---|---|---|
| `current_a` | A | Threshold comparison |
| `temperature_c` | °C | Thermal trip evaluation |
| `trip_flag` | bool | Did the threshold trigger? |
| `protection_event` | enum | Which protection mechanism fired? |
| `fault_type` | label | Ground-truth — was the trip justified? |
| `severity` | float | Fault intensity at trip time |
| Config parameters | — | Recorded alongside every run for scoring |

---

## 8. Key Metrics

| Metric | Direction | Target |
|---|---|---|
| Fault detection recall (trips where `fault_type` ≠ `none`) | ↑ | ≥ 95 % for critical faults (SCP, thermal runaway) |
| Nuisance-trip rate (trips where `fault_type` == `none`) per 1 000 drive cycles | ↓ | ≤ 2 |
| Pareto candidates found (combinations meeting both targets) | ↑ | ≥ 3 distinct candidates for bench shortlist |
| Bench validation pass rate of simulation-selected candidates | ↑ | ≥ 75 % (validates simulation sweep quality) |

---

## 9. Decision Criteria

| Outcome | Action |
|---|---|
| ≥ 3 Pareto candidates found | Submit top 3 to bench team for confirmation; prioritise by ease of OTA deployment |
| No candidates meet both targets | Widen the parameter search range; or escalate to hardware change (different IC or harness routing) |
| Bench validation pass rate < 75 % | Review simulation fidelity for this load type; improve inrush model; tighten sweep scoring criteria |
| Single dominant candidate | Consider direct deployment (with bench confirmation of 1 point) if schedule is critical |

---

## 10. Dependencies

| Direction | Artefact |
|---|---|
| **Upstream** | Load inrush profiles from load characterisation testing or supplier specs |
| **Upstream** | Minimum detection recall from functional safety / FMEA analysis |
| **Downstream** | [Threshold & Retry Calibration](../1-protection-design/threshold-and-retry-calibration.md) — simulation shortlist feeds the bench calibration process |
| **Downstream** | [Release Regression Gating](../1-protection-design/release-regression-gating.md) — new thresholds validated before SW release |
| **Downstream** | [Field-Driven Recalibration](../6-field-and-fleet/field-driven-recalibration.md) — same sweep process, triggered by field data instead of new variant |
| **Related** | [Variant Reuse Validation](../1-protection-design/variant-reuse-validation.md) — check sweep results transfer across variants |

---

## 11. Limitations

- Simulation sweep results are only as good as the load inrush model. If the
  inrush model is inaccurate (e.g., motor startup current not characterised),
  the Pareto frontier will be wrong and bench candidates will fail. Always
  validate the inrush model against at least one bench measurement before
  running a large sweep.
- Multi-channel interactions (shared return path, thermal coupling) are not
  captured in single-channel sweeps. Use [Multi-Channel Interaction](../4-vehicle-integration/multi-channel-interaction.md)
  scenarios for zone-level validation after a per-channel threshold is established.
- Bayesian optimisation requires a reliable objective function. Noisy simulation
  (stochastic fault injection) may require averaging over multiple runs per
  evaluation point.
