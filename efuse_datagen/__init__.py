"""eFuse Telemetry Generator — synthetic telemetry for automotive Zone Controller architectures."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

try:
    __version__ = version("efuse-telemetry-generator")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0-dev"

# ---------------------------------------------------------------------------
# Convenience re-exports — so users can write:
#   from efuse_datagen import TelemetryGenerator, load_config
# ---------------------------------------------------------------------------
from efuse_datagen.config.builtin import list_bundled_configs, load_bundled_config  # noqa: E402
from efuse_datagen.config.models import GeneratorConfig, load_config, load_config_data  # noqa: E402
from efuse_datagen.features.engine import FeatureEngine  # noqa: E402
from efuse_datagen.schemas.telemetry import ChannelMeta, LoadType  # noqa: E402
from efuse_datagen.simulation.generator import TelemetryGenerator  # noqa: E402
from efuse_datagen.storage.writer import StorageWriter  # noqa: E402

__all__ = [
    "ChannelMeta",
    "FeatureEngine",
    "GeneratorConfig",
    "LoadType",
    "StorageWriter",
    "TelemetryGenerator",
    "__version__",
    "generate",
    "list_bundled_configs",
    "load_bundled_config",
    "load_config",
    "load_config_data",
]


def generate(
    config: str | Path | GeneratorConfig = "quick_demo",
    *,
    output_dir: str | Path = "output",
    format: str = "parquet",
    duration_s: float | None = None,
    seed: int | None = None,
) -> dict[str, Path]:
    """Generate synthetic eFuse telemetry in one call.

    Parameters
    ----------
    config : str, Path, or GeneratorConfig
        A built-in config name (e.g. ``"quick_demo"``), a path to a YAML
        file, or an already-loaded :class:`GeneratorConfig`.
    output_dir : str or Path
        Root directory for output files.
    format : str
        ``"parquet"`` (default), ``"csv"``, or ``"json"``.
    duration_s : float, optional
        Override scenario duration in seconds.
    seed : int, optional
        Override random seed.

    Returns
    -------
    dict[str, Path]
        Mapping of output names to file paths
        (``telemetry``, ``features``, ``labels``, ``channel_manifest``, ``config``).

    Examples
    --------
    >>> from efuse_datagen import generate
    >>> result = generate("quick_demo")
    >>> result = generate("single_drive", duration_s=120, seed=99)
    """
    from datetime import datetime as _dt

    # Resolve config
    if isinstance(config, GeneratorConfig):
        cfg = config
        name = cfg.simulation.scenario_id
    elif isinstance(config, Path) or (isinstance(config, str) and Path(config).exists()):
        cfg = load_config(config)
        name = Path(config).stem
    else:
        cfg = load_bundled_config(str(config))
        name = str(config)

    sim_cfg = cfg.simulation
    feat_cfg = cfg.features
    store_cfg = cfg.storage

    # Apply overrides
    if duration_s is not None:
        sim_cfg.duration_s = duration_s
    if seed is not None:
        sim_cfg.seed = seed

    # Output directory
    timestamp = _dt.now().strftime("%Y%m%d-%H%M%S")
    out_dir = Path(output_dir) / f"{name}_{timestamp}"
    store_cfg.output_dir = str(out_dir)
    store_cfg.format = format

    # Generate
    gen = TelemetryGenerator(sim_cfg)
    telem_df, labels_df = gen.generate()

    # Features
    engine = FeatureEngine(feat_cfg)
    features_df = engine.compute(telem_df)

    # Write
    writer = StorageWriter(store_cfg)
    writer.write_telemetry(telem_df)
    writer.write_features(features_df)
    if not labels_df.empty:
        writer.write_labels(labels_df)
    writer.write_channel_manifest(sim_cfg.channels)

    # Run README
    writer.write_run_readme(
        scenario_name=sim_cfg.name,
        n_channels=len(sim_cfg.channels),
        n_rows=len(telem_df),
        n_features=len(features_df),
        n_labels=len(labels_df),
        duration_s=sim_cfg.duration_s,
        fmt=format,
    )

    # Config snapshot
    import yaml as _yaml

    config_snapshot = out_dir / "config.yaml"
    config_snapshot.parent.mkdir(parents=True, exist_ok=True)
    with open(config_snapshot, "w") as f:
        _yaml.safe_dump(sim_cfg.model_dump(mode="json"), f, sort_keys=False)

    ext = "parquet" if format == "parquet" else format
    return {
        "telemetry": out_dir / f"telemetry.{ext}",
        "features": out_dir / f"features.{ext}",
        "labels": out_dir / f"labels.{ext}",
        "channel_manifest": out_dir / f"channel_manifest.{ext}",
        "config": config_snapshot,
    }