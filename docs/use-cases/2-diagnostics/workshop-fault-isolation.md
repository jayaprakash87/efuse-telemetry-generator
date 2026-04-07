# Workshop Fault Isolation

## 1. Decision

Approve fault-isolation playbooks for the service network by confirming that each playbook's diagnostic steps can reliably distinguish the target fault from confusable alternatives using production-available telemetry.

## 2. Trigger

- New zone controller entering production — service documentation required before SOP
- Warranty data shows high no-fault-found (NFF) rate or repeated visits for the same symptom
- New fault pattern discovered in field with no existing isolation procedure

## 3. Stakeholders

| Role | Who |
|---|---|
| **Decision owner** | Aftersales engineering |
| **Data consumer** | Workshop technicians (follow the playbooks), service tooling (integrates diagnostic steps) |
| **Domain input** | Diagnostics team (DTC rules), eFuse Function Owner (expected fault signatures) |

## 4. Problem

Workshop fault isolation for eFuse-related symptoms is unreliable today:

- **Symptom overlap:** "Channel not powering load" could be open-load, blown connector, ground-path degradation, or latched protection trip. The technician sees the same dead load.
- **Generic documentation:** Service manuals say "check connector, check ground, replace ECU" without evidence-based decision trees.
- **No reference waveforms:** Technicians lack "this is what a healthy channel looks like vs. this specific fault" traces for their diagnostic tool.

**Cost:** No-fault-found (NFF) rate on eFuse-related service visits is typically 15–30 %. Each NFF visit costs €200–500 (labour + diagnostics time + unnecessary part if technician guesses wrong).

## 5. Why Synthetic Data

| Gap | How simulation fills it |
|---|---|
| **Paired examples** | Simulation produces matched healthy/faulty traces on the same channel under identical conditions — impossible to get systematically from field data |
| **All fault types covered** | Field data is biased toward common faults; rare faults (e.g., `ground_offset` at 100 mΩ) may never appear in workshop records |
| **Controlled confusion cases** | Can deliberately generate the exact scenarios that confuse technicians: "connector aging that looks like open load" or "ground offset that looks like overload" |

## 6. Scenario Design

| Element | Specification |
|---|---|
| **Focus** | The 5–8 most confused fault pairs identified from warranty data or DTC rule analysis |
| **Channels** | High-current (seat heater, defroster) and motor loads (window, mirror) — most service-relevant |
| **Fault pairs** | `open_load` vs. `connector_aging`; `ground_offset` vs. `overload`; `short_to_ground` vs. `latch-off from prior event`; `voltage_sag` (supply) vs. `high-resistance path` (harness) |
| **For each pair** | Generate: (a) healthy baseline, (b) fault A at detectable severity, (c) fault B at similar symptom severity |
| **Service-observable signals only** | Restrict to signals available on production diagnostic tools (CAN-reported current, voltage, DTC status, trip counter) |
| **Duration** | 30–60 s per trace (enough for load-on → steady state → fault manifestation → protection response) |

## 7. Required Signals

| Signal | Unit | Purpose |
|---|---|---|
| `current_a` | A | Primary workshop-observable signal |
| `voltage_v` | V | Distinguishes supply-side vs. load-side problems |
| `trip_flag` | bool | Whether protection activated |
| `protection_event` | enum | Event type (helps narrow root cause) |
| `retry_count` | int | Retry pattern is a disambiguator (hard short = no recovery; intermittent = recovers then re-trips) |
| `fault_type` | label | Ground truth (not shown to technician; used for playbook validation) |
| `state_on_off` | bool | Load command state (distinguishes commanded-off from open-load) |

## 8. Key Metrics

| Metric | Direction | Target |
|---|---|---|
| Correct fault identification rate (playbook leads to correct root cause on simulated data) | ↑ | ≥ 90 % across all confusion pairs |
| Average diagnostic steps to isolation | ↓ | ≤ 4 steps for 80 % of cases |
| No-fault-found exposure (playbook says "fault" but trace is actually healthy) | ↓ | < 5 % |
| Fault pairs remaining ambiguous after playbook (neither distinguishable with available signals) | ↓ | 0 for safety-relevant faults; ≤ 1 pair for comfort faults |

## 9. Decision Criteria

| Outcome | Action |
|---|---|
| All confusion pairs resolvable, ≤ 4 steps | Approve playbooks for service release; include reference waveform images from simulation |
| Some pairs require > 4 steps but are resolvable | Simplify decision tree; consider adding a calculated signal in service tool |
| A confusion pair is fundamentally unresolvable with CAN signals | Escalate: either add a dedicated diagnostic signal to CAN layout or accept the NFF exposure and document workaround |

## 10. Dependencies

| Direction | Artefact |
|---|---|
| **Upstream** | Validated DTC rules from [DTC Rule Engineering](dtc-rule-engineering.md) — playbooks build on what the DTC system reports |
| **Upstream** | Warranty/NFF data identifying the most confused fault pairs (if available) |
| **Downstream** | Service manual content, diagnostic-tool software update |
| **Related** | [CAN Telemetry Fidelity](../4-vehicle-integration/can-telemetry-fidelity.md) — if signals are too coarse to disambiguate, fidelity improvement is the upstream fix |

## 11. Limitations

- Playbook validation assumes the diagnostic tool displays signals at CAN-available resolution. If the tool further filters or aggregates, on-screen traces may differ from simulation predictions.
- Simulation does not model technician behaviour (e.g., skipping steps, misreading displays). Playbook usability testing with real technicians is still recommended.
- Multi-fault scenarios (e.g., connector aging + ground offset simultaneously) are rare but produce confusing symptoms; these are outside the standard confusion-pair scope unless explicitly requested.
