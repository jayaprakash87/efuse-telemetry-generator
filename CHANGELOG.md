# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Measurement ingestion adapter** (`efuse_datagen/ingestion/`) — load real bench, HIL,
  or production recordings (CSV, Parquet, MDF/MF4, BLF/ASC) into the standard telemetry
  schema via `MeasurementAdapter` with configurable column mapping.
- **`efuse-ingest` CLI** — one-command ingestion from file or directory with `--map`,
  `--channel`, `--source-tag` options. New `efuse-ingest` entry point in pyproject.toml.
- **`save_as_run()`** — persist ingested data in the standard run directory format so the
  dashboard and all analysis tools work identically on real data.
- **Data source detection** — `DataSource.detect()` tags runs as synthetic / bench / hil /
  production; dashboard sidebar shows a colour-coded data-source badge.
- **Hardware & harness analysis** (`efuse_datagen/analysis/hardware_harness.py`) — IC
  benchmarking, wiring/connector sizing validation, thermal headroom metrics. Works on
  any data source (synthetic or real).
- Wire gauge (`wire_gauge_awg`) and run length (`wire_run_length_m`) fields on `ChannelMeta`.
- Bus voltage nominal field (`bus_voltage_nominal_v`) on `SimulationConfig`.

### Changed
- **Dashboard modularised** — monolithic 790-line `dashboard_app.py` replaced with a
  140-line orchestrator that delegates to `efuse_datagen/dashboard/tabs/` modules
  (overview, signals, features, protection, config).
- Dashboard tabs consolidated from 6 to 5: merged Fault Analysis + Protection Events →
  "Fault & Protection"; renamed Telemetry → Signals.
- `list_runs()` now scans 2 levels deep to find `telemetry.parquet`, supporting nested
  run directories (e.g., `output/bench/<run_id>/`).
- `load_run()` handles empty DataFrames and non-datetime timestamp columns gracefully.
- **Unified config architecture** — single `GeneratorConfig` model with optional `fleet: FleetConfig`
  field replaces the separate `PlatformConfig` / `FleetSimConfig` / `load_fleet_config()`.
- **Renamed built-in configs** — `default` → `quick_demo`, `zone_controller_full` → `single_drive`,
  `one_month` → `multi_day`. New `fleet` config bundled as built-in template.
- **Merged fleet CLI** — `efuse-fleet` removed; fleet mode is now activated via
  `efuse-gen --config fleet` (auto-detected from `fleet:` key in config).
- **Config-prefixed output directories** — runs are now written to
  `output/<config>_<YYYYMMDD-HHMMSS>/` instead of `output/<YYYYMMDD-HHMMSS-random>/`.

## [0.1.1] — 2026-04-07

### Changed
- **Renamed** the entire project from `vip-data-generator` / `vip_datagen` to
  `efuse-telemetry-generator` / `efuse_datagen`.
- CLI entry points renamed: `vip-gen` → `efuse-gen`, `vip-dashboard` → `efuse-dashboard`.
- Environment variable renamed: `VIP_DATA_GENERATOR_OUTPUT_DIR` → `EFUSE_TELEMETRY_OUTPUT_DIR`.
- Repository moved to <https://github.com/jayaprakash87/efuse-telemetry-generator>.

### Fixed
- Unused `sys` import in `cli.py`.
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

[Unreleased]: https://github.com/jayaprakash87/efuse-telemetry-generator/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/jayaprakash87/efuse-telemetry-generator/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/jayaprakash87/efuse-telemetry-generator/releases/tag/v0.1.0
