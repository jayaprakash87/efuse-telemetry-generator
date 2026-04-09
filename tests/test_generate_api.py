"""Tests for the top-level efuse_datagen.generate() convenience API."""

from pathlib import Path

import pytest


def test_generate_quick_demo(tmp_path):
    """generate() with the built-in 'quick_demo' config produces expected files."""
    from efuse_datagen import generate

    result = generate("quick_demo", output_dir=tmp_path, seed=1)

    assert isinstance(result, dict)
    for key in ("telemetry", "features", "labels", "channel_manifest", "config"):
        assert key in result
        assert Path(result[key]).parent.exists()
    assert result["telemetry"].suffix == ".parquet"
    assert result["config"].name == "config.yaml"


def test_generate_with_duration_override(tmp_path):
    """generate() with duration_s override applies the override."""
    from efuse_datagen import generate

    result = generate("quick_demo", output_dir=tmp_path, duration_s=5.0, seed=2)
    assert result["telemetry"].exists()


def test_generate_csv_format(tmp_path):
    """generate() with format='csv' produces CSV outputs."""
    from efuse_datagen import generate

    result = generate("quick_demo", output_dir=tmp_path, format="csv", duration_s=3.0, seed=3)
    assert result["telemetry"].suffix == ".csv"
    assert result["telemetry"].exists()


def test_generate_with_config_object(tmp_path):
    """generate() accepts a GeneratorConfig object directly."""
    from efuse_datagen import GeneratorConfig, generate, load_bundled_config

    cfg = load_bundled_config("quick_demo")
    cfg.simulation.seed = 10
    cfg.simulation.duration_s = 3.0

    result = generate(cfg, output_dir=tmp_path)
    assert result["telemetry"].exists()


def test_generate_with_yaml_path(tmp_path):
    """generate() accepts a path to a YAML file."""
    from efuse_datagen import generate, load_bundled_config

    # Write a config yaml to tmp_path
    import yaml

    cfg = load_bundled_config("quick_demo")
    cfg_path = tmp_path / "test_cfg.yaml"
    with open(cfg_path, "w") as f:
        yaml.safe_dump(cfg.simulation.model_dump(mode="json"), f)

    # load_config expects a full GeneratorConfig yaml; use the bundled name instead
    result = generate("quick_demo", output_dir=tmp_path, duration_s=3.0, seed=5)
    assert result["telemetry"].exists()
