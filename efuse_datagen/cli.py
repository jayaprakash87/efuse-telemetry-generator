"""CLI for eFuse Telemetry Generator.

Example usage:
    efuse-gen                                     # quick_demo (3 ch, 60 s)
    efuse-gen --config single_drive               # 65 ch, one ignition cycle
    efuse-gen --config multi_day                   # 65 ch, 30 days
    efuse-gen --config fleet                       # 100 vehicles × 90 days
    efuse-gen --config fleet --vehicles 5 --days 7 # small fleet test
    efuse-gen --list-configs                       # show all built-in configs

The generator produces:
    <output>/<config>_<timestamp>/telemetry.parquet         raw per-sample eFuse signals
    <output>/<config>_<timestamp>/features.parquet          rolling derived features
    <output>/<config>_<timestamp>/labels.parquet            ground-truth fault windows
    <output>/<config>_<timestamp>/channel_manifest.parquet  per-channel metadata
    <output>/<config>_<timestamp>/drive_cycles.parquet      multi-cycle schedule (optional)
    <output>/<config>_<timestamp>/config.yaml               snapshot of the config used
"""

from __future__ import annotations

import multiprocessing
from datetime import datetime
from pathlib import Path

import typer
import yaml
from rich.console import Console

from efuse_datagen.config.builtin import list_bundled_configs, load_bundled_config
from efuse_datagen.config.models import (
    FeatureConfig,
    GeneratorConfig,
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

# ---------------------------------------------------------------------------
# topology subcommand group
# ---------------------------------------------------------------------------

topology_app = typer.Typer(
    name="topology",
    help="Import, export, and manage vehicle topology files.",
)
app.add_typer(topology_app, name="topology")


@topology_app.command("import")
def topology_import(
    source: Path = typer.Argument(
        ...,
        help="Path to CSV, Excel (.xlsx), or Parquet file with channel definitions.",
    ),
    output: Path = typer.Option(
        Path("topology.yaml"),
        "--output",
        "-o",
        help="Output YAML topology file.",
    ),
) -> None:
    """Import a vehicle topology from a spreadsheet into YAML.

    The spreadsheet should have one row per eFuse channel. Required columns:
    channel_id, zone_id. Recommended: efuse_family, load_name.

    Zone definitions are auto-generated from the zone_id column. Add optional
    zone_name, zone_location, zone_bus columns for richer zone metadata.

    Use 'efuse-gen topology template' to generate a CSV template with example rows.
    """
    from efuse_datagen.config.topology_io import import_topology

    topo = import_topology(source, output)
    n_z = len(topo["zones"])
    n_ch = len(topo["channel_specs"])
    console.print(f"[green]✓[/green] Imported {n_ch} channels across {n_z} zones from [bold]{source}[/bold]")
    console.print(f"  Output: [cyan]{output}[/cyan]")
    console.print()
    console.print("Use it in a scenario config:")
    console.print(f"  simulation:")
    console.print(f"    topology_file: ./{output.name}")


@topology_app.command("template")
def topology_template(
    output: Path = typer.Option(
        Path("channels_template.csv"),
        "--output",
        "-o",
        help="Output CSV template file.",
    ),
    minimal: bool = typer.Option(
        False,
        "--minimal",
        "-m",
        help="Emit only essential columns (channel_id, zone_id, efuse_family, load_name, load_type, zone_name).",
    ),
) -> None:
    """Generate a CSV template with example rows for filling in your vehicle topology.

    Open the CSV in Excel or Google Sheets, fill in your channels, then import:

        efuse-gen topology template -o my_channels.csv
        # ... fill in your data ...
        efuse-gen topology import my_channels.csv -o my_vehicle.yaml

    Use --minimal for a simpler template with only the essential columns.
    """
    from efuse_datagen.config.topology_io import export_template_csv

    export_template_csv(output, minimal=minimal)
    label = "minimal " if minimal else ""
    console.print(f"[green]✓[/green] {label.capitalize()}template written to [cyan]{output}[/cyan]")
    console.print()
    console.print("Fill in your channel data, then import:")
    console.print(f"  efuse-gen topology import {output} -o my_vehicle.yaml")


@topology_app.command("export")
def topology_export(
    source: Path = typer.Argument(
        ...,
        help="Path to the topology YAML file to export.",
    ),
    output: Path = typer.Option(
        Path("topology_export.csv"),
        "--output",
        "-o",
        help="Output CSV file.",
    ),
) -> None:
    """Export a topology YAML back to CSV for editing in a spreadsheet.

    Useful for modifying a bundled or imported topology in Excel / Sheets:

        efuse-gen topology export my_vehicle.yaml -o channels.csv
        # ... edit in Excel ...
        efuse-gen topology import channels.csv -o my_vehicle.yaml
    """
    from efuse_datagen.config.topology_io import export_topology_csv

    export_topology_csv(source, output)
    with open(source) as f:
        import yaml as _yaml
        topo = _yaml.safe_load(f)
    n_ch = len(topo.get("channel_specs", []))
    console.print(f"[green]✓[/green] Exported {n_ch} channels to [cyan]{output}[/cyan]")
    console.print()
    console.print("Edit in your spreadsheet, then re-import:")
    console.print(f"  efuse-gen topology import {output} -o {source.name}")


@topology_app.command("new")
def topology_new(
    output: Path = typer.Option(
        Path("my_vehicle.yaml"),
        "--output",
        "-o",
        help="Output YAML topology file.",
    ),
    template: str = typer.Option(
        "compact",
        "--template",
        "-t",
        help="Preset size: compact (2 zones / 12 ch), full (4 zones / 65 ch).",
    ),
) -> None:
    """Scaffold a new topology YAML from a bundled preset.

    Creates a copy of a bundled topology that you can edit directly:

        efuse-gen topology new -t compact -o my_prototype.yaml
        efuse-gen topology new -t full -o my_production.yaml

    Available presets: compact (bev_2zone_12ch), full (bev_4zone_65ch).
    """
    from importlib.resources import files as pkg_files

    presets = {
        "compact": "bev_2zone_12ch",
        "full": "bev_4zone_65ch",
    }
    key = template.lower()
    if key not in presets:
        raise typer.BadParameter(
            f"Unknown preset '{template}'. Available: {', '.join(sorted(presets))}"
        )

    bundled_name = presets[key]
    bundled = pkg_files("efuse_datagen").joinpath(f"config/topologies/{bundled_name}.yaml")
    content = bundled.read_text(encoding="utf-8")  # type: ignore[union-attr]

    output.write_text(content, encoding="utf-8")
    import yaml as _yaml
    topo = _yaml.safe_load(content)
    n_z = len(topo.get("zones", []))
    n_ch = len(topo.get("channel_specs", []))
    console.print(
        f"[green]✓[/green] Scaffolded [bold]{key}[/bold] topology "
        f"({n_z} zones, {n_ch} channels) → [cyan]{output}[/cyan]"
    )
    console.print()
    console.print("Reference it in your scenario config:")
    console.print(f"  simulation:")
    console.print(f"    topology_file: ./{output.name}")


@app.command("info")
def info(
    config: str = typer.Argument(
        ...,
        help="Path to YAML config or built-in name (quick_demo, single_drive, fleet, etc.).",
    ),
) -> None:
    """Display a summary of what a config contains without generating data.

    Shows scenario details, channel breakdown by zone and load type,
    fault injections, drive-cycle settings, and fleet configuration.

    Examples:

        efuse-gen info quick_demo
        efuse-gen info ./my_scenario.yaml
    """
    cfg, config_name = _load_requested_config(config)
    sim = cfg.simulation

    console.rule(f"[bold cyan]{sim.name}[/bold cyan]  ({config_name})")
    if sim.description:
        console.print(f"  {sim.description}")
    console.print()

    # Mode
    is_fleet = cfg.fleet is not None
    if is_fleet:
        mode = "Fleet"
    elif sim.drive_cycle.enabled:
        mode = "Multi-cycle"
    else:
        mode = "Single-cycle"
    console.print(f"  Mode        : [bold]{mode}[/bold]")
    console.print(f"  Channels    : {len(sim.channels)}")
    console.print(f"  Seed        : {sim.seed}")
    console.print(f"  Interval    : {sim.sample_interval_ms} ms")

    if not is_fleet and not sim.drive_cycle.enabled:
        console.print(f"  Duration    : {sim.duration_s} s")

    # Zone breakdown
    zones: dict[str, int] = {}
    load_types: dict[str, int] = {}
    for ch in sim.channels:
        z = ch.zone_id or "(unassigned)"
        zones[z] = zones.get(z, 0) + 1
        lt = ch.load_type.value if hasattr(ch.load_type, "value") else str(ch.load_type)
        load_types[lt] = load_types.get(lt, 0) + 1

    if zones:
        console.print()
        console.print("  [bold]Zones:[/bold]")
        for z, n in sorted(zones.items()):
            console.print(f"    {z}: {n} channels")

    if load_types:
        console.print()
        console.print("  [bold]Load types:[/bold]")
        for lt, n in sorted(load_types.items()):
            console.print(f"    {lt}: {n}")

    # Fault injections
    if sim.fault_injections:
        console.print()
        console.print(f"  [bold]Fault injections:[/bold] {len(sim.fault_injections)}")
        for fi in sim.fault_injections:
            console.print(f"    {fi.channel_id} → {fi.fault_type.value} at {fi.start_s}s ({fi.duration_s}s, intensity={fi.intensity})")

    # Drive cycle
    if sim.drive_cycle.enabled:
        dc = sim.drive_cycle
        console.print()
        console.print(f"  [bold]Drive cycle:[/bold]")
        console.print(f"    Days      : {dc.total_days}")
        console.print(f"    Profile   : {dc.profile}")

    # Fleet
    if is_fleet:
        fleet = cfg.fleet
        console.print()
        console.print(f"  [bold]Fleet:[/bold]")
        console.print(f"    Vehicles  : {fleet.n_vehicles}")
        console.print(f"    Days      : {fleet.duration_days}")
        console.print(f"    Archetypes: {len(fleet.archetypes)}")
        for a in fleet.archetypes:
            console.print(f"      {a.id} (weight={a.weight})")

    # Storage
    console.print()
    console.print(f"  [bold]Output:[/bold]")
    console.print(f"    Format    : {cfg.storage.format}")
    console.print(f"    Directory : {cfg.storage.output_dir}")


@app.callback(invoke_without_command=True)
def generate(
    ctx: typer.Context,
    config: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to YAML config, or a built-in name: quick_demo, single_drive, multi_day, fleet, stress_test.",
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
        help="Output format: parquet, csv, or json.",
    ),
    duration: float | None = typer.Option(
        None,
        "--duration",
        "-d",
        help="Override scenario duration in seconds (single-vehicle mode).",
    ),
    seed: int | None = typer.Option(
        None,
        "--seed",
        "-s",
        help="Override random seed for reproducibility.",
    ),
    # Fleet-specific options (only used when config has fleet: key)
    n_vehicles: int | None = typer.Option(
        None,
        "--vehicles",
        "-n",
        help="Override fleet vehicle count (fleet mode only).",
    ),
    duration_days: int | None = typer.Option(
        None,
        "--days",
        help="Override fleet duration in days (fleet mode only).",
    ),
    max_workers: int | None = typer.Option(
        None,
        "--workers",
        "-w",
        help="Override fleet parallel workers (fleet mode only).",
    ),
    write_combined: bool = typer.Option(
        False,
        "--combined",
        help="Write combined fleet_telemetry.parquet (fleet mode only).",
    ),
    json_log: bool = typer.Option(
        False,
        "--json-log",
        help="Emit structured JSON log lines instead of pretty output.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview what the config would generate without writing any files.",
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

    # ── CLI input validation ─────────────────────────────────────
    _VALID_FORMATS = {"parquet", "csv", "json"}
    if fmt not in _VALID_FORMATS:
        raise typer.BadParameter(
            f"Invalid format '{fmt}'. Choose from: {', '.join(sorted(_VALID_FORMATS))}."
        )
    if duration is not None and duration <= 0:
        raise typer.BadParameter("--duration must be > 0.")
    if seed is not None and seed < 0:
        raise typer.BadParameter("--seed must be >= 0.")
    if n_vehicles is not None and n_vehicles < 1:
        raise typer.BadParameter("--vehicles must be >= 1.")
    if duration_days is not None and duration_days < 1:
        raise typer.BadParameter("--days must be >= 1.")
    if max_workers is not None and max_workers < 1:
        raise typer.BadParameter("--workers must be >= 1.")

    # Load config
    cfg, config_name = _load_requested_config(config)

    # Reject mode-mismatched flags
    is_fleet = cfg.fleet is not None
    if is_fleet and duration is not None:
        raise typer.BadParameter(
            "--duration is not supported in fleet mode. Use --days for fleet duration."
        )
    if not is_fleet:
        fleet_flags = []
        if n_vehicles is not None:
            fleet_flags.append("--vehicles")
        if duration_days is not None:
            fleet_flags.append("--days")
        if max_workers is not None:
            fleet_flags.append("--workers")
        if write_combined:
            fleet_flags.append("--combined")
        if fleet_flags:
            raise typer.BadParameter(
                f"{', '.join(fleet_flags)} only work with fleet configs "
                f"(configs that have a fleet: section). "
                f"Try: efuse-gen --config fleet {' '.join(fleet_flags)}"
            )

    # ── Dry-run preview ────────────────────────────────────────
    if dry_run:
        sim_cfg = cfg.simulation
        if duration is not None:
            sim_cfg = sim_cfg.model_copy(update={"duration_s": duration})
        console.rule("[bold cyan]Dry Run — Preview")
        console.print(f"  Scenario  : [bold]{sim_cfg.name}[/bold]")
        console.print(f"  Mode      : {'Fleet' if is_fleet else 'Multi-cycle' if sim_cfg.drive_cycle.enabled else 'Single-cycle'}")
        console.print(f"  Channels  : {len(sim_cfg.channels)}")
        console.print(f"  Seed      : {seed or sim_cfg.seed}")
        if is_fleet:
            fleet = cfg.fleet
            nv = n_vehicles or fleet.n_vehicles
            dd = duration_days or fleet.duration_days
            console.print(f"  Vehicles  : {nv}")
            console.print(f"  Days      : {dd}")
            console.print(f"  Archetypes: {', '.join(a.id for a in fleet.archetypes)}")
        elif sim_cfg.drive_cycle.enabled:
            dc = sim_cfg.drive_cycle
            console.print(f"  Days      : {dc.total_days}")
            console.print(f"  Profile   : {dc.profile}")
            est_rows = int(sim_cfg.duration_s / (sim_cfg.sample_interval_ms / 1000) * len(sim_cfg.channels))
            console.print(f"  Est. rows : ~{est_rows:,} per cycle")
        else:
            n_samples = int(sim_cfg.duration_s / (sim_cfg.sample_interval_ms / 1000))
            est_rows = n_samples * len(sim_cfg.channels)
            console.print(f"  Duration  : {sim_cfg.duration_s}s  |  Interval: {sim_cfg.sample_interval_ms}ms")
            console.print(f"  Est. rows : {est_rows:,}")
        console.print(f"  Format    : {fmt}")
        console.print(f"  Output    : {output}/")
        console.print()
        console.print("[dim]No files written. Remove --dry-run to generate.[/dim]")
        return

    # Route to fleet mode if config has fleet section
    if cfg.fleet is not None:
        _run_fleet(cfg, config_name, output, n_vehicles, duration_days, max_workers, seed, write_combined, log)
        return

    # ── Single-vehicle mode ──────────────────────────────────────
    sim_cfg: SimulationConfig = cfg.simulation
    feat_cfg: FeatureConfig = cfg.features
    store_cfg: StorageConfig = cfg.storage

    run_id = f"{config_name}_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    out_dir = output / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

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
    # Single-cycle mode (default)
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

    # 4. Save config snapshot (full GeneratorConfig for reproducibility)
    config_snapshot = out_dir / "config.yaml"
    with open(config_snapshot, "w") as f:
        yaml.safe_dump(cfg.model_dump(mode="json"), f, sort_keys=False)

    # 5. Run README
    writer.write_run_readme(
        scenario_name=sim_cfg.name,
        n_channels=len(sim_cfg.channels),
        n_rows=len(telem_df),
        n_features=len(features_df),
        n_labels=len(labels_df),
        duration_s=sim_cfg.duration_s,
        fmt=fmt,
    )

    # Summary
    console.print()
    console.rule("[bold green]Done")
    console.print(f"  Telemetry  : {len(telem_df):,} rows")
    console.print(f"  Features   : {len(features_df):,} rows × {len(features_df.columns)} cols")
    console.print(f"  Fault wins : {len(labels_df):,} labelled samples")
    if cycles:
        console.print(f"  Cycles     : {len(cycles)}")
        console.print(f"  Driving    : {sum(c.duration_s for c in cycles)/3600:.1f} hours")
    console.print(f"  Files      : {out_dir.resolve()}/")
    console.print()
    console.print("[dim]Tip: run [bold]efuse-dashboard[/bold] to visualize results interactively (needs [dashboard] extra)[/dim]")
    console.print()


def _load_requested_config(config: str | None) -> tuple[GeneratorConfig, str]:
    """Load config and return (config, config_name) for output naming."""
    if config is None:
        return load_bundled_config("quick_demo"), "quick_demo"

    candidate = Path(config).expanduser()
    if candidate.exists():
        name = candidate.stem
        return load_config(candidate), name

    config_key = Path(config).stem
    bundled = list_bundled_configs()
    if config_key in bundled:
        return load_bundled_config(config_key), config_key

    choices = ", ".join(bundled)
    raise typer.BadParameter(
        f"Config '{config}' not found. Use a filesystem path or one of: {choices}."
    )


def _run_fleet(
    cfg: GeneratorConfig,
    config_name: str,
    output: Path,
    n_vehicles: int | None,
    duration_days: int | None,
    max_workers: int | None,
    seed: int | None,
    write_combined: bool,
    log,
) -> None:
    """Run fleet-scale generation (invoked when config has a fleet: section)."""
    from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn

    from efuse_datagen.simulation.fleet import FleetRunner

    fleet = cfg.fleet
    assert fleet is not None

    # CLI overrides
    overrides: dict = {}
    if n_vehicles is not None:
        overrides["n_vehicles"] = n_vehicles
    if duration_days is not None:
        overrides["duration_days"] = duration_days
    if max_workers is not None:
        overrides["max_workers"] = max_workers
    if seed is not None:
        overrides["seed"] = seed
    if write_combined:
        overrides["write_combined"] = True
    if overrides:
        cfg = cfg.model_copy(update={"fleet": fleet.model_copy(update=overrides)})
        fleet = cfg.fleet

    run_id = f"{config_name}_{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    console.rule("[bold cyan]eFuse Fleet Generator")
    console.print(f"  Vehicles    : {fleet.n_vehicles}")
    console.print(f"  Duration    : {fleet.duration_days} days")
    console.print(f"  Start date  : {fleet.start_date}")
    console.print(f"  Archetypes  : {len(fleet.archetypes)}")
    console.print(f"  Regions     : {', '.join(fleet.regions)}")
    console.print(f"  Workers     : {fleet.max_workers}")
    console.print(f"  Output      : {output / run_id}/")
    console.print()

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%  {task.completed}/{task.total}"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Vehicles", total=fleet.n_vehicles)

        def _cb(done: int, total: int) -> None:
            progress.update(task, completed=done)

        runner = FleetRunner(cfg, output_dir=output, progress_callback=_cb)
        manifest_df = runner.run(run_id=run_id)

    ok = len(manifest_df[manifest_df["status"] == "ok"])
    total_rows = manifest_df["n_telemetry_rows"].sum()
    total_hours = manifest_df["driving_hours"].sum()
    total_labels = manifest_df["n_fault_labels"].sum()

    console.print()
    console.rule("[bold green]Fleet generation complete")
    console.print(f"  Vehicles    : {ok}/{fleet.n_vehicles} succeeded")
    console.print(f"  Telemetry   : {total_rows:,} rows")
    console.print(f"  Fault labels: {total_labels:,}")
    console.print(f"  Vehicle-hrs : {total_hours:,.1f}")
    console.print(f"  Manifest    : {output / run_id}/fleet_manifest.parquet")
    console.print()


# ---------------------------------------------------------------------------
# ingest subcommand
# ---------------------------------------------------------------------------

ingest_app = typer.Typer(
    name="ingest",
    help="Ingest real measurement data (CSV / Parquet / MDF / BLF) into the standard eFuse run format.",
    add_completion=False,
)
app.add_typer(ingest_app, name="ingest")


@ingest_app.command()
def ingest(
    source: Path = typer.Argument(..., help="Path to a measurement file or directory of files."),
    output: Path = typer.Option(
        Path("output"),
        "--output", "-o",
        help="Root directory for ingested runs.",
    ),
    column_map: str | None = typer.Option(
        None,
        "--map", "-m",
        help="Column mapping as key=value pairs, e.g. 'I_ch01=current_a,U_bat=voltage_v,T_junc=temperature_c'.",
    ),
    time_column: str = typer.Option(
        "timestamp",
        "--time-col",
        help="Name of the timestamp column in the source file.",
    ),
    channel_id: str | None = typer.Option(
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

    run_id = f"ingest_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
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
    multiprocessing.freeze_support()
    app()


if __name__ == "__main__":
    main()
