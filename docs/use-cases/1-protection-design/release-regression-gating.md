# Release Regression Gating

## 1. Decision

Approve that a new software release has not degraded protection behaviour, nuisance-trip performance, or diagnostic observability compared to the previous release baseline.

## 2. Trigger

- Software release candidate ready for integration testing
- Application-layer change touches protection parameters, retry logic, or CAN signal scaling
- Middleware or driver update modifies eFuse IC communication timing

## 3. Stakeholders

| Role | Who |
|---|---|
| **Decision owner** | Software release manager + eFuse Function Owner |
| **Data consumer** | QA / validation team (go/no-go gate) |
| **Domain input** | Controls SW (change log for the release) |

## 4. Problem

Every software release risks silent regression: a threshold rounding change, a timing adjustment, or a CAN scaling update can shift protection behaviour without anyone noticing until field complaints arrive. Current practice is bench re-test on a small subset of channels — insufficient to catch subtle regressions across the full parameter space.

**Cost of a missed regression:** Field software update campaign (OTA or workshop visit) on affected vehicles — typically 6-figure EUR per incident depending on fleet size.

## 5. Why Synthetic Data

| Gap | How simulation fills it |
|---|---|
| **Reproducibility** | Fixed-seed scenario packs produce bit-identical stimuli — any telemetry delta is attributable to the SW change |
| **Coverage** | Golden pack covers all channel families × critical faults; bench can only spot-check |
| **Speed** | Runs in CI/CD pipeline overnight; bench regression suite takes days to schedule and execute |
| **Cost** | Zero hardware; zero lab booking |

## 6. Scenario Design

| Element | Specification |
|---|---|
| **Scenario pack** | "Golden pack" — frozen set of scenarios from the original [Threshold Calibration](threshold-and-retry-calibration.md) with fixed random seeds |
| **Channels** | All channel families represented (high-current, PWM, inrush-heavy, low-current always-on) |
| **Faults** | Baseline fault set: `short_to_ground`, `overload_spike`, `intermittent_overload`, `open_load`, `connector_aging` |
| **Protection parameters** | Baseline frozen config (no sweep — point comparison) |
| **Environment** | Three corners: cold (−40 °C / 9 V), nominal (+25 °C / 13.5 V), hot (+85 °C / 12 V) |
| **Duration** | Same as baseline run (60 s per scenario) |

## 7. Required Signals

| Signal | Unit | Purpose |
|---|---|---|
| `trip_flag` | bool | Core regression indicator |
| `protection_event` | enum | Regression in event type (e.g., SCP became OCP) |
| `retry_count` | int | Regression in retry behaviour |
| `current_a` | A | Detect scaling or offset drift |
| `voltage_v` | V | Detect supply-path regression |
| `temperature_c` | °C | Detect thermal-model drift |
| `fault_type` | label | Ground truth for detection-rate comparison |

## 8. Key Metrics

| Metric | Direction | Target |
|---|---|---|
| Protection-event delta vs baseline (new events not in baseline or missing events) | ↓ | 0 unexpected deltas |
| Nuisance-trip delta | ↓ | 0 new nuisance trips |
| Detection-rate delta (fault recall) | = | Within ±1 % of baseline |
| Retry-count delta (mean per fault family) | = | Within ±0.5 of baseline |
| Thermal-peak delta | = | Within ±2 °C of baseline |

## 9. Decision Criteria

| Outcome | Action |
|---|---|
| All deltas within tolerance | Release approved for integration bench test |
| Explainable deltas (e.g., intentional threshold change documented in release notes) | Accept with documented rationale; update golden baseline |
| Unexplained deltas | Block release; root-cause investigation required before re-submission |

## 10. Dependencies

| Direction | Artefact |
|---|---|
| **Upstream** | Golden scenario pack and baseline telemetry from [Threshold Calibration](threshold-and-retry-calibration.md) |
| **Upstream** | SW release candidate binary or config export |
| **Downstream** | Integration bench test plan (only triggered for approved releases) |
| **Related** | [DTC Rule Engineering](../2-diagnostics/dtc-rule-engineering.md) — if DTC logic is part of the release, detection metrics serve as DTC regression gate too |

## 11. Limitations

- Regression gating detects **behavioural** regressions observable in telemetry. It does not cover code-quality regressions (memory leaks, timing violations) — those require separate SW-quality tools.
- The golden pack covers the scenarios that were defined at calibration time. If a new operating mode was added (e.g., new power state), the golden pack must be extended to cover it.
- Bit-identical reproducibility depends on fixed random seeds and deterministic simulation. If the simulator changes version, the baseline must be regenerated.
