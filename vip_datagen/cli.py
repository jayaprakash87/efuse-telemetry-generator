"""CLI for the VIP synthetic eFuse data generator.

Usage
-----
  vip-gen generate                          # default 3-channel scenario → output/
  vip-gen generate --config configs/example_65ch.yaml
  vip-gen generate --config configs/default.yaml --output my_run/ --format csv
  vip-gen generate --duration 120 --channels 5 --seed 99

The generator produces:
  <output>/<run_id>/telemetry.parquet    raw per-sample eFuse signals
  <output>/<run_id>/features.parquet     rolling derived features
  <output>/<run_id>/labels.parquet       ground-truth fault windows
  <output>/<run_id>/config.yaml          snapshot of the config used
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console

from vip_datagen.config.models import (
    FeatureConfig,
    SimulationConfig,
    StorageConfig,
    load_config,
)
from vip_datagen.features.engine import FeatureEngine
from vip_datagen.simulation.generator import TelemetryGenerator
from vip_datagen.storage.writer import StorageWriter
from vip_datagen.utils.logging import configure_logging, get_logger

app = typer.Typer(
    name="vip-gen",
    help="VIP synthetic eFuse telemetry generator for ZC architecture validation.",
    add_completion=False,
    invoke_without_command=True,
)
console = Console()


@app.callback(invoke_without_command=True)
def generate(
    ctx: typer.Context,
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to YAML scenario config. Defaults to built-in 3-channel demo.",
        exists=True,
        dir_okay=False,
    ),
    output: Path = typer.Option(
        Path("output"),
        "--output",
        "-o",
        help="Root directory for output files.",
    ),
    fmt: str = typer.Option(
        "parquet",
        "--format",
        "-f",
        help="Output format: parquet or csv.",
    ),
    duration: Optional[float] = typer.Option(
        None,
        "--duration",
        "-d",
        help="Override scenario duration in seconds.",
    ),
    seed: Optional[int] = typer.Option(
        None,
        "--seed",
        "-s",
        help="Override random seed for reproducibility.",
    ),
    json_log: bool = typer.Option(
        False,
        "--json-log",
        help="Emit structured JSON log lines instead of pretty output.",
    ),
) -> None:
    """Generate synthetic eFuse telemetry, features, and fault labels."""
    if ctx.invoked_subcommand is not None:
        return
    configure_logging(json_format=json_log)
    log = get_logger(__name__)

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + _short_id()
    out_dir = output / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load config
    if config is not None:
        platform_cfg = load_config(config)
        sim_cfg: SimulationConfig = platform_cfg.simulation
        feat_cfg: FeatureConfig = platform_cfg.features
        store_cfg: StorageConfig = platform_cfg.storage
    else:
        sim_cfg = SimulationConfig()
        feat_cfg = FeatureConfig()
        store_cfg = StorageConfig(output_dir=str(output))

    # CLI overrides
    if duration is not None:
        sim_cfg = sim_cfg.model_copy(update={"duration_s": duration})
    if seed is not None:
        sim_cfg = sim_cfg.model_copy(update={"seed": seed})

    store_cfg = store_cfg.model_copy(update={"output_dir": str(out_dir), "format": fmt})

    console.rule("[bold cyan]VIP Data Generator")
    console.print(f"  Scenario  : [bold]{sim_cfg.name}[/bold]")
    console.print(f"  Channels  : {len(sim_cfg.channels)}")
    console.print(f"  Duration  : {sim_cfg.duration_s}s  |  Interval: {sim_cfg.sample_interval_ms}ms")
    console.print(f"  Seed      : {sim_cfg.seed}")
    console.print(f"  Output    : {out_dir}/")
    console.print()

    # 1. Generate raw telemetry
    console.print("[cyan]Generating telemetry...[/cyan]")
    gen = TelemetryGenerator(sim_cfg)
    telem_df, labels_df = gen.generate()
    log.info("Generated %d telemetry rows across %d channels", len(telem_df), len(sim_cfg.channels))

    # 2. Compute rolling features
    console.print("[cyan]Computing features...[/cyan]")
    engine = FeatureEngine(feat_cfg)
    features_df = engine.compute(telem_df)
    log.info("Computed features: %d rows, %d columns", len(features_df), len(features_df.columns))

    # 3. Save outputs
    console.print("[cyan]Writing output files...[/cyan]")
    writer = StorageWriter(store_cfg)
    writer.write_telemetry(telem_df)
    writer.write_features(features_df)
    if not labels_df.empty:
        writer.write_labels(labels_df)
    writer.write_channel_manifest(sim_cfg.channels)

    # 4. Save config snapshot
    config_snapshot = out_dir / "config.yaml"
    with open(config_snapshot, "w") as f:
        yaml.safe_dump(sim_cfg.model_dump(mode="json"), f, sort_keys=False)

    # Summary
    console.print()
    console.rule("[bold green]Done")
    console.print(f"  Telemetry  : {len(telem_df):,} rows")
    console.print(f"  Features   : {len(features_df):,} rows × {len(features_df.columns)} cols")
    console.print(f"  Fault wins : {len(labels_df):,} labelled samples")
    console.print(f"  Files      : {out_dir}/")
    console.print()


def _short_id(length: int = 6) -> str:
    import random
    import string
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
