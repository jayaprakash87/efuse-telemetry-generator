"""Helpers for packaged built-in scenario configs."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import yaml

from efuse_datagen.config.models import PlatformConfig, load_config_data

BUILTIN_CONFIGS: dict[str, str] = {
    "default": "default.yaml",
    "zone_controller_full": "zone_controller_full.yaml",
    "one_month": "one_month.yaml",
    "stress_test": "stress_test.yaml",
}


def list_bundled_configs() -> dict[str, str]:
    """Return the mapping of built-in config names to packaged YAML filenames."""
    return BUILTIN_CONFIGS.copy()


def load_bundled_config(config_name: str) -> PlatformConfig:
    """Load one of the packaged built-in scenario configs."""
    key = Path(config_name).stem
    if key not in BUILTIN_CONFIGS:
        choices = ", ".join(BUILTIN_CONFIGS)
        raise KeyError(f"Unknown built-in config '{config_name}'. Choose one of: {choices}")

    resource = files("efuse_datagen").joinpath(f"config/templates/{BUILTIN_CONFIGS[key]}")
    raw = yaml.safe_load(resource.read_text(encoding="utf-8"))
    return load_config_data(raw)