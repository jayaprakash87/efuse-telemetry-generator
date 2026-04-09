# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] — 2026-04-09

### Added
- **Topology CLI** (`efuse-gen topology`) — new subcommand group with `import`, `export`, `template`, and `new` commands for managing vehicle topology YAML files from CSV/Excel/Parquet spreadsheets.
- **`efuse-gen info` command** — display a config summary (channels, zones, faults, drive-cycle) without generating data.
- **`--dry-run` flag** on `efuse-gen` — preview channel count, estimated rows, and output path without writing files.
- **Reusable topology files** — `topology_file` field on `SimulationConfig` loads zones and channel_specs from a standalone YAML (bundled name or file path) with caching for fleet mode.
- **Bundled topologies** — `bev_2zone_12ch` (compact) and `bev_4zone_65ch` (full) shipped in `config/topologies/`.
- **New built-in scenario configs** — `custom_topology` and `custom_topology_with_catalog` templates demonstrating topology-file usage.
- **Config templates README** — `config/templates/README.md` documenting all bundled scenario configs.
- **`LoadType` enum** — `resistive`, `inductive`, `motor`, `ptc`, `capacitive`, `led`, `solenoid` replaces bare strings on `ChannelMeta` and `EFuseProfile`.
- **`ChannelMeta.explain()`** — introspect field documentation programmatically.
- **Top-level Python API** — `from efuse_datagen import generate, TelemetryGenerator, load_config` plus `__all__` and a one-call `generate()` convenience function.
- **Output README** — each run directory now includes a `README.md` describing its files, row counts, and quick-load snippets.
- **`[excel]` optional extra** — `openpyxl` dependency for `.xlsx` topology import.
- **Topology IO module** (`efuse_datagen/config/topology_io.py`) — import/export logic with fuzzy column-header aliases, type coercion, and unknown-family warnings.
- **Topology IO tests** — `tests/test_topology_io.py` covering import, export, aliased headers, roundtrip, type coercion, and error cases.
- **Docs index page** (`docs/index.md`) — "Where to Start" landing page with role-based reading paths.
- **Quickstart guide expanded** — full PyPI install-to-dashboard walkthrough in `docs/quickstart.md`.

### Changed
- **`efuse-ingest` entry point removed** — ingestion is now exclusively available as `efuse-gen ingest`.
- **`use_example_topology` removed** — replaced by `topology_file` field; old configs must migrate.
- **Fleet-only flags now error** instead of printing a warning when used with single-vehicle configs.
- Topology conflict detection — providing `topology_file`, `channel_specs`, and/or `channels` simultaneously now raises a clear error.
- `DriveCycleConfig.profile` and `VehicleArchetypeConfig.profile` now use `Literal["commuter", "mixed", "heavy"]` instead of bare `str`.
- `StorageConfig.format` now uses `Literal["parquet", "csv", "json"]` instead of bare `str`.
- `extra = "forbid"` added to `FaultRateConfig`, `FeatureConfig`, and `RegionalWeatherConfig` models.
- Zone cross-reference validation — `build_channels()` now raises upfront on orphan `zone_id` references.
- Enum coercion in catalog — raw string values for `load_type`, `driver_type`, `power_class`, `source_protocol` are auto-coerced to their enum types.
- Topology YAML bundled in sdist — `MANIFEST.in` and `pyproject.toml` `package-data` updated.
- Built-in template configs (`fleet.yaml`, `multi_day.yaml`, `single_drive.yaml`) updated to use `topology_file`.
- Catalog module docstring and example topology factory moved to `topology_io` / bundled YAML files.
- README updated with PyPI install instructions, developer-setup section, and quickstart link.
- Docs (`architecture.md`, `configuration.md`, `dashboard.md`, `data-model.md`, `drive-cycles.md`, `onboarding.md`) refreshed.

## [1.0.0] — 2026-04-09

### Changed
- Promoted to first stable release on PyPI.
- Development status upgraded to Production/Stable.
- Added `MANIFEST.in` for reliable sdist packaging.
- Added Changelog URL to project metadata.

## [0.2.0] — 2026-04-08

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
- **CLI input validation** — mode-mismatch warnings and argument-range checks.
- **Cross-field validation** on config and schema models; `extra = "forbid"` rejects unknown YAML keys.
- **Fleet-level run discovery & visualization** in the dashboard.
- New simulation templates: `fleet`, `multi_day`, `single_drive`, `quick_demo`.
- Example script for ingesting bench recording CSV into standard run format.
- **Versioning & type hinting** — `py.typed` marker, `__version__` export.
- **CI enhancements** — ruff linting step, Pyright type checking, coverage reporting.
- Integration tests for fleet-scale generation.

### Changed
- **Dashboard modularised** — monolithic 790-line `dashboard_app.py` replaced with a
  140-line orchestrator that delegates to `efuse_datagen/dashboard/tabs/` modules
  (overview, signals, features, protection, config).
- Dashboard tabs consolidated from 6 to 5: merged Fault Analysis + Protection Events →
  "Fault & Protection"; renamed Telemetry → Signals.
- Dashboard rendering improved with better layout and error handling/boundaries.
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
- PEP 604 union types across codebase (`X | None` instead of `Optional[X]`).
- Dependency versions constrained in `pyproject.toml`.

### Fixed
- Feature engine edge-case hardening.
- Cache expiration added to data loading functions.
- ANSI escape codes stripped in CLI validation tests for accurate assertions.
- Missing fault rate fields and stale doc references corrected.
- Unused imports removed across test files and feature modules.
- Seed generation refactored in simulation files for deterministic fleet runs.

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
