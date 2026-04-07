# Pre-Certification Screening

## 1. Decision

Rank fault × load × environment stress combinations by protection-event density and thermal severity to prioritise the physical bench campaign — test the riskiest scenarios first, defer or eliminate low-risk ones.

## 2. Trigger

- Physical validation campaign scoped and budgeted — need to allocate limited bench time to highest-value tests
- [Safety Coverage Mapping](safety-coverage-mapping.md) identified more gaps than the bench budget can cover — need to triage
- Test lab shared across programs — need a defensible prioritisation to negotiate bench slots

## 3. Stakeholders

| Role | Who |
|---|---|
| **Decision owner** | Validation test planner + certification manager |
| **Data consumer** | Bench test engineer (executes the prioritised plan), safety engineer (confirms risk assessment) |
| **Domain input** | eFuse Function Owner (expected worst-case scenarios), thermal engineer (thermal limits) |

## 4. Problem

Coverage mapping tells you **what** to test. Screening tells you **what to test first.** With limited bench time (often 2–4 weeks shared across programs), not every combination can be tested physically. The question is: which combinations are most likely to reveal a real problem?

Today, prioritisation is based on engineer judgement: "hot + high current + short = worst case." This works for obvious extremes but misses non-intuitive interactions:

- Cold + connector aging + inrush: connector resistance is higher at −40 °C, combined with aging, and the inrush may push the IC into a thermal-electrical corner that nominal analysis doesn't predict.
- Load dump + multi-channel recovery + degraded ground: the simultaneous recovery inrush through a degraded ground path creates a virtual ground shift that trips adjacent channels.

## 5. Why Synthetic Data

| Gap | How simulation fills it |
|---|---|
| **Exhaustive stress ranking** | Run hundreds of stress combinations; rank by protection-event count, thermal peak, and diagnostic ambiguity — not by gut feel |
| **Non-intuitive interactions** | Simulation reveals which combinations produce the most events; these are often not the "obvious" hot+high+short combinations |
| **Quantified severity** | Each combination gets a numerical stress score (events per minute, peak die temp, margin to shutdown); allows data-driven prioritisation |

## 6. Scenario Design

| Element | Specification |
|---|---|
| **Stress combinations** | Full cross-product from [Safety Coverage Mapping](safety-coverage-mapping.md): {fault × channel × temp × supply × harness_condition} |
| **Additional stress factors** | Add powernet disturbances: cold_crank, load_dump overlaid on fault scenarios |
| **Multi-channel activation** | Include worst-case simultaneous channel sets (from [Multi-Channel Interaction](../4-vehicle-integration/multi-channel-interaction.md)) |
| **Duration** | 60 s per combination (longer than coverage mapping to capture cumulative stress effects) |
| **Scoring** | For each combination, count: protection events, nuisance trips, thermal peaks, DTC ambiguities |

## 7. Required Signals

| Signal | Unit | Purpose |
|---|---|---|
| `protection_event` | enum + count | Primary stress indicator |
| `temperature_c` | °C | Thermal stress severity |
| `trip_flag` | bool | Nuisance trip indicator |
| `retry_count` | int | Recovery difficulty |
| `fault_type` | label | Links back to FMEA |
| `ambient_temp_c` | °C | Stress condition |
| `supply_v` | V | Stress condition |
| `connector_r_ohm` | Ω | Degradation condition |

## 8. Key Metrics

| Metric | Direction | Target |
|---|---|---|
| Stress score per combination (composite: events + thermal proximity to shutdown + nuisance trips) | report | Ranked list; top 20 % labelled "must test on bench" |
| Bench campaign scope reduction (combinations safely deferred based on zero-event simulation) | ↑ | 40–60 % reduction in required bench scenarios |
| Non-intuitive high-risk discoveries (combinations ranked high by simulation but not by engineer prior) | report | Called out explicitly for review |
| Correlation with known field issues (if available: do simulation-ranked-high scenarios match historical field failures?) | ↑ | Used as validation of ranking methodology |

## 9. Decision Criteria

| Outcome | Action |
|---|---|
| Clear ranking; top-20 % covers all protection events | Approve focused bench plan; document rationale for deferred combinations |
| Ranking reveals non-intuitive high-risk scenarios | Add these to bench plan; brief the test engineer on expected behaviour |
| Many combinations produce events (>40 % of matrix) | Protection strategy may be too aggressive or too marginal; feed back to [Threshold Calibration](../1-protection-design/threshold-and-retry-calibration.md) |
| Zero events across the entire matrix | Either protection is over-conservative (never trips even under stress) or the scenario design is too mild; review both |

## 10. Dependencies

| Direction | Artefact |
|---|---|
| **Upstream** | Coverage map from [Safety Coverage Mapping](safety-coverage-mapping.md) |
| **Upstream** | Protection configuration from [Threshold Calibration](../1-protection-design/threshold-and-retry-calibration.md) |
| **Upstream** | Multi-channel combinations from [Multi-Channel Interaction](../4-vehicle-integration/multi-channel-interaction.md) |
| **Downstream** | Prioritised physical bench test plan |
| **Downstream** | Bench-time negotiation with test-lab management |

## 11. Limitations

- Stress ranking is relative (combination A is more stressful than B). Absolute risk assessment requires coupling with failure-probability data from FMEA, which is outside this tool's scope.
- Simulation stress scores depend on the protection configuration being correct. If thresholds are wrong, the ranking is wrong.
- Low-ranked combinations are "low risk based on simulation," not "no risk." Deferring them is a risk-managed decision, not a guarantee of safety.
