# Degradation Early Warning

## 1. Decision

Engineer and validate predictive features — computed from CAN-available eFuse telemetry — that detect progressive degradation (connector aging, ground-path resistance increase, thermal drift) before it causes a protection trip or a customer-visible failure.

## 2. Trigger

- Fleet analytics team building a predictive-maintenance model for eFuse-related failures
- Warranty data shows that 60 %+ of eFuse-related returns have long degradation lead time (weeks to months) before hard failure
- Cloud data pipeline in place to ingest eFuse CAN signals at scale

## 3. Stakeholders

| Role | Who |
|---|---|
| **Decision owner** | Fleet analytics / data science team lead |
| **Data consumer** | Cloud analytics platform (deploys feature-extraction pipeline), service planning (triggers proactive recalls) |
| **Domain input** | eFuse Function Owner (degradation physics), diagnostics team (DTC correlation) |

## 4. Problem

Progressive degradation — connector aging, ground-path corrosion, thermal-interface deterioration — accounts for the majority of eFuse-related field failures. These failures don't happen suddenly: current drift, voltage offset, and temperature rise evolve over weeks or months before the channel trips or the connector overheats.

In theory, a fleet analytics model could detect these trends early and trigger proactive service before the failure becomes customer-visible. In practice:

- **No labelled training data:** Real fleet data has millions of "healthy" samples and almost zero confirmed "degrading" samples with a known degradation type and severity.
- **Feature engineering is blind:** Data scientists don't know which computed features (rolling mean, variance, slope, cross-channel ratio) are physically meaningful for eFuse degradation — so they test hundreds of features, most of which are noise.
- **Threshold setting is arbitrary:** Without a ground-truth severity scale, there's no principled way to set the alert threshold between "normal variation" and "degradation needing service."

## 5. Why Synthetic Data

| Gap | How simulation fills it |
|---|---|
| **Labels** | Every simulated degradation episode has a ground-truth label: type, severity, progression rate, and time-to-failure |
| **Volume** | Generate 10 000+ labelled degradation trajectories in hours; field may have 10 confirmed cases per year |
| **Feature validation** | Test whether a candidate feature (e.g., 30-day current slope) actually separates connector aging from normal seasonal variation — because you know the ground truth |
| **Threshold calibration** | Set the alert threshold at the severity level where the feature reliably separates healthy from degrading, then validate with real field data as it arrives |

## 6. Scenario Design

| Element | Specification |
|---|---|
| **Channels** | High-current (heater, defroster) and motor loads (most susceptible to connector degradation in field data) |
| **Degradation types** | `connector_aging` (progressive +0.5 / +1 / +2 mΩ per day), `ground_offset` (progressive +1 / +5 mΩ per day), `thermal_interface_degradation` (progressive +0.1 °C/W per week) |
| **Healthy baseline** | Same channels, same operating profile, no degradation — for class-balance and feature calibration |
| **Duration** | Simulated 30 / 60 / 90 days (at accelerated time, capturing daily drive cycles with ambient variation) |
| **Seasonal variation** | Ambient temperature follows a realistic daily/seasonal profile (to separate degradation trend from thermal variation) |
| **CAN constraints** | Apply CAN quantisation from [CAN Telemetry Fidelity](../4-vehicle-integration/can-telemetry-fidelity.md) — features must work at production resolution |

## 7. Required Signals

| Signal | Unit | Purpose |
|---|---|---|
| `current_a` | A | Primary feature source (at CAN resolution) |
| `voltage_v` | V | Primary feature source |
| `temperature_c` | °C | Ambient and die temp for temperature compensation |
| `fault_type` | label | Ground-truth degradation type |
| `severity` | float | Ground-truth degradation magnitude at each timestep |
| `time_to_failure` | float | Days until protection trip or hard failure (if progression continues) |
| `channel_id` | str | Channel identity |
| `drive_cycle_id` | int | For aggregating per-cycle features |

## 8. Key Metrics

| Metric | Direction | Target |
|---|---|---|
| Feature separation (AUROC or similar) between healthy and degrading at 50 % of failure severity | ↑ | ≥ 0.90 for `connector_aging`; ≥ 0.85 for `ground_offset` |
| Early-warning lead time (days before hard failure at which the feature crosses the alert threshold) | ↑ | ≥ 14 days for `connector_aging` (typical field warranty response time) |
| False-alert rate on healthy fleet (feature crosses threshold for non-degrading channels) | ↓ | < 1 % over 90 days |
| Feature robustness to CAN quantisation (AUROC drop when evaluated at production resolution vs. full resolution) | ↓ | ≤ 5 % AUROC drop |

## 9. Decision Criteria

| Outcome | Action |
|---|---|
| Feature exceeds all targets at CAN resolution | Deploy to fleet analytics pipeline; begin shadow-mode evaluation on production data |
| Feature works at full resolution but fails at CAN resolution | Feed back to [CAN Telemetry Fidelity](../4-vehicle-integration/can-telemetry-fidelity.md) — justify higher resolution for this channel; or explore cross-channel features that are less resolution-sensitive |
| Feature achieves early warning but false-alert rate too high | Add temperature compensation or load-state guard to reduce false alerts during seasonal transitions |
| No feature achieves useful separation for a degradation type | That degradation type cannot be detected from CAN telemetry alone; explore dedicated diagnostic session (e.g., off-board impedance measurement) |

## 10. Dependencies

| Direction | Artefact |
|---|---|
| **Upstream** | CAN resolution constraints from [CAN Telemetry Fidelity](../4-vehicle-integration/can-telemetry-fidelity.md) |
| **Upstream** | Degradation physics from domain reference (connector aging model, ground-path corrosion rates) |
| **Downstream** | Fleet analytics prediction pipeline |
| **Downstream** | Proactive service planning (when fleet alerts trigger workshop scheduling) |
| **Related** | [DTC Rule Engineering](../2-diagnostics/dtc-rule-engineering.md) — DTC rules detect hard faults; this use case detects soft degradation before DTC-level severity is reached |
| **Related** | [Field-Driven Recalibration](field-driven-recalibration.md) — fleet data that confirms degradation predictions may also trigger recalibration |

## 11. Limitations

- Synthetic degradation models are linear or parameterised progressions. Real degradation may be non-linear (e.g., fretting corrosion with sudden step changes) or influenced by factors outside the model (vibration, humidity, chemical exposure).
- Feature performance on synthetic data is an upper bound. Real fleet data has additional noise sources (diagnostic tool jitter, OBD interactions, ECU sleep/wake artefacts) not modelled in simulation.
- Model deployment (cloud pipeline, OTA update, service-network integration) is outside the scope of this use case. This use case produces a validated feature and threshold, not a production system.
