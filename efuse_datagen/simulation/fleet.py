"""Fleet-scale telemetry generation.

Orchestrates parallel multi-vehicle, multi-day simulation using the existing
single-vehicle drive-cycle machinery.  Each vehicle is derived from a
*population archetype* and assigned:

- A unique deterministic seed (child of the master fleet seed)
- An age-dependent fault-rate profile
- A shared regional weather timeline (correlated ambient temperature)

Output layout::

    output/<config>_<timestamp>/
        fleet_manifest.parquet       vehicle_id, archetype, age_months, region, ...
        regions/
            temperate_weather.parquet   day, ambient_temp_c, supply_voltage_v
            nordic_weather.parquet
        vehicles/
            v0001/
                telemetry.parquet
                labels.parquet
                features.parquet
                drive_cycles.parquet
            v0002/
                ...
        fleet_telemetry.parquet      (optional, write_combined=True)
        fleet_labels.parquet         (optional)
        fleet_config.yaml

Usage::

    from efuse_datagen.config.models import load_config
    from efuse_datagen.simulation.fleet import FleetRunner

    cfg = load_config("path/to/fleet.yaml")   # cfg.fleet must be set
    runner = FleetRunner(cfg, output_dir=Path("output"))
    manifest = runner.run()
"""

from __future__ import annotations

import concurrent.futures
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from efuse_datagen.config.models import (
    FleetConfig,
    GeneratorConfig,
    RegionalWeatherConfig,
    SimulationConfig,
    StorageConfig,
    VehicleArchetypeConfig,
)
from efuse_datagen.utils.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Weather timeline
# ---------------------------------------------------------------------------


def build_regional_weather(
    region_cfg: RegionalWeatherConfig,
    n_days: int,
    seed: int,
    start_day_of_year: int = 1,
) -> pd.DataFrame:
    """Generate a daily weather timeline for a region.

    The ambient temperature follows:
        T(d) = mean + seasonal_amplitude * sin(2π(d - peak_day + 91) / 365)  +  noise

    The seasonal sine gives realistic summer/winter swings.  A small
    mean-reverting noise component adds day-to-day weather variation.

    Parameters
    ----------
    region_cfg  : RegionalWeatherConfig
    n_days      : Number of calendar days to generate
    seed        : RNG seed (one per region so regions are independent)
    start_day_of_year : Day-of-year for day 0 (1 = Jan 1)

    Returns
    -------
    DataFrame with columns: day_index, day_of_year, ambient_temp_c, supply_voltage_v
    """
    rng = np.random.default_rng(seed)
    days = np.arange(n_days)
    doy = (start_day_of_year + days - 1) % 365 + 1  # 1-based day of year

    # Seasonal component — peaks at season_peak_day
    phase = 2 * np.pi * (doy - region_cfg.season_peak_day + 91) / 365
    seasonal = region_cfg.seasonal_amplitude_c * np.sin(phase)

    # Mean-reverting noise
    noise = np.zeros(n_days)
    noise[0] = rng.normal(0, region_cfg.ambient_temp_std_c * 0.5)
    for i in range(1, n_days):
        noise[i] = 0.8 * noise[i - 1] + rng.normal(0, region_cfg.ambient_temp_std_c * 0.3)

    ambient = region_cfg.ambient_temp_mean_c + seasonal + noise

    # Supply voltage — small day-to-day variation around mean
    supply = rng.normal(
        region_cfg.supply_voltage_mean_v,
        region_cfg.supply_voltage_std_v,
        n_days,
    )
    supply = np.clip(supply, 10.5, 15.0)

    return pd.DataFrame({
        "day_index": days,
        "day_of_year": doy,
        "ambient_temp_c": np.round(ambient, 2),
        "supply_voltage_v": np.round(supply, 3),
    })


# ---------------------------------------------------------------------------
# Vehicle spec (sampled from archetype)
# ---------------------------------------------------------------------------


@dataclass
class VehicleSpec:
    """One vehicle sampled from a population archetype."""

    vehicle_id: str
    vehicle_index: int
    archetype_id: str
    region: str
    profile: str
    age_months: int
    seed: int
    fault_rate_overrides: dict[str, float] = field(default_factory=dict)


