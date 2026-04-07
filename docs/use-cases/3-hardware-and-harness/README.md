# 3 — Hardware & Harness

> **Core question:** *Is my physical substrate — eFuse IC, wiring harness, connectors — robust enough for the application?*

Hardware decisions are expensive to change. Once a wire gauge is committed, a connector is tooled, or an IC is contracted, rework costs escalate by 10–100× compared to a concept-phase change. Yet these decisions are routinely made from static datasheet analysis alone, ignoring dynamic load profiles, fault interactions, and degradation over vehicle lifetime.

This group targets the three physical-substrate decisions where simulation can prevent late-stage surprises.

## Use Cases

| # | Use Case | Decision |
|---|---|---|
| 1 | [eFuse IC Benchmarking](efuse-ic-benchmarking.md) | Select the best-fit IC family from 2–3 candidates |
| 2 | [Wiring & Connector Sizing](wiring-and-connector-sizing.md) | Set harness gauge and connector rating with margin evidence |
| 3 | [Thermal Headroom Validation](thermal-headroom-validation.md) | Confirm die temperature stays within budget under sustained and degraded conditions |

## Who uses this

- Hardware architect / Zone Controller HW team (all three)
- Sourcing / procurement (IC benchmarking)
- Wiring harness team + cost engineering (wiring sizing)
- Thermal / packaging engineer (thermal headroom)

## Why a separate group (not merged with Protection Design)

Protection calibration asks "what parameters should I set?" — it takes the hardware as given. This group asks "is the hardware itself adequate?" — it questions the substrate before parameters are even relevant.
