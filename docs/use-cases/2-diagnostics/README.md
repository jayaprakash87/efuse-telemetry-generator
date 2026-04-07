# 2 — Diagnostics

> **Core question:** *Can I detect and isolate faults reliably — in development and in the workshop?*

Diagnostics is where eFuse telemetry becomes actionable: without reliable fault detection, protection events are just unexplained shutdowns. The challenge is that eFuse faults are inherently ambiguous — a voltage drop could be a loose connector, a degraded ground, or a genuine short. The same symptom appears for different root causes.

This group covers two genuinely distinct problems: **designing DTC rules** (an engineering decision) and **building fault-isolation guidance for workshops** (a service-operations deliverable).

## Use Cases

| # | Use Case | Decision |
|---|---|---|
| 1 | [DTC Rule Engineering](dtc-rule-engineering.md) | Define and validate diagnostic detection rules with measurable precision and recall |
| 2 | [Workshop Fault Isolation](workshop-fault-isolation.md) | Build evidence-based troubleshooting playbooks that distinguish confusable fault types |

## Who uses this

- Diagnostics / DTC team (rule design and validation)
- Aftersales engineering (workshop content)
- eFuse Function Owner (provides domain input on expected fault behaviour)
- Service operations (consumes playbooks)

## Relationship to other groups

- Protection events from [Protection Design](../1-protection-design/) are the raw material for diagnostic rules.
- Fault-isolation quality directly affects service costs — the financial case is captured in the diagnostic use cases themselves, not in a separate "cost" folder.