def sample_population(fleet_cfg: FleetConfig) -> list[VehicleSpec]:
    """Sample N vehicle specs from the archetype distribution.

    Returns a list of VehicleSpec, length = fleet_cfg.n_vehicles.
    Each vehicle gets a unique child seed derived from the master seed.
    """
    rng = np.random.default_rng(fleet_cfg.seed)
    seed_seq = np.random.SeedSequence(fleet_cfg.seed)
    child_seeds = seed_seq.spawn(fleet_cfg.n_vehicles)

    archetypes = fleet_cfg.archetypes
    weights = np.array([a.weight for a in archetypes], dtype=float)
    weights /= weights.sum()

    specs: list[VehicleSpec] = []
    for i in range(fleet_cfg.n_vehicles):
        arch_idx = int(rng.choice(len(archetypes), p=weights))
        arch: VehicleArchetypeConfig = archetypes[arch_idx]

        age = int(rng.integers(arch.age_months_min, max(arch.age_months_max, arch.age_months_min + 1)))

        child_entropy = child_seeds[i].entropy
        if isinstance(child_entropy, int):
            vseed = child_entropy % (2**31)
        else:
            vseed = int(child_entropy[0] % (2**31))

        specs.append(VehicleSpec(
            vehicle_id=f"v{i + 1:04d}",
            vehicle_index=i,
            archetype_id=arch.id,
            region=arch.region,
            profile=arch.profile,
            age_months=age,
            seed=vseed,
            fault_rate_overrides=dict(arch.fault_rate_overrides),
        ))

    return specs


# ---------------------------------------------------------------------------
# Per-vehicle config builder
# ---------------------------------------------------------------------------


def build_vehicle_sim_config(
    spec: VehicleSpec,
    fleet_cfg: FleetConfig,
    base_sim: SimulationConfig,
    regional_weather: pd.DataFrame,
    start_date: date,
) -> SimulationConfig:
    """Build a SimulationConfig for a single vehicle.

    - Applies age-dependent fault rate scaling on top of any archetype overrides
    - Sets `drive_cycle.ambient_temp_mean_c` from the regional weather mean
      (per-trip temperatures are further modulated inside DriveCyclePlanner)
    - Enables multi-cycle mode with the fleet's duration_days
    """
    base = base_sim

    # Fault rate model:
    #   age_months drives up connector_aging and gradual_degradation
    #   (doubles at 48 months, triples at 96 months)
    age_factor = 1.0 + min(spec.age_months / 48.0, 2.0)
    base_fr = base.drive_cycle.fault_rates

    fr_updates: dict[str, Any] = {}
    aging_fields = {"connector_aging", "gradual_degradation"}
    for fname in aging_fields:
        base_val = getattr(base_fr, fname)
        fr_updates[fname] = round(base_val * age_factor, 4)

    # Apply archetype-level overrides on top
    for fname, val in spec.fault_rate_overrides.items():
        if hasattr(base_fr, fname):
            fr_updates[fname] = float(val)

    updated_fr = base_fr.model_copy(update=fr_updates)

    # Regional ambient: use the mean of the weather column for the drive-cycle config
    ambient_mean = float(regional_weather["ambient_temp_c"].mean())
    ambient_std = float(regional_weather["ambient_temp_c"].std())

    dc_cfg = base.drive_cycle.model_copy(update={
        "enabled": True,
        "total_days": fleet_cfg.duration_days,
        "profile": spec.profile,
        "ambient_temp_mean_c": round(ambient_mean, 1),
        "ambient_temp_std_c": round(max(ambient_std, 1.0), 1),
        "fault_rates": updated_fr,
    })

    return base.model_copy(update={
        "seed": spec.seed,
        "drive_cycle": dc_cfg,
        "bus_voltage_nominal": float(regional_weather["supply_voltage_v"].mean()),
    })


# ---------------------------------------------------------------------------
# Top-level function for multiprocessing (must be module-level / picklable)
# ---------------------------------------------------------------------------


