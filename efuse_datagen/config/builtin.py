"""Helpers for packaged built-in scenario configs."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import yaml

from efuse_datagen.config.models import GeneratorConfig, load_config_data

BUILTIN_CONFIGS: dict[str, str] = {
    "quick_demo": "quick_demo.yaml",
    "custom_topology": "custom_topology.yaml",
    "custom_topology_with_catalog": "custom_topology_with_catalog.yaml",
    "single_drive": "single_drive.yaml",
    "multi_day": "multi_day.yaml",
    "fleet": "fleet.yaml",
    "stress_test": "stress_test.yaml",
}


def list_bundled_configs() -> dict[str, str]:
    """Return the mapping of built-in config names to packaged YAML filenames."""
    return BUILTIN_CONFIGS.copy()


def load_bundled_config(config_name: str) -> GeneratorConfig:
    """Load one of the packaged built-in scenario configs."""
    key = Path(config_name).stem

    if key not in BUILTIN_CONFIGS:
        choices = ", ".join(BUILTIN_CONFIGS)
        raise KeyError(f"Unknown built-in config '{config_name}'. Choose one of: {choices}")

    resource = files("efuse_datagen").joinpath(f"config/templates/{BUILTIN_CONFIGS[key]}")
    raw = yaml.safe_load(resource.read_text(encoding="utf-8"))
    return load_config_data(raw)