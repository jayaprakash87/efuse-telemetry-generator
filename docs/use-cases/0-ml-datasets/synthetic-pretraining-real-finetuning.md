# Synthetic Pre-training + Real Fine-tuning

## 1. Decision

Establish a transfer-learning workflow — pre-train a model on synthetic data,
then fine-tune on a small real dataset — to reach acceptable model performance
earlier in the programme when real labelled data is scarce or expensive to
collect.

---

## 2. Trigger

- Bench or HIL data is available (via `MeasurementAdapter`) but the labelled
  subset is too small to train a model from scratch
- A new eFuse IC or vehicle variant is introduced and production data does not
  yet exist
- Model trained purely on synthetic data shows a performance gap on real bench
  data that fine-tuning could close

---

## 3. Stakeholders

| Role | Who |
|---|---|
| **Decision owner** | ML / data science team lead |
| **Data consumer** | Same pipeline as fault classifier or anomaly model trained in use cases 0.1–0.3 |
| **Domain input** | Test / validation team (provides labelled bench data); eFuse Function Owner (confirms fault labels) |

---

## 4. Problem

The fundamental tension in eFuse ML:

- **Real data is the goal** — models need to work on real vehicle telemetry, not
  synthetic signals.
- **Real labelled data is hard.** Bench testing is expensive. Each labelled fault
  event requires an engineer to set up, trigger, observe, and annotate the event.
  Getting 1 000 labelled events per fault type is cost-prohibitive.
- **Synthetic-only models transfer imperfectly.** Simulation approximates real
  physics but misses measurement noise, sensor offsets, harness impedance
  variation, and ECU timing jitter. A model trained only on synthetic data will
  degrade when deployed on real hardware.

Transfer learning breaks this tension: synthetic data gives the model a strong
prior on fault structure; a small real dataset corrects for the
simulation-to-reality gap.

---

## 5. Why Synthetic Data

| Gap | How simulation fills it |
|---|---|
| **Diverse pre-training** | Cover all fault types, severities, and operating conditions — impossible with a small bench dataset |
| **Feature initialisation** | Model learns meaningful representations (current transients, thermal gradients) before seeing real data |
| **Label economy** | Fine-tuning requires 10–50× fewer real labelled examples than training from scratch |
| **Iterative improvement** | As more real data accumulates, the fine-tuning set grows and the model improves without regenerating synthetic data |

---

## 6. Scenario Design

**Phase 1 — Synthetic pre-training:**

| Element | Specification |
|---|---|
| **Dataset** | Full fault classifier dataset from [use case 0.1](fault-classifier-training.md) |
| **Volume** | ≥ 1 000 windows per fault class; 5 000 normal windows |
| **Architecture** | Choose model architecture before pre-training; transfer the encoder weights |

**Phase 2 — Real fine-tuning:**

| Element | Specification |
|---|---|
| **Source** | Bench / HIL recordings loaded via `MeasurementAdapter`; or production CAN logs with confirmed DTC labels |
| **Required volume** | Target ≥ 50 labelled examples per fault class; evaluate at 10, 25, 50, 100 to plot label efficiency curve |
| **Fine-tuning strategy** | Freeze encoder for first N epochs; unfreeze for final M epochs with reduced learning rate |
| **Validation set** | Real data held-out set (minimum 20 % of real labelled data) |

---

## 7. Required Signals

Same as [Fault Classifier Training](fault-classifier-training.md), for both
the synthetic pre-training set and the real fine-tuning set. The
`MeasurementAdapter` column map must map real signal names to the standard
schema before fine-tuning data is ingested.

| Signal | Unit | Source |
|---|---|---|
| `current_a` | A | Synthetic + real |
| `voltage_v` | V | Synthetic + real |
| `temperature_c` | °C | Synthetic + real |
| `fault_type` | label | Synthetic (injected) + real (confirmed DTC or bench annotation) |
| `severity` | float | Synthetic only — real may not have this |

---

## 8. Key Metrics

| Metric | Direction | Target |
|---|---|---|
| F1 on real held-out set after fine-tuning with 50 real examples per class | ↑ | ≥ 0.80 |
| F1 on real held-out set — trained from scratch on same 50 real examples | baseline | Expected to be lower; confirms pre-training benefit |
| Label efficiency (real examples needed to reach F1 = 0.80) | ↓ | ≤ 50 per class (vs. ≥ 500 from scratch) |
| Pre-training → fine-tuning F1 gap vs. synthetic-only model | — | Quantifies the simulation-to-reality gap; track per release |

---

## 9. Decision Criteria

| Outcome | Action |
|---|---|
| Fine-tuned model meets F1 target with ≤ 50 real examples per class | Adopt transfer workflow as standard for new variants; define minimum bench annotation budget |
| Fine-tuned model does not exceed from-scratch baseline | Pre-training representation is not transferring; review synthetic data fidelity or model architecture |
| Simulation-to-reality gap is large (> 20 % F1 drop) | Investigate signal fidelity differences; improve synthetic noise model or CAN quantisation; re-run pre-training |

---

## 10. Dependencies

| Direction | Artefact |
|---|---|
| **Upstream** | [Fault Classifier Training](fault-classifier-training.md) — provides the pre-training dataset and model architecture |
| **Upstream** | `MeasurementAdapter` — ingests real bench / HIL recordings with correct column mapping |
| **Downstream** | Production fault classifier or anomaly model deployed to fleet |
| **Related** | [Anomaly Detection Pre-training](anomaly-detection-pretraining.md) — same transfer pattern applies to anomaly models |
| **Related** | [Field-Driven Recalibration](../6-field-and-fleet/field-driven-recalibration.md) — field data that accumulates post-deployment grows the fine-tuning set over time |

---

## 11. Limitations

- Transfer learning benefit depends on the similarity between synthetic and real
  signal distributions. If the simulation's fault waveforms are significantly
  different from real bench waveforms, pre-training may not help or could hurt.
  Always measure the label efficiency curve rather than assuming transfer works.
- Fine-tuning on very small real datasets (< 10 examples per class) risks
  overfitting the fine-tuning adapters. Use early stopping and held-out
  validation strictly.
- This use case covers model development only. Model versioning, A/B testing,
  and fleet deployment infrastructure are out of scope.