def _generate_vehicle(args: tuple) -> dict:
    """Generate one vehicle's full multi-cycle dataset.

    This function is the unit of work executed by ProcessPoolExecutor.
    It must be a module-level function (not a lambda / nested) to be picklable
    on macOS (which uses spawn rather than fork).

    Returns a result dict with paths and summary statistics.
    """
    (
        spec,
        fleet_cfg,
        base_sim,
        regional_weather_df,
        start_date,
        out_dir,
        feat_cfg_dict,
        run_id,
    ) = args

    try:
        from datetime import timezone as _tz

        from efuse_datagen.config.models import FeatureConfig
        from efuse_datagen.features.engine import FeatureEngine
        from efuse_datagen.simulation.drive_cycles import DriveCyclePlanner, generate_multi_cycle
        from efuse_datagen.storage.writer import StorageWriter

        log.info("[%s] Starting vehicle %s (archetype=%s, region=%s)",
                 run_id, spec.vehicle_id, spec.archetype_id, spec.region)

        sim_cfg = build_vehicle_sim_config(spec, fleet_cfg, base_sim, regional_weather_df, start_date)
        feat_cfg = FeatureConfig.model_validate(feat_cfg_dict)
        dc = sim_cfg.drive_cycle

        # Plan
        base_dt = datetime(
            start_date.year, start_date.month, start_date.day, 0, 0, 0, tzinfo=_tz.utc
        )
        planner = DriveCyclePlanner(dc, seed=sim_cfg.seed)
        cycles = planner.generate_schedule(base_dt)
        faults_per_cycle = planner.distribute_faults(cycles, sim_cfg.channels)

        # Generate
        telem_df, labels_df = generate_multi_cycle(sim_cfg, cycles, faults_per_cycle)

        if telem_df.empty:
            log.warning("[%s] Vehicle %s produced empty telemetry", run_id, spec.vehicle_id)
            return {"vehicle_id": spec.vehicle_id, "status": "empty", "n_rows": 0}

        # Tag vehicle
        telem_df["vehicle_id"] = spec.vehicle_id
        if not labels_df.empty:
            labels_df["vehicle_id"] = spec.vehicle_id

        # Features
        engine = FeatureEngine(feat_cfg)
        features_df = engine.compute(telem_df)

        # Write per-vehicle files
        v_dir = Path(out_dir) / "vehicles" / spec.vehicle_id
        v_dir.mkdir(parents=True, exist_ok=True)

        store_cfg = StorageConfig(output_dir=str(v_dir), format="parquet")
        writer = StorageWriter(store_cfg)
        writer.write_telemetry(telem_df)
        writer.write_features(features_df)
        if not labels_df.empty:
            writer.write_labels(labels_df)
        writer.write_channel_manifest(sim_cfg.channels)
        writer.write_drive_cycles(cycles)

        return {
            "vehicle_id": spec.vehicle_id,
            "status": "ok",
            "n_rows": len(telem_df),
            "n_labels": len(labels_df),
            "n_cycles": len(cycles),
            "driving_hours": sum(c.duration_s for c in cycles) / 3600,
            "telem_path": str(v_dir / "telemetry.parquet"),
            "labels_path": str(v_dir / "labels.parquet"),
            "features_path": str(v_dir / "features.parquet"),
        }

    except Exception as exc:  # noqa: BLE001
        log.error("[%s] Vehicle %s failed: %s", run_id, spec.vehicle_id, exc, exc_info=True)
        return {"vehicle_id": spec.vehicle_id, "status": f"error: {exc}", "n_rows": 0}


# ---------------------------------------------------------------------------
# Fleet runner
# ---------------------------------------------------------------------------


