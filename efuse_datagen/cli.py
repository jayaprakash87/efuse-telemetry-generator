"""CLI for eFuse Telemetry Generator.

Example usage:
    efuse-gen
    efuse-gen --config zone_controller_full
    efuse-gen --config one_month
    efuse-gen --config default --output my_run/ --format csv
    efuse-gen --config default --duration 120 --seed 99

The generator produces:
    <output>/<run_id>/telemetry.parquet         raw per-sample eFuse signals
    <output>/<run_id>/features.parquet          rolling derived features
    <output>/<run_id>/labels.parquet            ground-truth fault windows
    <output>/<run_id>/channel_manifest.parquet  per-channel metadata for the dashboard
    <output>/<run_id>/drive_cycles.parquet      multi-cycle schedule metadata (optional)
    <output>/<run_id>/config.yaml               snapshot of the config used
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console

from efuse_datagen.config.builtin import list_bundled_configs, load_bundled_config
from efuse_datagen.config.models import (
    FeatureConfig,
    PlatformConfig,
    SimulationConfig,
    StorageConfig,
    load_config,
)
from efuse_datagen.features.engine import FeatureEngine
from efuse_datagen.simulation.generator import TelemetryGenerator
from efuse_datagen.storage.writer import StorageWriter
from efuse_datagen.utils.logging import configure_logging, get_logger

app = typer.Typer(
    name="efuse-gen",
    help="Synthetic eFuse telemetry generator for ZC architecture validation.",
    add_completion=False,
    invoke_without_command=True,
)
console = Console()


@app.callback(invoke_without_command=True)
def generate(
    ctx: typer.Context,
    config: Optional[str] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to YAML scenario config, or a built-in config name such as default or one_month.",
    ),
    list_configs: bool = typer.Option(
        False,
        "--list-configs",
        help="List the built-in packaged scenario configs and exit.",
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

    if list_configs:
        console.print("Built-in configs:")
        for key, filename in list_bundled_configs().items():
            console.print(f"  [cyan]{key}[/cyan]  ({filename})")
        return

    configure_logging(json_format=json_log)
    log = get_logger(__name__)

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + _short_id()
    out_dir = output / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load config
    platform_cfg = _load_requested_config(config)
    sim_cfg: SimulationConfig = platform_cfg.simulation
    feat_cfg: FeatureConfig = platform_cfg.features
    store_cfg: StorageConfig = platform_cfg.storage

    # CLI overrides
    if duration is not None:
        sim_cfg = sim_cfg.model_copy(update={"duration_s": duration})
    if seed is not None:
        sim_cfg = sim_cfg.model_copy(update={"seed": seed})

    store_cfg = store_cfg.model_copy(update={"output_dir": str(out_dir), "format": fmt})

    console.rule("[bold cyan]eFuse Telemetry Generator")
    console.print(f"  Scenario  : [bold]{sim_cfg.name}[/bold]")
    console.print(f"  Channels  : {len(sim_cfg.channels)}")
    console.print(f"  Seed      : {sim_cfg.seed}")
    console.print(f"  Output    : {out_dir}/")

    # ------------------------------------------------------------------
    # Multi-cycle mode (drive_cycle.enabled = true)
    # ------------------------------------------------------------------
    if sim_cfg.drive_cycle.enabled:
        from datetime import timezone

        from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn

        from efuse_datagen.simulation.drive_cycles import (
            DriveCyclePlanner,
            generate_multi_cycle,
        )

        dc = sim_cfg.drive_cycle
        console.print(
            f"  Mode      : [bold magenta]Multi-cycle[/bold magenta]  "
            f"({dc.total_days} days, profile={dc.profile})"
        )
        console.print(f"  Interval  : {sim_cfg.sample_interval_ms}ms")
        console.print()

        # Plan schedule
        console.print("[cyan]Planning drive cycle schedule...[/cyan]")
        base_time = (
            datetime.now(tz=timezone.utc)
            .replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        )
        planner = DriveCyclePlanner(dc, seed=sim_cfg.seed)
        cycles = planner.generate_schedule(base_time)
        total_hours = sum(c.duration_s for c in cycles) / 3600
        console.print(
            f"  Cycles    : {len(cycles)}  |  "
            f"Total driving: {total_hours:.1f} h"
        )

        # Distribute faults
        console.print("[cyan]Distributing faults stochastically...[/cyan]")
        faults_per_cycle = planner.distribute_faults(cycles, sim_cfg.channels)
        total_faults = sum(len(v) for v in faults_per_cycle.values())
        console.print(f"  Faults    : {total_faults} injections planned")
        console.print()

        # Generate each cycle with progress bar
        console.print("[cyan]Generating telemetry per cycle...[/cyan]")
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Cycles", total=len(cycles))

            def _cb(done: int, total: int) -> None:
                progress.update(task, completed=done)

            telem_df, labels_df = generate_multi_cycle(
                sim_cfg, cycles, faults_per_cycle, progress_callback=_cb
            )

        log.info(
            "Generated %d telemetry rows across %d cycles",
            len(telem_df),
            len(cycles),
        )

    # ------------------------------------------------------------------
    # Single-cycle mode (legacy / default)
    # ------------------------------------------------------------------
    else:
        console.print(
            f"  Duration  : {sim_cfg.duration_s}s  |  Interval: {sim_cfg.sample_interval_ms}ms"
        )
        console.print()

        console.print("[cyan]Generating telemetry...[/cyan]")
        gen = TelemetryGenerator(sim_cfg)
        telem_df, labels_df = gen.generate()
        log.info(
            "Generated %d telemetry rows across %d channels",
            len(telem_df),
            len(sim_cfg.channels),
        )
        cycles = None  # no drive-cycle schedule to write

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
    if cycles:
        writer.write_drive_cycles(cycles)

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
    if cycles:
        console.print(f"  Cycles     : {len(cycles)}")
        console.print(f"  Driving    : {sum(c.duration_s for c in cycles)/3600:.1f} hours")
    console.print(f"  Files      : {out_dir}/")
    console.print()


def _short_id(length: int = 6) -> str:
    import random
    import string
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def _load_requested_config(config: str | None) -> PlatformConfig:
    """Load either a filesystem config or one of the packaged built-in configs."""
    if config is None:
        return load_bundled_config("default")

    candidate = Path(config).expanduser()
    if candidate.exists():
        return load_config(candidate)

    config_key = Path(config).stem
    bundled = list_bundled_configs()
    if config_key in bundled:
        return load_bundled_config(config_key)

    choices = ", ".join(bundled)
    raise typer.BadParameter(
        f"Config '{config}' not found. Use a filesystem path or one of: {choices}."
    )


# ---------------------------------------------------------------------------
# efuse-ingest sub-command
# ---------------------------------------------------------------------------

ingest_app = typer.Typer(
    name="efuse-ingest",
    help="Ingest real measurement data (CSV / Parquet / MDF / BLF) into the standard eFuse run format.",
    add_completion=False,
)


@ingest_app.command()
def ingest(
    source: Path = typer.Argument(..., help="Path to a measurement file or directory of files."),
    output: Path = typer.Option(
        Path("output"),
        "--output", "-o",
        help="Root directory for ingested runs.",
    ),
    column_map: Optional[str] = typer.Option(
        None,
        "--map", "-m",
        help="Column mapping as key=value pairs, e.g. 'I_ch01=current_a,U_bat=voltage_v,T_junc=temperature_c'.",
    ),
    time_column: str = typer.Option(
        "timestamp",
        "--time-col",
        help="Name of the timestamp column in the source file.",
    ),
    channel_id: Optional[str] = typer.Option(
        None,
        "--channel",
        help="Override channel_id (default: derive from filename).",
    ),
    glob_pattern: str = typer.Option(
        "*.csv",
        "--glob",
        help="Glob pattern when source is a directory.",
    ),
    data_source_tag: str = typer.Option(
        "bench",
        "--source-tag",
        help="Data source tag: bench, hil, or production.",
    ),
) -> None:
    """Ingest measurement data into the standard run format."""
    from datetime import datetime

    from efuse_datagen.ingestion import MeasurementAdapter, save_as_run

    configure_logging(json_format=False)

    # Parse column map
    cmap: dict[str, str] = {}
    if column_map:
        for pair in column_map.split(","):
            pair = pair.strip()
            if "=" in pair:
                k, v = pair.split("=", 1)
                cmap[k.strip()] = v.strip()

    adapter = MeasurementAdapter(
        column_map=cmap,
        time_column=time_column,
        default_channel_id=channel_id or "ch_001",
    )

    source = source.expanduser()
    if source.is_dir():
        tel_df = adapter.load_directory(source, glob_pattern=glob_pattern)
    else:
        tel_df = adapter.load(source, channel_id=channel_id)

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + _short_id()
    run_dir = output / run_id

    save_as_run(
        telemetry_df=tel_df,
        output_dir=run_dir,
        data_source=data_source_tag,
    )

    console.rule("[bold green]Ingestion complete")
    console.print(f"  Samples  : {len(tel_df):,}")
    console.print(f"  Channels : {tel_df['channel_id'].nunique()}")
    console.print(f"  Source   : {data_source_tag}")
    console.print(f"  Output   : {run_dir}/")
    console.print()


def main() -> None:
    app()


def ingest_main() -> None:
    ingest_app()


if __name__ == "__main__":
    main()
