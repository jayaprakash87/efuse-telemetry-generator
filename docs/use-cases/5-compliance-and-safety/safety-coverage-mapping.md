# Safety Coverage Mapping

## 1. Decision

Confirm that the planned physical validation campaign — bench tests, vehicle tests, and analysis — covers all fault families, load types, and environmental conditions required by functional-safety and OEM-specific standards, and identify gaps before testing begins.

## 2. Trigger

- FMEA or hazard analysis complete — need to trace mitigation evidence to specific test scenarios
- Test plan review milestone approaching (e.g., B-sample validation kick-off)
- Audit preparation — compliance team needs a coverage matrix for the assessor

## 3. Stakeholders

| Role | Who |
|---|---|
| **Decision owner** | Functional safety engineer / FMEA owner |
| **Data consumer** | Validation test planner (adjusts test plan based on gaps), certification manager (presents to auditor) |
| **Domain input** | eFuse FO (fault families and protection modes), safety team (ASIL-relevant failure modes) |

## 4. Problem

A typical zone-controller FMEA identifies 30–60 failure modes across 6–12 channels. Each mode should be demonstrated under multiple conditions (hot, cold, degraded supply, aged harness). The resulting test matrix is 200–500 unique combinations. Physical test plans cover 30–50 of these — selected by experience, not by systematic prioritisation.

The gaps are invisible until an auditor asks "where is the evidence for over-temperature on channel 4 at −40 °C with a degraded connector?" and nobody has an answer.

**Cost of a gap discovered during audit:** 4–12 week delay for supplementary testing; potentially delays homologation.

## 5. Why Synthetic Data

| Gap | How simulation fills it |
|---|---|
| **Enumeration** | Simulation can run the full 200–500 combination matrix; physical testing cannot |
| **Early gap detection** | Run the full matrix at simulation level; compare against the planned physical test plan; highlight untested combinations |
| **Evidence classification** | For each combination, classify: "can be covered by simulation + analysis," "needs bench test," "needs vehicle test." This directly feeds the evidence portfolio |
| **Labels** | Simulation output carries fault labels, protection-event logs, and operating-condition metadata — exactly the traceability an auditor wants |

## 6. Scenario Design

| Element | Specification |
|---|---|
| **Coverage source** | FMEA failure-mode list + OEM validation requirements catalogue |
| **Channels** | All channel families on the zone controller |
| **Fault families** | Every fault type in the FMEA: `short_to_ground`, `open_load`, `overload`, `ground_offset`, `connector_aging`, `voltage_sag`, `thermal_runaway` |
| **Conditions** | Temperature: −40 / +25 / +85 °C; supply: 9 / 12 / 13.5 V; harness: nominal / degraded |
| **Combinatorial** | Full cross-product of {fault × channel × condition} |
| **Duration** | 30 s per combination (enough to trigger and confirm protection response) |

## 7. Required Signals

| Signal | Unit | Purpose |
|---|---|---|
| `fault_type` | label | Maps to FMEA failure mode |
| `protection_event` | enum | Maps to FMEA safety mechanism |
| `trip_flag` | bool | Confirms mechanism activated |
| `retry_count` | int | Confirms recovery or latch behaviour |
| `channel_id` | str | Maps to FMEA item |
| `ambient_temp_c` | °C | Condition traceability |
| `supply_v` | V | Condition traceability |
| `connector_r_ohm` | Ω | Degradation condition traceability |

## 8. Key Metrics

| Metric | Direction | Target |
|---|---|---|
| FMEA failure-mode coverage (% of modes with ≥ 1 simulation run demonstrating correct protection response) | ↑ | 100 % |
| Condition-corner coverage (% of mode × condition combinations covered) | ↑ | ≥ 90 % (remaining 10 % require vehicle test) |
| Gaps identified (mode × condition combinations where protection did NOT behave as expected) | report | Enumerate for test-plan adjustment |
| Combinations classified as "simulation-sufficient" vs. "needs bench" vs. "needs vehicle" | report | Minimise bench/vehicle list without sacrificing compliance |

## 9. Decision Criteria

| Outcome | Action |
|---|---|
| Full coverage; all protection responses correct | Proceed to focused physical test plan (bench confirms highest-risk simulation results only) |
| Coverage gaps found (untested combinations) | Add missing combinations to physical test plan or generate additional simulation scenarios |
| Protection failures found (mode where mechanism did NOT activate) | Escalate to [Threshold Calibration](../1-protection-design/threshold-and-retry-calibration.md) — protection strategy needs rework for that mode |

## 10. Dependencies

| Direction | Artefact |
|---|---|
| **Upstream** | FMEA / hazard analysis (failure modes + required safety mechanisms) |
| **Upstream** | Protection configuration from [Threshold Calibration](../1-protection-design/threshold-and-retry-calibration.md) |
| **Downstream** | Physical bench validation test plan |
| **Downstream** | Compliance evidence portfolio for auditor |
| **Related** | [Pre-Certification Screening](pre-certification-screening.md) — screening prioritises within the coverage map |

## 11. Limitations

- Simulation evidence is classified as "analysis" under ISO 26262, not "test." Safety-critical failure modes (ASIL B and above) will still require physical demonstration. Simulation scopes which physical tests are needed, it does not replace them.
- The coverage map is only as complete as the FMEA input. If a failure mode is missing from the FMEA, the coverage map will not catch it.
- Simulation assumes the protection implementation matches the specification. Implementation bugs (e.g., off-by-one in threshold register) are not caught by simulation.
