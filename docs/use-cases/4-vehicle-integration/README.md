# 4 — Vehicle Integration

> **Core question:** *Does the eFuse function work correctly when the rest of the vehicle gets involved?*

An eFuse IC on a bench behaves predictably. An eFuse on a zone controller in a vehicle operates in a hostile electrical environment: supply voltage sags during crank, load-dump transients arrive unannounced, the CAN bus has limited bandwidth, and multiple channels on the same IC interact through shared silicon and shared return paths.

This group covers the system-level interactions that only become visible when the eFuse function is embedded in a vehicle context.

## Use Cases

| # | Use Case | Decision |
|---|---|---|
| 1 | [Powernet Disturbance Resilience](powernet-disturbance-resilience.md) | Confirm protection and diagnostics survive real powernet events without false trips or missed faults |
| 2 | [CAN Telemetry Fidelity](can-telemetry-fidelity.md) | Set CAN signal resolution and sampling rate to preserve diagnostic value under bandwidth constraints |
| 3 | [Multi-Channel Interaction](multi-channel-interaction.md) | Identify cross-channel effects (shared return, virtual drop, thermal coupling) that invalidate single-channel analysis |

## Who uses this

- Powernet team (disturbance resilience)
- Network / CAN architecture team (telemetry fidelity)
- Zone Controller HW architect + eFuse Function Owner (multi-channel interaction)

## Why this matters for synthetic data specifically

Vehicle-integration effects are extremely expensive to test physically — they require a full powernet test bench or a vehicle. Simulation can reproduce supply disturbances, CAN quantisation, and multi-channel contention systematically, exposing integration issues months before a test vehicle is available.
