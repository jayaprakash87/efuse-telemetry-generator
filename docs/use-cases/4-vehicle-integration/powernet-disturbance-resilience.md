# Powernet Disturbance Resilience

## 1. Decision

Confirm that eFuse protection thresholds and DTC rules remain correct — no false trips, no missed faults, no unnecessary latch-offs — during standard powernet disturbances (cold crank, load dump, jump start, voltage recovery).

## 2. Trigger

- Powernet specification published (defines disturbance profiles the ZC must survive)
- Integration testing reveals unexpected trips during crank or load-dump
- Vehicle-level energy management adds new operating states (e.g., recuperation, V2L mode)

## 3. Stakeholders

| Role | Who |
|---|---|
| **Decision owner** | Powernet team + eFuse Function Owner |
| **Data consumer** | Validation (scopes powernet bench tests), Controls SW (adjusts blanking windows) |
| **Domain input** | Battery / starter team (crank profile), vehicle integration (load-dump spec per OEM) |

## 4. Problem

Powernet disturbances are among the harshest electrical events an eFuse sees:

- **Cold crank** (−40 °C): supply voltage drops to 4–6 V for 50–200 ms. eFuse current sense may lose accuracy below 8 V. Loads that were drawing 10 A now see reduced supply and behave unpredictably (motor stalls, heater resistance shifts). If SCP threshold is set relative to supply, a 6 V sag may trip a channel unnecessarily.
- **Load dump**: supply spikes to 27–40 V for milliseconds. IC survives (clamped internally), but after the dump, voltage recovery can cause inrush on all channels simultaneously — the combined inrush may trigger multi-channel thermal events.
- **Jump start** (24 V applied): sustained overvoltage causes higher current at constant-resistance loads. SCP threshold set at 2× nominal may now be borderline.

Today, powernet resilience is tested late — on the vehicle or powernet bench. Failures at that stage are expensive: protection-parameter rework, DTC debounce adjustment, or worst case, IC redesign.

## 5. Why Synthetic Data

| Gap | How simulation fills it |
|---|---|
| **Early access** | Powernet disturbance profiles can be injected before a vehicle or powernet bench exists |
| **Systematic sweep** | Can test every channel × every disturbance × every temperature corner; physical tests typically cover a subset |
| **Combined with faults** | Can test "cold crank + connector aging" — does the DTC rule still work when the supply is unstable AND the connector is degraded? Physical testing of these combinations is impractical |

## 6. Scenario Design

| Element | Specification |
|---|---|
| **Disturbance profiles** | Cold crank (V_min = 4.5 V, 6.0 V, 8.0 V; duration 50 / 100 / 200 ms), load dump (V_max = 27 V / 36 V / 40 V; duration 5 / 40 / 100 ms), jump start (24 V sustained 60 s) |
| **Channels** | All channel families: high-current, PWM, motor, low-current always-on |
| **Concurrent operation** | All channels active during disturbance (worst-case simultaneous recovery) |
| **Fault overlay** | Each disturbance × {no fault, `connector_aging` at 25 mΩ, `ground_offset` at 100 mΩ} |
| **Temperature** | −40 / +25 / +85 °C |
| **Duration** | 30 s per scenario: pre-disturbance steady state → disturbance → recovery → post-disturbance steady state |

## 7. Required Signals

| Signal | Unit | Purpose |
|---|---|---|
| `voltage_v` | V | Supply voltage during disturbance (primary input) |
| `current_a` | A | Channel current response to supply change |
| `trip_flag` | bool | False trip during disturbance? |
| `protection_event` | enum | Which protection path triggered (SCP? OCP? OTP?) |
| `retry_count` | int | Post-disturbance recovery behaviour |
| `fault_type` | label | Ground truth: "no fault; disturbance only" vs. "fault during disturbance" |
| `temperature_c` | °C | Die temperature during and after multi-channel simultaneous recovery |

## 8. Key Metrics

| Metric | Direction | Target |
|---|---|---|
| False trip rate during disturbance (channels tripping with no fault present) | ↓ | 0 for all channels during cold crank and jump start |
| Channels failing to recover after load dump | ↓ | 0 (all channels must resume normal operation within 500 ms of voltage recovery) |
| Fault detection rate during disturbance (a fault is present AND the disturbance is happening) | ↑ | ≥ 80 % (acceptable to suppress detection during crank; but not permanently) |
| Post-disturbance DTC false-positive rate (DTC stored after disturbance but no fault was present) | ↓ | 0 |
| Thermal peak during simultaneous multi-channel recovery after load dump | ↓ | < T_die warning threshold |

## 9. Decision Criteria

| Outcome | Action |
|---|---|
| All channels survive all disturbances without false trips | Protection config approved for powernet integration |
| False trips during crank on specific channels | Add blanking window (suppress SCP for X ms after supply < Y V); document and test on bench |
| DTC stored after disturbance despite no fault | Adjust DTC debounce / confirmation — require post-disturbance stable period before confirming DTC |
| Thermal peak during multi-channel recovery is marginal | Add staggered recovery (channels resume sequentially, not simultaneously) |

## 10. Dependencies

| Direction | Artefact |
|---|---|
| **Upstream** | Powernet specification (disturbance profiles, voltage limits) from vehicle integration |
| **Upstream** | Frozen protection thresholds from [Threshold Calibration](../1-protection-design/threshold-and-retry-calibration.md) |
| **Downstream** | Powernet bench test plan (prioritised by simulation findings) |
| **Related** | [Multi-Channel Interaction](multi-channel-interaction.md) — post-disturbance multi-channel recovery is both a powernet and multi-channel problem |
| **Related** | [DTC Rule Engineering](../2-diagnostics/dtc-rule-engineering.md) — DTC blanking/suppression during disturbance is a diagnostic-rule concern |

## 11. Limitations

- Simulation injects voltage-profile disturbances; it does not model the battery, starter motor, or alternator dynamics that produce them. Real disturbance profiles may differ in shape (overshoot, ringing, recovery slope).
- Load-dump clamping is assumed ideal (IC datasheet spec). Actual clamping diode forward-voltage variation and PCB parasitics are not modelled.
- Simultaneous recovery behaviour depends on IC internal sequencing (some ICs restart channels sequentially by design). If the IC model does not capture this, the thermal peak during recovery may be over-estimated.
