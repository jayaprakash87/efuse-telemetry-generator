# Thermal Headroom Validation

## 1. Decision

Confirm that eFuse IC die temperature stays within safe operating limits under sustained load, combined channel activation, elevated ambient, and degraded harness/connector conditions — and quantify how much margin exists before thermal shutdown interrupts normal operation.

## 2. Trigger

- New topology defined with high-current channels packed on a single IC
- Ambient temperature specification raised (e.g., engine-bay-adjacent zone controller)
- Field thermal shutdown events reported on specific channel combinations
- PCB layout revision changes thermal path (heatsink pad area, copper pour)

## 3. Stakeholders

| Role | Who |
|---|---|
| **Decision owner** | Hardware architect / thermal engineer |
| **Data consumer** | eFuse Function Owner (protection interaction), packaging (heatsink design) |
| **Domain input** | IC supplier (thermal resistance specs), vehicle integration (ambient profile) |

## 4. Problem

eFuse ICs dissipate power proportional to the on-resistance (R_DS(on)) times the load current squared. On a zone controller with 6–12 channels, total power dissipation under combined load can reach several watts. Add an 85 °C ambient, a degraded connector increasing current for the same power delivery, and a PCB layout with limited copper pour — and die temperature can approach thermal shutdown.

Thermal shutdown is a blunt instrument: the IC shuts down **all** channels simultaneously, losing power to safety-relevant loads (e.g., mirror defrost, rear defroster). It is not a graceful degradation.

Today, thermal analysis uses simplified steady-state models: sum of P = I²R per channel, apply thermal resistance junction-to-ambient, check against T_shutdown. This ignores:

- **Dynamic duty cycles** — thermal ratcheting from cyclic loads (heater on/off) never reaches steady-state but accumulates heat when cooling is insufficient.
- **Cross-channel coupling** — channels share the same die; high-current channel A heats the die, reducing thermal margin for adjacent channel B.
- **Degradation amplification** — a 50 mΩ connector aging forces the IC to deliver more current (if voltage-regulated load) or causes more power dissipation across the harness, raising the local thermal environment.

## 5. Why Synthetic Data

| Gap | How simulation fills it |
|---|---|
| **Dynamic thermal profiles** | Simulation runs realistic duty cycles over minutes, capturing ratcheting and thermal equilibrium — not just worst-case static point |
| **Multi-channel interaction** | All channels active simultaneously with independent duty cycles; total die power is the sum, and the simulation tracks it |
| **Degradation coupling** | Connector aging → increased current or voltage stress → increased IC dissipation → higher die temp → earlier thermal shutdown; this chain is modelled end-to-end |
| **Speed** | Can sweep ambient × channel-set × degradation × duty-cycle in hours; thermal chamber testing of the same matrix takes weeks |

## 6. Scenario Design

| Element | Specification |
|---|---|
| **Channels** | Full zone-controller topology; activate worst-case channel combinations (e.g., all high-current channels simultaneous) |
| **Load profiles** | Realistic duty cycles: PTC heater continuous at rated current, seat heater 30 s on / 30 s off, blower PWM 70 %, window motor 6 s bursts |
| **Ambient sweep** | +25 / +55 / +70 / +85 °C (track how margin collapses) |
| **Degradation** | Connector aging at 0 / 25 / 50 / 100 mΩ per channel |
| **Harness** | Nominal and worst-case harness resistance |
| **Supply** | 12.0 V and 13.5 V (higher supply → lower current for voltage-regulated loads → less IC dissipation; lower supply → opposite) |
| **Duration** | 5–10 min per scenario (thermal time constant of eFuse ICs is typically 1–5 s; run 10–50× longer to see steady-state envelope) |

## 7. Required Signals

| Signal | Unit | Purpose |
|---|---|---|
| `temperature_c` | °C | Die temperature estimate (primary metric) |
| `current_a` | A | Per-channel current (input to power dissipation calculation) |
| `voltage_v` | V | Supply and load-side (voltage drop contributes to dissipation) |
| `trip_flag` | bool | Thermal-shutdown event |
| `protection_event` | enum | OTP (over-temperature protection) events specifically |
| `channel_id` | str | Which channels were active at time of thermal peak |
| `ambient_temp_c` | °C | Config: ambient temperature for this run |
| `connector_r_ohm` | Ω | Config: degradation level |

## 8. Key Metrics

| Metric | Direction | Target |
|---|---|---|
| Peak die temperature at +85 °C ambient, all high-current channels active | ↓ | ≤ T_shutdown − 20 °C |
| Thermal headroom (T_shutdown − T_die_peak) at worst-case duty cycle | ↑ | ≥ 15 °C at nominal connector; ≥ 5 °C at worst-case aged connector |
| Time to thermal shutdown under sustained worst-case load (if it occurs) | ↑ | > 60 s (enough for load management to deactivate non-critical channels) |
| Number of channel combinations that trigger thermal shutdown at +85 °C | ↓ | 0 for safety-relevant channel sets |

## 9. Decision Criteria

| Outcome | Action |
|---|---|
| ≥ 15 °C headroom at all conditions | Thermal design approved; no heatsink changes needed |
| Headroom 5–15 °C at worst case | Acceptable with thermal load management strategy (shed non-critical channels at high die temp) |
| Headroom < 5 °C or thermal shutdown occurs | Escalate: increase copper pour, add heatsink pad, or split high-current channels across two ICs |
| Degraded connector pushes thermal budget over limit | Define maximum allowable connector resistance for the thermal spec; link to [Wiring & Connector Sizing](wiring-and-connector-sizing.md) for connector quality requirement |

## 10. Dependencies

| Direction | Artefact |
|---|---|
| **Upstream** | IC thermal resistance specifications (junction-to-PCB, junction-to-ambient) from supplier |
| **Upstream** | PCB thermal model or copper-pour assumptions from layout team |
| **Upstream** | Ambient temperature profile from vehicle integration |
| **Downstream** | Thermal load management strategy (if headroom is marginal) |
| **Related** | [IC Benchmarking](efuse-ic-benchmarking.md) — thermal behaviour is a key comparison dimension |
| **Related** | [Wiring & Connector Sizing](wiring-and-connector-sizing.md) — harness impedance affects IC power dissipation |
| **Related** | [Multi-Channel Interaction](../4-vehicle-integration/multi-channel-interaction.md) — cross-channel contention is both a thermal and electrical concern |

## 11. Limitations

- The simulator uses a simplified lumped-thermal model (single thermal resistance, single time constant) — it does not model PCB layout, copper geometry, or airflow. Results are valid for relative comparisons and margin estimation, not absolute die-temperature prediction.
- Transient thermal events shorter than the IC's thermal time constant (e.g., 10 ms inrush) contribute negligible heating and are not the focus of this use case.
- Actual thermal validation on the production PCB in a thermal chamber remains mandatory for sign-off. Simulation scopes which conditions to test, it does not replace the thermal chamber.
