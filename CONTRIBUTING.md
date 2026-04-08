# Contributing

Thanks for contributing to eFuse Telemetry Generator.

## Scope

This project focuses on synthetic eFuse telemetry generation for BEV Zone Controller architectures. Good contributions usually improve one of these areas:

- simulation fidelity and fault modelling
- packaged CLI and dashboard usability
- documentation and onboarding
- test coverage and release quality

Keep changes narrowly scoped and avoid mixing unrelated refactors with functional changes.

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,dashboard]"
```

Useful commands:

```bash
pytest -q
python -m build --sdist --wheel
efuse-gen --list-configs
efuse-gen --config default
efuse-dashboard --help
```

## Coding Guidelines

- Preserve the current package model: packaged runtime code and packaged built-in config templates under `efuse_datagen/config/templates/`.
- Do not duplicate built-in configs in multiple locations.
- Keep documentation, comments, and docstrings aligned with the current runtime behaviour.
- Prefer small, reviewable changes over broad rewrites.
- Add or update tests when changing generator logic, config parsing, or packaging behaviour.

## Pull Requests

Before opening a pull request:

1. Run `pytest -q`.
2. Run `python -m build --sdist --wheel`.
3. If you changed packaged runtime flows, smoke test at least one of:
   - `efuse-gen --config quick_demo`
   - `efuse-gen --list-configs`
   - `efuse-dashboard --help`
4. Update docs if user-facing behaviour changed.

PR descriptions should explain:

- what changed
- why it changed
- how it was validated
- any follow-up work or limitations

## Issues

When reporting bugs, include:

- Python version
- install method (`pip install -e`, wheel install, etc.)
- exact command used
- relevant config name or custom YAML
- traceback or log output

## Release Notes

If a change affects packaging, CLI behaviour, built-in configs, or dashboard launch flow, add a short release note entry in the PR description so it can be carried into the next release.
