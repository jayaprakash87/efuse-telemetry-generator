# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] — 2026-04-07

### Changed
- **Renamed** the entire project from `vip-data-generator` / `vip_datagen` to
  `efuse-telemetry-generator` / `efuse_datagen`.
- CLI entry points renamed: `vip-gen` → `efuse-gen`, `vip-dashboard` → `efuse-dashboard`.
- Environment variable renamed: `VIP_DATA_GENERATOR_OUTPUT_DIR` → `EFUSE_TELEMETRY_OUTPUT_DIR`
  (old name still accepted for backward compatibility).
- Repository moved to <https://github.com/jayaprakash87/efuse-telemetry-generator>.

### Fixed
- Unused `sys` import in `cli.py`.
- Missing `PlatformConfig` import in `cli.py` type annotation.
- Unused `timezone` import in `drive_cycles.py`.

## [0.1.0] — 2026-04-07

### Added
- Physics-based synthetic eFuse telemetry generator with 8-stage per-sample pipeline.
- 14 injectable fault types: overload spike, intermittent overload, voltage sag,
  thermal drift, noisy sensor, dropped packet, gradual degradation, open load,
  jump start, load dump, cold crank, connector aging, thermal coupling, wake transient.
- 19 eFuse IC family catalog (Infineon PROFET+2, TLE, BTS; ST VIPower VN/VND/VNH/VNL).
- 65-channel, 4-zone BEV topology factory.
- Composite noise model: 1/f pink noise, ADC quantization, thermal Johnson-Nyquist, EMI spikes.
- First-order RC junction temperature model with temperature-dependent Rds,on.
- ISENSE sensing-chain model (k_ILIS tempco, R_ILIS tolerance).
- F(i,t) energy-integral overcurrent protection with SCP, thermal shutdown, retry logic, latch-off.
- Multi-cycle drive scheduling with Poisson trip distribution and stochastic fault injection.
- 20+ rolling feature engine (RMS, spike score, degradation trend, protection event rates).
- Parquet / CSV / JSON output with channel manifest and drive-cycle metadata.
- Streamlit dashboard with 6 tabs (Overview, Telemetry, Features, Fault Analysis, Protection Events, Config).
- 4 bundled scenario configs: `default`, `zone_controller_full`, `one_month`, `stress_test`.
- Structured JSON logging with correlation IDs.
- CI pipeline (GitHub Actions) testing Python 3.10 / 3.11 / 3.12.
- PyPI publish workflow with OIDC trusted publisher.
- 31 pytest tests covering generation, protection logic, bus voltage events, thermal coupling, and power states.
- Comprehensive documentation: architecture, configuration, data model, drive cycles, dashboard, onboarding.

[0.1.1]: https://github.com/jayaprakash87/efuse-telemetry-generator/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/jayaprakash87/efuse-telemetry-generator/releases/tag/v0.1.0
