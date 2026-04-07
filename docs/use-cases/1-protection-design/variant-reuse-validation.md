# Variant Reuse Validation

## 1. Decision

Confirm that an existing protection calibration is still safe and nuisance-free when a new load variant, regional option, or supplier substitution is added to the topology.

## 2. Trigger

- New vehicle variant adds or replaces a load (e.g., heated steering wheel, upgraded seat heater, regional auxiliary heater)
- Second-source supplier change alters inrush profile or steady-state current
- Late program change (option package, market adaptation) modifies the channel mix on an already-frozen zone controller

## 3. Stakeholders

| Role | Who |
|---|---|
| **Decision owner** | Platform / variant management + eFuse Function Owner |
| **Data consumer** | Validation team (scopes bench delta-test) |
| **Domain input** | Feature owner (new load spec), supplier (new IC/load datasheet) |

## 4. Problem

Platform programs reuse zone-controller calibrations across dozens of variants. When a new load is added late — or a supplier change shifts the inrush profile — nobody knows whether the existing thresholds still provide adequate protection without nuisance trips. Today the options are:

1. **Assume it's fine** → risk field nuisance trips or protection gaps discovered at integration.
2. **Full recalibration** → expensive, slow, blocks the variant launch.
3. **Quick bench check** → covers only the new channel, misses cross-channel thermal interactions.

**Cost of getting it wrong:** A single nuisance-trip pattern on a high-volume variant can trigger a field campaign (software update to thousands of vehicles).

## 5. Why Synthetic Data

| Gap | How simulation fills it |
|---|---|
| **Speed** | Variant validation in hours, not the weeks needed for new bench booking |
| **Coverage** | Tests the new load alongside existing loads under combined thermal and fault conditions — bench tests are usually single-channel |
| **Combinatorics** | Dozens of variant × ambient × fault combinations are impractical on bench |

## 6. Scenario Design

| Element | Specification |
|---|---|
| **Channels** | Full existing channel set + the new/changed load |
| **Faults** | Same fault families as original calibration: `short_to_ground`, `overload_spike`, `intermittent_overload`, `connector_aging` |
| **Protection parameters** | Fixed — use the frozen baseline from [Threshold Calibration](threshold-and-retry-calibration.md) |
| **Variant delta** | New load's nominal current, inrush profile, duty cycle; changed harness path if applicable |
| **Environment** | Same ambient/supply envelope: −40 / +25 / +85 °C; 9.0 / 12.0 / 13.5 V |
| **Duration** | 60 s per scenario; include simultaneous multi-channel activation (worst-case thermal) |

## 7. Required Signals

| Signal | Unit | Purpose |
|---|---|---|
| `current_a` | A | Compare new-load inrush against existing SCP threshold |
| `voltage_v` | V | Detect voltage-sag from new load's current draw |
| `temperature_c` | °C | Die temperature under combined load (thermal interaction) |
| `trip_flag` | bool | Any trip not present in the baseline run |
| `protection_event` | enum | Type of trip if it occurs |
| `channel_id` | str | Distinguish new channel from existing |
| `load_name` | str | New load identity |

## 8. Key Metrics

| Metric | Direction | Target |
|---|---|---|
| New nuisance trips introduced (trips that did not occur in baseline run) | ↓ | 0 |
| Fault detection rate on new channel | ↑ | ≥ 95 % (matches baseline family target) |
| Die-temperature increase vs baseline (combined load) | ↓ | < 5 °C increase at +85 °C ambient |
| Cross-channel trip rate (existing channels tripping due to new load's thermal/voltage impact) | ↓ | 0 |

## 9. Decision Criteria

| Outcome | Action |
|---|---|
| Zero new nuisance trips, detection rate met, thermal delta < 5 °C | Approve variant with existing calibration; skip full recalibration |
| New channel trips on inrush but others OK | Add channel-specific inrush override; bench-confirm that channel only |
| Cross-channel thermal or voltage impact | Full recalibration needed; escalate schedule impact to program management |

## 10. Dependencies

| Direction | Artefact |
|---|---|
| **Upstream** | Frozen baseline calibration from [Threshold Calibration](threshold-and-retry-calibration.md) |
| **Upstream** | New load specification (from feature owner or supplier) |
| **Downstream** | Bench delta-test plan (only channels flagged by simulation need physical test) |
| **Related** | [Thermal Headroom Validation](../3-hardware-and-harness/thermal-headroom-validation.md) — if thermal delta is close to limit |

## 11. Limitations

- Simulation models thermal coupling via simplified zone-level thermal resistance; actual PCB layout, heatsink geometry, and airflow are not modelled.
- If the variant changes the harness path (different connector, longer cable run), the harness model must be updated — the default config assumes the baseline harness.
- Approval for safety-critical channels still requires at least one physical confirmation, regardless of simulation outcome.
