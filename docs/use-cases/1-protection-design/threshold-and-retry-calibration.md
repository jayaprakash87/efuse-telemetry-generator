# Threshold & Retry Calibration

## 1. Decision

Freeze SCP, OCP, I²T, retry-count, cooldown, and latch-off parameters for each channel family before A-sample hardware is available for full bench characterisation.

## 2. Trigger

- A-sample or B-sample hardware freeze approaching
- Bench queue is full; protection parameter selection cannot wait for physical testing
- New IC family selected and no prior calibration data exists

## 3. Stakeholders

| Role | Who |
|---|---|
| **Decision owner** | eFuse Function Owner |
| **Data consumer** | Controls SW team (implements thresholds in application layer) |
| **Domain input** | Hardware architect (load specs), safety team (minimum coverage) |

## 4. Problem

Protection parameters interact in non-obvious ways. Raising the SCP threshold reduces nuisance trips on inrush-heavy loads (seat heater, PTC) but weakens short-circuit coverage. Extending I²T tolerance avoids tripping on warm-start transients but delays detection of genuine overcurrent. Retry count trades availability against wiring thermal stress.

Today these trade-offs are resolved by bench trial-and-error on a small number of loads. The result is either over-conservative thresholds (nuisance trips in the field) or late rework when integration testing exposes gaps.

**Cost of deciding without data:** 2–4 additional bench-iteration cycles, each costing 1–3 weeks of lab time.
**Cost of waiting:** Hardware freeze slips; downstream SW integration blocked.

## 5. Why Synthetic Data

| Gap | How simulation fills it |
|---|---|
| **Availability** | A-sample hardware does not exist yet; simulation provides channel-level telemetry months earlier |
| **Coverage** | Bench can test 3–5 load/fault combinations per day; simulation sweeps hundreds overnight |
| **Labels** | Every simulated trip carries a ground-truth fault label — bench trips require manual root-cause analysis |
| **Speed** | Full threshold × fault × load matrix in hours, not weeks |

## 6. Scenario Design

| Element | Specification |
|---|---|
| **Channels** | Seat heater (12 A nom), rear defroster (25 A nom), PTC heater (40 A nom), power window (8 A nom, high inrush), HVAC blower (6 A PWM) |
| **Faults** | `short_to_ground` (hard, 0.1 Ω), `overload_spike` (1.5× nom, 2 s), `intermittent_overload` (1.2× nom, cycling), `connector_aging` (gradual +50 mΩ/week) |
| **Protection sweep** | `scp_threshold_a`: nom ×{1.5, 2.0, 2.5, 3.0}; `i2t_threshold_a2s`: {50, 100, 200, 500}; `max_retries`: {1, 3, 5}; `cooldown_s`: {0.5, 1.0, 2.0} |
| **Environment** | Ambient: −40 °C, +25 °C, +85 °C; supply: 12.0 V, 13.5 V, 9.0 V (cranking sag) |
| **Duration** | 60 s per scenario (captures inrush → steady-state → fault → protection → recovery) |
| **Topology** | Single zone controller, 6-channel eFuse IC, shared ground return |

## 7. Required Signals

| Signal | Unit | Purpose |
|---|---|---|
| `current_a` | A | Load current including inrush transients |
| `voltage_v` | V | Supply-side and load-side voltage |
| `temperature_c` | °C | eFuse die temperature estimate |
| `trip_flag` | bool | Whether the channel tripped |
| `protection_event` | enum | SCP / OCP / I²T / OTP / latch-off |
| `retry_count` | int | Retries before latch or recovery |
| `fault_type` | label | Injected fault ground truth |
| `severity` | float | Fault magnitude (Ω, A, or ratio) |
| `channel_id` | str | Channel under test |
| `load_name` | str | Physical load identity |
| `config_id` | str | Protection-parameter set ID |

## 8. Key Metrics

| Metric | Direction | Target |
|---|---|---|
| Nuisance-trip rate (trips during normal operation incl. inrush) | ↓ | < 1 per 10 000 cycles per channel |
| Fault detection rate (trips on genuine faults) | ↑ | ≥ 99 % for `short_to_ground`, ≥ 95 % for `overload_spike` |
| Mean retry count before latch-off on hard short | ↓ | ≤ 2 |
| Thermal headroom at trip (T_die vs T_shutdown) | ↑ | ≥ 15 °C margin at +85 °C ambient |
| Parameter sets meeting all four criteria above | ↑ | ≥ 1 viable set per channel family |

## 9. Decision Criteria

| Outcome | Action |
|---|---|
| ≥ 1 parameter set passes all KPIs for every channel family | Freeze as baseline; schedule bench confirmation on top-3 critical channels |
| Some channel families fail | Narrow sweep; consider load-specific overrides for failing channels |
| No parameter set passes | Escalate — protection strategy may need architectural change (e.g., separate SCP + I²T IC, or load-specific retry policy) |

## 10. Dependencies

| Direction | Artefact |
|---|---|
| **Upstream** | Load specification (nominal current, inrush profile, duty cycle) from feature owners |
| **Upstream** | IC datasheet (SCP accuracy ±%, I²T tolerance, thermal shutdown point) from supplier |
| **Downstream** | [Release Regression Gating](release-regression-gating.md) — frozen thresholds become the golden baseline |
| **Downstream** | [DTC Rule Engineering](../2-diagnostics/dtc-rule-engineering.md) — protection events feed diagnostic rule design |
| **Related** | [Variant Reuse Validation](variant-reuse-validation.md) — reuses same methodology for new load mixes |

## 11. Limitations

- Simulation assumes ideal IC behaviour within datasheet tolerance; silicon-specific quirks (e.g., SCP blanking-time variation across process corners) require bench confirmation.
- Inrush profiles are modelled from load-class averages; actual inrush depends on specific motor/heater part number and harness impedance.
- Final release of thresholds to production still requires supplier sign-off and at least one bench confirmation per channel family.
