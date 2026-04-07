# Wiring & Connector Sizing

## 1. Decision

Set harness wire gauge and connector contact rating for each zone-controller channel with quantified evidence of voltage-drop margin, thermal margin, and diagnostic observability under realistic load profiles and degradation.

## 2. Trigger

- Zone controller architecture definition — harness specification must be committed before vehicle-level wiring freeze
- Cost-reduction initiative targeting harness weight or copper content
- Field warranty data showing connector-degradation-related failures on specific channels

## 3. Stakeholders

| Role | Who |
|---|---|
| **Decision owner** | Wiring harness team + cost engineering |
| **Data consumer** | Zone Controller HW team (integration), eFuse Function Owner (protection interaction) |
| **Domain input** | Load-spec owner (current profiles), connector supplier (contact resistance specs) |

## 4. Problem

Harness sizing is a three-way trade-off: **cost/weight** (thinner wire, smaller connector) vs. **voltage-drop margin** (thicker wire reduces drop) vs. **robustness to degradation** (more margin tolerates aging connectors longer).

Today, harness sizing uses static worst-case current analysis: peak current × safety factor → wire gauge from lookup table. This approach:

- **Over-designs low-risk channels** (e.g., LED supply at 0.5 A gets the same gauge as a motor because the table only has a few choices) → wasted copper, added weight.
- **Under-designs channels with dynamic profiles** (e.g., seat heater cycling between 0 and 12 A with 25 A inrush — steady-state analysis misses the thermal ratcheting effect on connector temperature).
- **Ignores diagnostic observability** — a "safe" gauge from a voltage-drop perspective may still mask diagnostic signals if connector aging adds 50 mΩ and the CAN resolution can't see the difference.

**Cost of over-design:** A 10 % harness weight reduction on a high-volume BEV saves €5–15 per vehicle in copper alone.
**Cost of under-design:** A connector failure at 60 000 km triggers a warranty repair (€300–800) and potential safety recall if the failure mode is fire-relevant.

## 5. Why Synthetic Data

| Gap | How simulation fills it |
|---|---|
| **Dynamic profiles** | Simulation runs realistic duty cycles (not just peak current), exposing thermal ratcheting and voltage-drop dynamics that static analysis misses |
| **Degradation sweep** | Can model connector resistance increasing from 1 mΩ to 100 mΩ over simulated vehicle life; bench testing a single connector aging profile takes months |
| **Combined effects** | Harness resistance + connector aging + ambient temperature + load duty cycle — all interacting simultaneously |
| **Diagnostic coupling** | Can measure whether a given gauge/connector combination still produces an observable diagnostic signature on CAN at production resolution |

## 6. Scenario Design

| Element | Specification |
|---|---|
| **Channels** | Group by current class: high (PTC 40 A, defroster 25 A), medium (seat heater 12 A, window motor 8 A), low (LED 0.5 A, sensor 0.1 A) |
| **Harness sweep** | `harness_r_ohm`: 5 / 10 / 20 / 50 / 100 mΩ (corresponds to different gauge/length combinations) |
| **Connector sweep** | `connector_r_ohm`: 0.5 / 2 / 5 / 10 / 50 mΩ (0.5 = new; 50 = severely aged) |
| **Degradation** | `connector_aging` fault: progressive increase at 0.5 / 1 / 2 mΩ per simulated week |
| **Load profiles** | Realistic duty cycles: heater 30 s on / 30 s off, motor window cycle (6 s burst), blower continuous PWM at 60 % |
| **Environment** | −40 / +25 / +85 °C (connector resistance increases at cold; wire resistance increases at hot) |
| **Duration** | 5–10 min simulated per combination (captures thermal steady-state under duty cycle) |

## 7. Required Signals

| Signal | Unit | Purpose |
|---|---|---|
| `current_a` | A | Load current under harness impedance |
| `voltage_v` | V | Supply-side and load-side voltage (difference = harness + connector drop) |
| `temperature_c` | °C | Harness/connector thermal estimate |
| `trip_flag` | bool | Did harness resistance cause a protection trip? |
| `fault_type` | label | `connector_aging`, `ground_offset` if injected |
| `harness_r_ohm` | Ω | Config: harness resistance setting |
| `connector_r_ohm` | Ω | Config: connector resistance setting |
| `channel_id` | str | Channel identity |

## 8. Key Metrics

| Metric | Direction | Target |
|---|---|---|
| Voltage-drop margin at load (V_supply − V_load − V_min_operating) | ↑ | ≥ 0.5 V under worst-case duty cycle + temperature |
| Connector-aging threshold: resistance at which first diagnostic alert triggers | ↓ (earlier is better) | Alert before connector reaches fire-risk temperature |
| Nuisance-trip rate caused by harness/connector impedance | ↓ | 0 under nominal + early-aging conditions |
| Copper weight saved vs. baseline (for channels where thinner gauge is safe) | ↑ | Report per-channel delta for cost rollup |
| Diagnostic observability: can CAN-reported current/voltage distinguish "healthy aged" from "fault" at chosen gauge? | ↑ | Yes/No per channel at production CAN resolution |

## 9. Decision Criteria

| Outcome | Action |
|---|---|
| Channel meets all margins with thinner gauge | Downgrade gauge; document evidence for harness spec review |
| Channel fails voltage margin at nominal gauge | Upgrade gauge or add connector quality requirement |
| Channel passes voltage but fails diagnostic observability | Flag for [CAN Telemetry Fidelity](../4-vehicle-integration/can-telemetry-fidelity.md) review — may need higher CAN resolution on this channel |
| Connector aging threshold is very early (alert at <10 mΩ increase) | Investigate whether alert threshold is nuisance-prone; consider relaxing if safety margin exists |

## 10. Dependencies

| Direction | Artefact |
|---|---|
| **Upstream** | Load duty-cycle specifications from feature owners |
| **Upstream** | Connector resistance specs and aging curves from supplier |
| **Downstream** | Harness specification document (gauge per channel, connector rating) |
| **Downstream** | [DTC Rule Engineering](../2-diagnostics/dtc-rule-engineering.md) — connector-aging diagnostic rules need to know the expected resistance range |
| **Related** | [Thermal Headroom Validation](thermal-headroom-validation.md) — harness thermal contribution affects IC die temperature budget |

## 11. Limitations

- Simulation uses a lumped-resistance model for the harness; distributed effects (skin effect at high frequency, proximity effect in bundled cables) are not modelled.
- Connector aging model is linear progression; real connector degradation may be non-linear (e.g., fretting corrosion with step changes).
- Physical routing, bundling, and environmental sealing are not modelled — mechanical and environmental factors driving harness failure require separate analysis.
- Final gauge selection must still satisfy OEM wiring standards (e.g., LV 112, VW 80000) regardless of simulation evidence.
