# CAN Telemetry Fidelity

## 1. Decision

Set CAN signal resolution (bit width), sampling interval, and message scheduling for eFuse telemetry signals such that degradation-relevant features are preserved — without exceeding the available CAN bandwidth budget.

## 2. Trigger

- CAN database (DBC) definition phase — signal layout being negotiated with the network team
- Diagnostics team reports that DTC rules cannot distinguish fault types at current CAN resolution
- Network team requests bandwidth reduction and proposes coarser signal packing

## 3. Stakeholders

| Role | Who |
|---|---|
| **Decision owner** | Network / CAN architecture team + eFuse Function Owner |
| **Data consumer** | Diagnostics team (DTC rules operate on CAN-quantised data), fleet analytics (degradation models) |
| **Domain input** | IC supplier (raw sensor accuracy), eFuse FO (which signals are diagnostic-critical) |

## 4. Problem

CAN bandwidth on a zone-controller bus is finite and contested. Every signal competes for space. The network team's incentive is to pack signals as compactly as possible — reduce resolution from 16-bit to 8-bit, reduce sampling from 10 ms to 100 ms, aggregate channels into coarser messages.

The consequence for diagnostics:

- **Quantisation destroys signatures:** `connector_aging` adds 20–50 mΩ to a 12 A channel → +0.24 to +0.60 A current increase. At 0.5 A CAN resolution (8-bit, 0–128 A range), this degradation is invisible — it rounds to the same CAN value as healthy operation.
- **Sampling aliasing misses transients:** A 10 ms protection trip followed by 200 ms retry is visible at 10 ms CAN sampling but invisible at 100 ms. DTC rules can't confirm a retry pattern they can't see.
- **Diagnostic feature loss is irreversible:** Once the DBC is frozen and hardware is in vehicles, the resolution cannot be improved (no OTA update changes CAN message layout).

Today this trade-off is resolved by "gut feel" or precedent from previous programs. There is no systematic way to test what resolution is "good enough" before the DBC is frozen.

## 5. Why Synthetic Data

| Gap | How simulation fills it |
|---|---|
| **Ground-truth comparison** | Simulate at full-resolution "truth" → apply CAN quantisation → measure how much diagnostic information is lost. This is impossible with real CAN data (you never have the unquantised truth) |
| **Sweep resolution** | Test 8 / 10 / 12 / 16-bit current resolution and 10 / 20 / 50 / 100 ms sampling in a full factorial — quantify the diagnostic cost of each reduction |
| **Fault-specific sensitivity** | Different faults need different resolution: `short_to_ground` (large signal, low resolution OK) vs. `connector_aging` (tiny signal, needs high resolution). Simulation maps the minimum-viable resolution per fault family |

## 6. Scenario Design

| Element | Specification |
|---|---|
| **Channels** | Representative per load family (high-current, PWM, motor, low-current) |
| **Faults** | `connector_aging` (subtle, 20–100 mΩ), `ground_offset` (subtle, 50–200 mΩ), `short_to_ground` (large), `open_load` (large), `intermittent_overload` (transient) |
| **Full-resolution baseline** | Simulate at 1 ms / 16-bit (simulator native resolution) |
| **CAN quantisation sweep** | Apply post-processing: current resolution {0.1, 0.25, 0.5, 1.0} A; voltage resolution {0.05, 0.1, 0.25} V; sampling interval {10, 20, 50, 100} ms |
| **DTC rule evaluation** | Apply the same DTC rules (from [DTC Rule Engineering](../2-diagnostics/dtc-rule-engineering.md)) to full-resolution and each quantised version; compare precision/recall |
| **Environment** | Nominal only (resolution sensitivity is independent of ambient temp for this purpose) |

## 7. Required Signals

| Signal | Unit | Purpose |
|---|---|---|
| `current_a` (full-res) | A | Truth signal |
| `current_a` (quantised) | A | CAN-resolution signal for comparison |
| `voltage_v` (full-res) | V | Truth signal |
| `voltage_v` (quantised) | V | CAN-resolution signal for comparison |
| `fault_type` | label | Ground truth for detection-rate measurement |
| `severity` | float | For threshold-sensitivity analysis |
| `can_resolution_config` | str | Which quantisation setting was applied |

## 8. Key Metrics

| Metric | Direction | Target |
|---|---|---|
| Detection recall delta: (full-res recall − quantised recall) per fault family | ↓ | ≤ 5 % recall loss for safety-relevant faults |
| Minimum current resolution that preserves `connector_aging` detection at ≥ 85 % recall | ↓ (finer is more expensive but needed) | Report the value (e.g., 0.25 A) |
| Minimum sampling interval that preserves retry-pattern recognition | ↓ | Report the value (e.g., 20 ms) |
| CAN bandwidth consumed at chosen resolution/rate vs. network budget | ↓ | Within allocated bandwidth (typically 5–15 % of bus for eFuse telemetry) |

## 9. Decision Criteria

| Outcome | Action |
|---|---|
| A resolution/rate combination meets diagnostic targets within bandwidth budget | Freeze DBC signal definition; document diagnostic justification for the chosen resolution |
| Diagnostic targets require more bandwidth than allocated | Negotiate with network team: present recall-loss data to justify additional bandwidth |
| Subtle faults (`connector_aging`) are undetectable at any feasible CAN resolution | Accept the limitation; document that these faults require off-board analytics (cloud-based fleet models) or a dedicated diagnostic session on higher-res interface |

## 10. Dependencies

| Direction | Artefact |
|---|---|
| **Upstream** | DTC rules from [DTC Rule Engineering](../2-diagnostics/dtc-rule-engineering.md) (rules to evaluate at each resolution) |
| **Upstream** | CAN bandwidth budget from network team |
| **Downstream** | CAN DBC specification (frozen signal definition) |
| **Downstream** | [Workshop Fault Isolation](../2-diagnostics/workshop-fault-isolation.md) — playbooks must account for CAN resolution limits |
| **Downstream** | [Degradation Early Warning](../6-field-and-fleet/degradation-early-warning.md) — fleet analytics models train on CAN-resolution data |

## 11. Limitations

- Simulation applies ideal quantisation (floor/round). Real CAN implementations may add jitter, message-loss, and bus-arbitration delays that further degrade signal quality.
- DTC rules evaluated here operate on single-channel signals. System-level DTCs that correlate across channels or ECUs are outside this scope.
- This use case optimises for diagnostic value. Other CAN signal consumers (e.g., HMI displays, energy management) may have different resolution requirements that also compete for bandwidth.
