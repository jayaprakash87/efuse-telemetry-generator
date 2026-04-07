# eFuse Telemetry Use-Case Library

This library contains **15 use cases** organised by the **engineering decision** each one supports — not by department, lifecycle phase, or cost category.

Every use case follows the same [template](_template.md): one decision, one trigger, measurable KPIs, explicit pass/fail criteria, and honest limitations.

---

## Decision Navigator

Start from the question you need to answer:

```
What decision do I need to make?
│
├─ "Will my protection strategy work?"
│   └─ 1-protection-design/
│       ├─ Threshold & Retry Calibration ─── freeze SCP/I²T/retry before hardware
│       ├─ Variant Reuse Validation ──────── confirm cal is safe for new load/variant
│       └─ Release Regression Gating ─────── approve SW release hasn't broken protection
│
├─ "Can I detect and isolate faults?"
│   └─ 2-diagnostics/
│       ├─ DTC Rule Engineering ──────────── design and validate DTC rules with precision/recall
│       └─ Workshop Fault Isolation ──────── build evidence-based troubleshooting playbooks
│
├─ "Is my hardware robust enough?"
│   └─ 3-hardware-and-harness/
│       ├─ eFuse IC Benchmarking ─────────── select best IC from 2–3 candidates
│       ├─ Wiring & Connector Sizing ─────── set gauge/connector with margin evidence
│       └─ Thermal Headroom Validation ───── confirm die temp stays in budget
│
├─ "Does eFuse work in the vehicle system?"
│   └─ 4-vehicle-integration/
│       ├─ Powernet Disturbance Resilience ─ survive crank, load-dump, jump-start
│       ├─ CAN Telemetry Fidelity ────────── set CAN resolution to preserve diagnostics
│       └─ Multi-Channel Interaction ─────── find shared-return and thermal coupling effects
│
├─ "Can I prove compliance?"
│   └─ 5-compliance-and-safety/
│       ├─ Safety Coverage Mapping ────────── find untested FMEA combinations
│       └─ Pre-Certification Screening ───── rank stress scenarios for bench priority
│
└─ "What's happening in the field?"
    └─ 6-field-and-fleet/
        ├─ Degradation Early Warning ──────── engineer predictive features for fleet analytics
        └─ Field-Driven Recalibration ─────── validate threshold fixes before OTA deployment
```

---

## By Stakeholder

| If you are a… | Start here |
|---|---|
| **eFuse Function Owner** | [Threshold Calibration](1-protection-design/threshold-and-retry-calibration.md), then [DTC Rule Engineering](2-diagnostics/dtc-rule-engineering.md) |
| **Hardware architect** | [IC Benchmarking](3-hardware-and-harness/efuse-ic-benchmarking.md), [Thermal Headroom](3-hardware-and-harness/thermal-headroom-validation.md) |
| **Wiring harness team** | [Wiring & Connector Sizing](3-hardware-and-harness/wiring-and-connector-sizing.md) |
| **Diagnostics / DTC team** | [DTC Rule Engineering](2-diagnostics/dtc-rule-engineering.md), [Workshop Fault Isolation](2-diagnostics/workshop-fault-isolation.md) |
| **Powernet team** | [Powernet Disturbance Resilience](4-vehicle-integration/powernet-disturbance-resilience.md) |
| **CAN / network architect** | [CAN Telemetry Fidelity](4-vehicle-integration/can-telemetry-fidelity.md) |
| **Validation / test planner** | [Pre-Certification Screening](5-compliance-and-safety/pre-certification-screening.md) |
| **Safety / FMEA engineer** | [Safety Coverage Mapping](5-compliance-and-safety/safety-coverage-mapping.md) |
| **Fleet analytics / data science** | [Degradation Early Warning](6-field-and-fleet/degradation-early-warning.md) |
| **Quality / warranty team** | [Field-Driven Recalibration](6-field-and-fleet/field-driven-recalibration.md) |
| **Platform / variant manager** | [Variant Reuse Validation](1-protection-design/variant-reuse-validation.md) |
| **SW release manager** | [Release Regression Gating](1-protection-design/release-regression-gating.md) |

---

## Dependency Map

Use cases are not independent — decisions flow from architecture through to field operations.

```
IC Benchmarking ──────┐
                      ├──→ Threshold Calibration ──→ Release Regression Gating
Wiring & Connector ───┤         │                            │
Sizing                │         ↓                            ↓
                      │    DTC Rule Engineering ──→ Workshop Fault Isolation
Thermal Headroom ─────┘         │
                                ↓
Powernet Disturbance ──→ Multi-Channel ──→ Variant Reuse Validation
Resilience               Interaction
                                │
CAN Telemetry Fidelity ────────┘
        │
        ↓
Safety Coverage Mapping ──→ Pre-Certification Screening
        │
        ↓
Degradation Early Warning ──→ Field-Driven Recalibration
```

---

## What was deliberately excluded

| Topic | Reason |
|---|---|
| **"Cost reduction" as a use-case group** | Cost is an outcome of every use case (e.g., bench-hours saved, NFF rate reduced). It is captured in each use case's Key Metrics and Decision Criteria, not as a separate folder. |
| **"Energy efficiency" as a use-case group** | Standby current and load scheduling are real vehicle-level concerns, but the eFuse is a sensor and switch — not the decision owner for energy budgets. Where relevant (e.g., quiescent current affecting thermal models), it's absorbed into [Thermal Headroom](3-hardware-and-harness/thermal-headroom-validation.md). |
| **"Post-development" as a lifecycle folder** | Lifecycle stage is a dimension, not a domain. Post-launch calibration refinement is in [Field-Driven Recalibration](6-field-and-fleet/field-driven-recalibration.md). Variant expansion is in [Variant Reuse Validation](1-protection-design/variant-reuse-validation.md). |
| **EMC / conducted noise robustness** | Outside the simulation model's capabilities. EMC testing is bench-only; the simulator does not model RF interference, radiated emissions, or conducted transients beyond supply-voltage disturbances. |

---

## Template

Use the [template](_template.md) to create new use cases. Each use case must answer **one decision** and include measurable KPIs with targets.