class FleetRunner:
    """Orchestrate fleet-scale generation across multiple vehicles in parallel.

    Parameters
    ----------
    cfg : GeneratorConfig
        Must have ``cfg.fleet`` set (non-None).
    output_dir : Path
        Root directory.  A timestamped sub-directory is created inside it.
    progress_callback : callable | None
        Called as ``(completed: int, total: int)`` after each vehicle finishes.
    """

    def __init__(
        self,
        cfg: GeneratorConfig,
        output_dir: Path = Path("output"),
        progress_callback=None,
    ) -> None:
        if cfg.fleet is None:
            raise ValueError("GeneratorConfig.fleet must be set for fleet mode")
        self.cfg = cfg
        self.fleet = cfg.fleet
        self.output_dir = Path(output_dir)
        self.progress_callback = progress_callback

    def run(self, run_id: str | None = None) -> pd.DataFrame:
        """Run the fleet simulation.

        Returns
        -------
        pd.DataFrame
            Vehicle manifest — one row per vehicle with identity, summary stats,
            and output paths.
        """
        if run_id is None:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            run_id = f"fleet_{ts}"

        out_dir = self.output_dir / run_id
        out_dir.mkdir(parents=True, exist_ok=True)

        start_date = date.fromisoformat(self.fleet.start_date)
        start_doy = start_date.timetuple().tm_yday

        # ── 1. Build regional weather timelines ──────────────────────
        log.info("Generating regional weather timelines (%d regions)...", len(self.fleet.regions))
        region_weather: dict[str, pd.DataFrame] = {}
        regions_dir = out_dir / "regions"
        regions_dir.mkdir(exist_ok=True)

        rng = np.random.default_rng(self.fleet.seed + 9999)  # isolated seed for regions
        for region_name, region_cfg in self.fleet.regions.items():
            region_seed = int(rng.integers(0, 2**31))
            weather_df = build_regional_weather(
                region_cfg,
                n_days=self.fleet.duration_days,
                seed=region_seed,
                start_day_of_year=start_doy,
            )
            region_weather[region_name] = weather_df
            weather_df.to_parquet(regions_dir / f"{region_name}_weather.parquet", index=False)
            log.info(
                "  Region %-20s  T_mean=%.1f°C  T_range=[%.1f, %.1f]°C",
                region_name,
                weather_df["ambient_temp_c"].mean(),
                weather_df["ambient_temp_c"].min(),
                weather_df["ambient_temp_c"].max(),
            )

        # ── 2. Sample vehicle population ─────────────────────────────
        specs = sample_population(self.fleet)
        log.info("Sampled %d vehicles from %d archetypes", len(specs), len(self.fleet.archetypes))

        # ── 3. Parallel vehicle generation ───────────────────────────
        feat_cfg_dict = self.cfg.features.model_dump()

        work_items = [
            (
                spec,
                self.fleet,
                self.cfg.simulation,
                region_weather.get(spec.region, list(region_weather.values())[0]),
                start_date,
                str(out_dir),
                str(out_dir),
                feat_cfg_dict,
                run_id,
            )
            for spec in specs
        ]

        results: list[dict] = []
        max_workers = min(self.fleet.max_workers, len(specs))

        log.info(
            "Generating %d vehicles with up to %d parallel workers...",
            len(specs),
            max_workers,
        )

        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_generate_vehicle, item): item[0] for item in work_items}
            done_count = 0
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                results.append(result)
                done_count += 1
                if self.progress_callback:
                    self.progress_callback(done_count, len(specs))
                if done_count % max(1, math.ceil(len(specs) / 10)) == 0 or done_count == len(specs):
                    ok = sum(1 for r in results if r.get("status") == "ok")
                    log.info("  Progress: %d/%d  (ok=%d)", done_count, len(specs), ok)

        # ── 4. Build manifest ─────────────────────────────────────────
        spec_by_id = {s.vehicle_id: s for s in specs}
        manifest_rows = []
        for res in results:
            spec = spec_by_id[res["vehicle_id"]]
            row = {
                "vehicle_id": spec.vehicle_id,
                "archetype_id": spec.archetype_id,
                "region": spec.region,
                "profile": spec.profile,
                "age_months": spec.age_months,
                "seed": spec.seed,
                "status": res.get("status", "unknown"),
                "n_telemetry_rows": res.get("n_rows", 0),
                "n_fault_labels": res.get("n_labels", 0),
                "n_drive_cycles": res.get("n_cycles", 0),
                "driving_hours": round(res.get("driving_hours", 0.0), 2),
                "telem_path": res.get("telem_path", ""),
                "labels_path": res.get("labels_path", ""),
                "features_path": res.get("features_path", ""),
            }
            manifest_rows.append(row)

        manifest_df = pd.DataFrame(manifest_rows).sort_values("vehicle_id")
        manifest_df.to_parquet(out_dir / "fleet_manifest.parquet", index=False)

        # ── 5. Optional combined outputs ──────────────────────────────
        if self.fleet.write_combined:
            self._write_combined(out_dir, manifest_df)

        # ── 6. Save config snapshot ───────────────────────────────────
        with open(out_dir / "fleet_config.yaml", "w") as f:
            yaml.safe_dump(self.cfg.model_dump(mode="json"), f, sort_keys=False)

        ok_count = len(manifest_df[manifest_df["status"] == "ok"])
        total_rows = manifest_df["n_telemetry_rows"].sum()
        total_hours = manifest_df["driving_hours"].sum()
        log.info(
            "Fleet run complete: %d/%d OK | %s total rows | %.0f vehicle-hours | → %s",
            ok_count,
            len(specs),
            f"{total_rows:,}",
            total_hours,
            out_dir,
        )

        return manifest_df

    @staticmethod
    def _write_combined(out_dir: Path, manifest_df: pd.DataFrame) -> None:
        """Concatenate all vehicle outputs into fleet-level files."""
        telem_parts: list[pd.DataFrame] = []
        label_parts: list[pd.DataFrame] = []

        for _, row in manifest_df.iterrows():
            if row["status"] != "ok":
                continue
            t_path = Path(row["telem_path"])
            l_path = Path(row["labels_path"])
            if t_path.exists():
                telem_parts.append(pd.read_parquet(t_path))
            if l_path.exists() and l_path.stat().st_size > 0:
                try:
                    label_parts.append(pd.read_parquet(l_path))
                except Exception:
                    pass

        if telem_parts:
            combined = pd.concat(telem_parts, ignore_index=True)
            combined.to_parquet(out_dir / "fleet_telemetry.parquet", index=False)
            log.info("Combined telemetry: %s rows → fleet_telemetry.parquet", f"{len(combined):,}")

        if label_parts:
            combined_labels = pd.concat(label_parts, ignore_index=True)
            combined_labels.to_parquet(out_dir / "fleet_labels.parquet", index=False)
            log.info("Combined labels: %s rows → fleet_labels.parquet", f"{len(combined_labels):,}")
