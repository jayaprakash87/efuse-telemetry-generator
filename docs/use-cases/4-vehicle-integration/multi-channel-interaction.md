# Multi-Channel Interaction

## 1. Decision

Identify and quantify cross-channel effects — shared-return voltage rise (virtual ground offset), simultaneous-activation thermal coupling, and current-redistribution during protection events — that invalidate single-channel analysis and may require topology or calibration changes.

## 2. Trigger

- Zone-controller topology defined with multiple high-current channels sharing a common ground return
- Single-channel calibration complete but system-level validation pending
- Field complaints of channel Y tripping when channel X activates (cross-coupling symptom)

## 3. Stakeholders

| Role | Who |
|---|---|
| **Decision owner** | Zone Controller HW architect + eFuse Function Owner |
| **Data consumer** | Validation (bench test focus), diagnostics team (cross-channel DTC impact) |
| **Domain input** | PCB layout engineer (ground path impedance), IC supplier (internal die sharing architecture) |

## 4. Problem

Most eFuse analysis — protection calibration, DTC rule design, thermal budgeting — treats each channel independently. On a real zone-controller PCB, channels interact:

- **Shared ground return:** 6 channels share a single ground trace back to the battery. When channel A draws 25 A through a 5 mΩ return path, the return voltage rises by 125 mV. Channel B's voltage reading is now offset by 125 mV — its DTC threshold for `ground_offset` may false-trigger, or a real ground fault on B may be masked.
- **Simultaneous activation thermal coupling:** Channels A and B are adjacent on the same eFuse die. A runs at 25 A continuous, heating the die. B has calibration validated at +85 °C ambient — but with A's 2 W of dissipation, the local die temperature is already +95 °C when B activates. B's thermal headroom is 10 °C less than expected.
- **Protection-event redistribution:** When channel A trips (SCP latch-off), its load current drops to zero. If A was on a voltage-regulated bus, the supply voltage rises — channels B, C, D see a sudden supply increase, which may cause momentary overcurrent on motor or PTC loads.

These effects are invisible in single-channel simulation and difficult to isolate on a bench (you see the symptom but not the cause).

## 5. Why Synthetic Data

| Gap | How simulation fills it |
|---|---|
| **Multi-channel co-simulation** | Simulation activates all channels simultaneously with realistic duty cycles and a shared ground model — single-channel bench tests cannot reproduce this |
| **Ground-path modelling** | Inject explicit ground-return impedance and measure the virtual ground offset across all channels |
| **Controlled fault interaction** | Trip one channel and measure the effect on all others — systematically, not as an accidental bench discovery |
| **Sweep** | Vary ground impedance, channel combinations, and fault timing to find worst-case interactions |

## 6. Scenario Design

| Element | Specification |
|---|---|
| **Topology** | Full zone-controller channel set with explicit shared-ground model: `ground_return_r_ohm` per path |
| **Channel combinations** | All channels active; then systematic pairwise and triplet high-current combinations |
| **Ground-return sweep** | `ground_return_r_ohm`: 1 / 5 / 10 / 20 mΩ (covers PCB quality range) |
| **Fault injection** | `ground_offset` on individual channels; simultaneous activation of worst-case pair; SCP trip on one channel while others are active |
| **Duty cycles** | Realistic: PTC continuous, seat heater cycling, blower PWM, window motor burst |
| **Environment** | +25 °C (isolate electrical interaction) and +85 °C (combined with thermal coupling) |
| **Duration** | 60 s per combination (captures activation transients and steady-state interaction) |

## 7. Required Signals

| Signal | Unit | Purpose |
|---|---|---|
| `current_a` | A | Per-channel current (detect redistribution) |
| `voltage_v` | V | Per-channel load-side voltage (detect virtual ground offset) |
| `ground_offset_v` | V | Calculated ground-return voltage rise |
| `temperature_c` | °C | Die temperature (detect thermal coupling) |
| `trip_flag` | bool | Cross-channel false trip detection |
| `protection_event` | enum | Which protection path triggered |
| `channel_id` | str | Channel identity for interaction mapping |
| `active_channels` | list | Which channels were active at each timestamp |

## 8. Key Metrics

| Metric | Direction | Target |
|---|---|---|
| Maximum virtual ground offset across all channel combinations | ↓ | < 100 mV (below DTC ground-offset detection threshold) |
| Cross-channel false trip rate (channel B trips because of channel A's activity) | ↓ | 0 |
| Thermal headroom reduction due to adjacent-channel dissipation | ↓ | ≤ 10 °C reduction vs. single-channel thermal analysis |
| Post-trip voltage redistribution overshoot on remaining channels | ↓ | < 5 % of nominal voltage (avoids triggering OVP on surviving channels) |
| Number of channel combinations requiring calibration adjustment for multi-channel effects | ↓ | Identify and enumerate (fewer is better) |

## 9. Decision Criteria

| Outcome | Action |
|---|---|
| Virtual ground offset < 100 mV and no cross-channel trips | Topology approved; single-channel calibration valid for system use |
| Ground offset 100–250 mV on specific combinations | Add ground-offset compensation to DTC rules for affected channels; or split ground return on PCB |
| Cross-channel false trips detected | Adjust SCP thresholds for affected channel pairs; add blanking during adjacent-channel activation |
| Thermal coupling reduces headroom below 5 °C | Apply findings from [Thermal Headroom Validation](../3-hardware-and-harness/thermal-headroom-validation.md); consider channel reallocation across ICs |

## 10. Dependencies

| Direction | Artefact |
|---|---|
| **Upstream** | PCB ground-return impedance from layout team |
| **Upstream** | Single-channel calibration from [Threshold Calibration](../1-protection-design/threshold-and-retry-calibration.md) |
| **Downstream** | System-level protection calibration adjustments (if needed) |
| **Downstream** | [DTC Rule Engineering](../2-diagnostics/dtc-rule-engineering.md) — ground-offset compensation rules |
| **Related** | [Thermal Headroom Validation](../3-hardware-and-harness/thermal-headroom-validation.md) — multi-channel thermal is related but focuses on IC die temp; this use case focuses on electrical interaction |

## 11. Limitations

- The shared-ground model is a lumped impedance. Real PCB ground paths have distributed resistance, inductance, and via transitions that can cause localised voltage gradients not captured by a single resistance value.
- Die-internal channel-to-channel coupling (within the IC silicon) is not modelled unless the IC model explicitly includes it. Most IC models treat channels as electrically independent at the die level.
- Power-supply impedance (battery + wiring to ZC) is modelled as ideal or simple Thévenin equivalent. Actual battery internal resistance and cable impedance affect voltage redistribution more than the zone-controller ground path for some scenarios.
