# 0 — ML Dataset Engineering

This section covers use cases where the **primary output is a labelled dataset**
for training, evaluating, or fine-tuning a machine-learning model — not an
immediate engineering decision.

The generator's value here is unique:

- **Exact ground truth.** Every fault, degradation step, and threshold crossing
  has a known label because we injected it. Real data rarely has this.
- **Class balance by design.** Rare fault types (thermal runaway, latch-up) can
  be generated at arbitrary frequency so classifiers don't train on 99 % normal.
- **Parametric sweeps.** A dataset that would take months of bench time is
  generated in minutes by sweeping configs.
- **Reproducibility.** A config YAML + seed fully reproduces a dataset.
  Experiments can be re-run or extended without re-running physical tests.

---

## Use Cases

| # | Use Case | ML task |
|---|---|---|
| 0.1 | [Fault Classifier Training](fault-classifier-training.md) | Multi-class supervised classification |
| 0.2 | [Anomaly Detection Pre-training](anomaly-detection-pretraining.md) | Unsupervised / one-class learning on normal data |
| 0.3 | [Pre-Trip Sequence Prediction](pre-trip-sequence-prediction.md) | Time-series regression / seq2seq |
| 0.4 | [Synthetic Pre-training + Real Fine-tuning](synthetic-pretraining-real-finetuning.md) | Transfer learning / domain adaptation |
| 0.5 | [Threshold Search via Simulation Sweeps](threshold-search-via-simulation.md) | Optimisation / hyperparameter search |

---

## Relationship to Other Use Cases

ML datasets produced here feed directly into:

- **[DTC Rule Engineering](../2-diagnostics/dtc-rule-engineering.md)** — classifier
  outputs can replace or augment hand-written DTC rules.
- **[Degradation Early Warning](../6-field-and-fleet/degradation-early-warning.md)** —
  anomaly and sequence models are the production form of that use case.
- **[Field-Driven Recalibration](../6-field-and-fleet/field-driven-recalibration.md)** —
  synthetic pre-training reduces the real data needed to validate a new threshold.
- **[Threshold & Retry Calibration](../1-protection-design/threshold-and-retry-calibration.md)** —
  simulation sweeps (use case 0.5) accelerate the manual calibration process.
