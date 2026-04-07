# Use-Case Template

Every use case in this library exists to support **one engineering decision**.
If you cannot state the decision in one sentence, the use case is too broad.

---

## 1. Decision

> One sentence: what engineering or business decision does this use case enable?

Example: "Freeze SCP and I²T thresholds for the body-domain zone controller before A-sample hardware."

---

## 2. Trigger

When in the program lifecycle does this decision become urgent?

| Typical trigger | Example |
|---|---|
| Milestone approaching | A-sample freeze, SW drop, SOP-12 |
| New information | Supplier change, field warranty spike, variant added |
| Blocked process | Bench queue full, DTC precision unknown, compliance gap found |

---

## 3. Stakeholders

| Role | Relationship |
|---|---|
| **Decision owner** | Who signs off? |
| **Data consumer** | Who uses the simulation output? |
| **Domain input** | Who defines loads, faults, or acceptance criteria? |

---

## 4. Problem

Why can't this decision be made today?

Be specific:
- What data is missing, late, or ambiguous?
- What is the cost of deciding without it (rework, warranty, safety)?
- What is the cost of waiting (schedule slip, bench queue)?

---

## 5. Why Synthetic Data

What does simulation provide that bench, vehicle, or field data cannot — or cannot provide fast enough?

Address at least one:
- **Availability** — hardware does not exist yet
- **Coverage** — faults too rare or dangerous to reproduce physically
- **Speed** — parameter sweeps that would take weeks on bench
- **Labels** — ground-truth fault labels not available in real data
- **Cost** — physical test is disproportionately expensive

---

## 6. Scenario Design

| Element | Specification |
|---|---|
| **Target channels / loads** | e.g., seat heater (12 A), rear defroster (25 A), PTC (40 A) |
| **Fault injection** | Fault types, severities, progression rates |
| **Protection parameters to sweep** | Thresholds, timings, retry counts |
| **Environmental conditions** | Ambient temp range, power states, supply voltage |
| **Duration / cycles** | Seconds, drive cycles, or simulated weeks |
| **Topology** | Zone, harness path, connector assumptions |

---

## 7. Required Signals

List every signal the downstream analysis needs.

| Signal | Unit | Purpose |
|---|---|---|
| `current_a` | A | Load and fault current |
| `voltage_v` | V | Supply and load-side voltage |
| `temperature_c` | °C | Die, ambient, or harness temp |
| `trip_flag` | bool | Protection activation |
| `protection_event` | enum | SCP / OCP / OTP / latch |
| `fault_type` | label | Ground-truth injected fault |
| `severity` | float | Fault intensity |

Add or remove rows for the specific use case.

---

## 8. Key Metrics

3–5 measurable KPIs.  Each must have a **direction** (↑ better or ↓ better) and ideally a **target**.

| Metric | Direction | Target (if known) |
|---|---|---|
| Example: nuisance-trip rate | ↓ | < 2 per 1 000 drive cycles |
| Example: fault detection recall | ↑ | ≥ 95 % for critical faults |

---

## 9. Decision Criteria

What does "pass" look like? What action follows each outcome?

| Outcome | Action |
|---|---|
| All KPIs met | Freeze configuration; proceed to bench confirmation |
| Partial pass | Narrow sweep range; iterate on failing channels |
| Fail | Escalate to hardware or architecture review |

---

## 10. Dependencies

| Direction | Related use case or artefact |
|---|---|
| **Upstream** | What inputs does this use case need? (e.g., load spec, IC datasheet) |
| **Downstream** | What consumes this use case's output? (e.g., bench plan, DTC spec) |
| **Related** | Other use cases that share scenarios or data |

---

## 11. Limitations

Be honest about what simulation does **not** cover.

- Which real-world effects are outside the model?
- When is bench or vehicle validation still mandatory?
- What assumptions could invalidate the result?
