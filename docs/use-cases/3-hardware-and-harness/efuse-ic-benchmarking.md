# eFuse IC Benchmarking

## 1. Decision

Select the best-fit eFuse IC family from 2–3 supplier candidates by comparing their protection accuracy, thermal behaviour, diagnostic observability, and nuisance-trip exposure under identical application-representative load and fault profiles.

## 2. Trigger

- New zone controller platform entering concept phase — IC selection required before architecture freeze
- Second-source qualification — need to confirm that an alternative supplier's IC performs equivalently
- IC end-of-life notification — replacement candidate must be validated against existing calibration

## 3. Stakeholders

| Role | Who |
|---|---|
| **Decision owner** | Hardware architect + sourcing |
| **Data consumer** | eFuse Function Owner (protection-parameter impact), validation (bench-test scoping) |
| **Domain input** | Supplier (IC datasheet, application notes), load-spec owner (channel requirements) |

## 4. Problem

IC selection today is driven by datasheet comparisons: SCP accuracy (±15 % vs. ±20 %), maximum channel count, package size, and unit price. These parameters are necessary but insufficient. What matters in the application:

- **SCP accuracy spread:** A ±20 % IC on a 12 A channel means SCP could trigger anywhere from 9.6 A to 14.4 A — marginal for distinguishing inrush from overload.
- **I²T tolerance:** Datasheets specify typical; application needs worst-case across temperature.
- **Thermal shutdown interaction:** IC A shuts down at 175 °C with 10 ms deglitch; IC B at 150 °C with 50 ms. Under sustained load at 85 °C ambient, IC B may shut down healthy channels earlier.
- **Diagnostic current-sense accuracy:** ±10 % vs. ±15 % current measurement directly affects DTC rule precision.

None of these interactions are visible from datasheet alone. Bench comparison of 2–3 ICs across representative loads takes 3–6 weeks of lab time.

## 5. Why Synthetic Data

| Gap | How simulation fills it |
|---|---|
| **Controlled comparison** | Same load profile, same faults, same environment — only the IC model changes |
| **Speed** | Full comparison in hours, not weeks |
| **Parameter corners** | Can sweep IC parameter tolerances (SCP ±%, I²T ±%) to find worst-case interactions |
| **Cost** | No sample procurement; no bench booking |

## 6. Scenario Design

| Element | Specification |
|---|---|
| **IC candidates** | 2–3 IC families, each modelled with nominal + worst-case parameter corners |
| **Channels** | Same channel set across all candidates: high-current (PTC, defroster), medium (seat heater, window), low (LED, sensor supply), PWM (blower) |
| **Faults** | `short_to_ground`, `overload_spike`, `open_load`, `connector_aging` — same severity for each IC |
| **Protection config** | Same target thresholds; IC-specific mapping (e.g., IC A has 4-bit SCP DAC, IC B has analog trim) |
| **Environment** | −40 / +25 / +85 °C; 9 V / 12 V / 13.5 V |
| **Duration** | 60 s per scenario per IC candidate |

## 7. Required Signals

| Signal | Unit | Purpose |
|---|---|---|
| `current_a` | A | Current-sense accuracy comparison |
| `voltage_v` | V | Channel voltage drop comparison |
| `temperature_c` | °C | Die temperature under identical load |
| `trip_flag` | bool | Trip-point comparison |
| `protection_event` | enum | Event-type comparison (SCP vs. OCP path) |
| `retry_count` | int | Recovery-behaviour comparison |
| `efuse_family` | str | IC candidate identifier |
| `fault_type` | label | Ground truth |
| `config_id` | str | Parameter-corner identifier |

## 8. Key Metrics

| Metric | Direction | Target |
|---|---|---|
| Nuisance-trip rate delta between candidates | ↓ | Preferred IC ≤ 50 % of worst candidate |
| Fault detection rate (for identical DTC rules applied to each IC's telemetry) | ↑ | ≥ 95 % for all candidates (if not, IC's current-sense is too poor) |
| Thermal headroom at +85 °C under sustained load | ↑ | ≥ 20 °C to thermal shutdown for all channels |
| Parameter-corner worst case: SCP trip point range across tolerance band | ↓ (tighter is better) | Trip-point spread ≤ 30 % of nominal for critical channels |
| Number of channels requiring load-specific calibration overrides | ↓ | Preferred IC needs fewer overrides |

## 9. Decision Criteria

| Outcome | Action |
|---|---|
| One IC clearly dominates on nuisance trips, thermal headroom, and diagnostic fidelity | Select; proceed to commercial negotiation and bench confirmation |
| Two ICs equivalent on protection but one has better diagnostic accuracy | Select the one with better observability (downstream DTC benefit outweighs marginal cost difference) |
| All candidates fail thermal headroom on high-current channels | Escalate — may need IC with integrated thermal protection or PCB layout change |
| No candidate achieves nuisance-free operation on inrush-heavy loads | Escalate — load-specific inrush management (soft-start, current limiting) needed regardless of IC |

## 10. Dependencies

| Direction | Artefact |
|---|---|
| **Upstream** | IC datasheets with parameter tolerances from supplier |
| **Upstream** | Channel load specifications from feature owners |
| **Downstream** | [Threshold Calibration](../1-protection-design/threshold-and-retry-calibration.md) — selected IC determines calibration feasibility space |
| **Downstream** | [DTC Rule Engineering](../2-diagnostics/dtc-rule-engineering.md) — IC current-sense accuracy constrains rule precision |
| **Related** | [Thermal Headroom Validation](thermal-headroom-validation.md) — detailed thermal analysis for the selected IC |

## 11. Limitations

- IC models in the simulator are parameterised from datasheet values, not silicon-measured data. Process-corner effects beyond datasheet specification are not captured.
- Simulation does not model IC packaging and PCB thermal path — thermal headroom results are relative comparisons between ICs, not absolute die-temperature predictions.
- EMC behaviour (susceptibility to conducted/radiated noise) is outside the simulation model's scope. EMC screening remains a bench-only activity.
