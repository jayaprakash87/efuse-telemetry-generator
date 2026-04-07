# 1 — Protection Design

> **Core question:** *Will my protection strategy work — across loads, faults, variants, and software releases?*

Protection-parameter decisions (SCP, OCP, I²T, retry count, cooldown, latch policy) are the single highest-impact calibration an eFuse function owner makes. Get them wrong and you ship either nuisance trips that annoy customers or weak protection that risks wiring damage.

This group covers the full lifecycle of that decision: early calibration, variant reuse, and release-to-release stability.

## Use Cases

| # | Use Case | Decision |
|---|---|---|
| 1 | [Threshold & Retry Calibration](threshold-and-retry-calibration.md) | Freeze SCP / I²T / retry parameters before hardware availability |
| 2 | [Variant Reuse Validation](variant-reuse-validation.md) | Confirm existing calibration is safe for a new load, region, or option |
| 3 | [Release Regression Gating](release-regression-gating.md) | Approve a software release has not degraded protection behaviour |

## Who uses this

- eFuse Function Owner (decision owner for all three)
- Controls / application software (implements thresholds)
- Validation (confirms on bench after simulation narrows the space)
- Platform / variant management (triggers variant-reuse validation)

## Typical program timing

| Use case | Program phase |
|---|---|
| Threshold calibration | Concept → A-sample |
| Variant reuse | B-sample → SOP (each new variant) |
| Regression gating | Every SW release candidate |
