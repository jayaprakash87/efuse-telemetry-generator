# Documentation — Where to Start

```bash
pip install efuse-telemetry-generator
efuse-gen                    # 3-channel demo → output/ in ~8 seconds
```

## Pick Your Path

| I want to… | Start here |
|------------|-----------|
| **Generate test data** (first 10 minutes) | [Quickstart Guide](quickstart.md) |
| **Understand the simulation** | [Architecture](architecture.md) → [Signal Chain One-Pager](signal-chain-one-pager.md) |
| **Modify a config / add channels** | [Configuration Guide](configuration.md) |
| **Learn the eFuse physics** | [Domain Reference](domain-reference.md) |
| **Find a validation scenario** for my team | [Use-Case Library](use-cases/README.md) — 20 ready-made scenarios |
| **Run fleet / multi-day simulations** | [Drive Cycles Deep-Dive](drive-cycles.md) |
| **Visualize results interactively** | [Dashboard Guide](dashboard.md) |
| **Understand the output files** | [Data Model Reference](data-model.md) |
| **Contribute code** | [Contributing](../CONTRIBUTING.md) → [Onboarding](onboarding.md) |

## Suggested Reading Order

1. **[Quickstart](quickstart.md)** — install, run, see output (5 min)
2. **[Configuration](configuration.md)** — modify channels, faults, duration (10 min)
3. **[Architecture](architecture.md)** — how the pipeline works (15 min)
4. **[Data Model](data-model.md)** — what the output columns mean (10 min)
5. Pick a topic above based on your role.

## Quick Reference

```bash
efuse-gen                              # Default 3-channel demo
efuse-gen --config single_drive        # 65-channel full topology
efuse-gen --config multi_day           # 30-day simulation
efuse-gen --dry-run --config fleet     # Preview without writing files
efuse-gen --list-configs               # Show all built-in configs
efuse-gen ingest recording.csv         # Ingest real measurement data
efuse-gen topology template -o t.csv   # CSV template for custom topology
efuse-dashboard                        # Interactive dashboard (needs [dashboard] extra)
```
