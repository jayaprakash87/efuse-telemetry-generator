"""Persistence helpers for generator outputs.

Writes telemetry, features, labels, channel manifests, drive-cycle
metadata, and optional alert payloads to local files. Supports Parquet
(default), CSV, and JSON.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from efuse_datagen.config.models import StorageConfig
from efuse_datagen.utils.logging import get_logger

log = get_logger(__name__)


class StorageWriter:
    """Write generator DataFrames and alert payloads to local storage."""

    def __init__(self, config: StorageConfig | None = None, disk_min_free_mb: int = 0) -> None:
        self.cfg = config or StorageConfig()
        self._out = Path(self.cfg.output_dir)
        self._out.mkdir(parents=True, exist_ok=True)
        self._disk_min_free_mb = disk_min_free_mb

    def write_telemetry(self, df: pd.DataFrame, name: str = "telemetry") -> Path:
        return self._write_df(df, name)

    def write_features(self, df: pd.DataFrame, name: str = "features") -> Path:
        return self._write_df(df, name)

    def write_labels(self, df: pd.DataFrame, name: str = "labels") -> Path:
        return self._write_df(df, name)

    def write_scored(self, df: pd.DataFrame, name: str = "scored") -> Path:
        return self._write_df(df, name)

    def write_channel_manifest(self, channels: list, name: str = "channel_manifest") -> Path | None:
        """Write per-channel static metadata so the dashboard can display zone/load info."""
        if not channels:
            return None
        rows = [
            {
                "channel_id": ch.channel_id,
                "zone_id": ch.zone_id,
                "load_name": ch.load_name,
                "system_cluster": ch.system_cluster,
                "system_name": ch.system_name,
                "efuse_family": ch.efuse_family.value if hasattr(ch.efuse_family, "value") else str(ch.efuse_family),
                "load_type": ch.load_type,
                "power_class": ch.power_class.value if hasattr(ch.power_class, "value") else str(ch.power_class),
                "nominal_current_a": ch.nominal_current_a,
                "max_current_a": ch.max_current_a,
                "fuse_rating_a": ch.fuse_rating_a,
                "r_ds_on_ohm": ch.r_ds_on_ohm,
                "r_thermal_kw": ch.r_thermal_kw,
                "tau_thermal_s": ch.tau_thermal_s,
                "t_ambient_c": ch.t_ambient_c,
                "thermal_shutdown_c": ch.thermal_shutdown_c,
                "harness_r_ohm": ch.harness_r_ohm,
                "connector_r_ohm": ch.connector_r_ohm,
                "wire_gauge_mm2": ch.wire_gauge_mm2,
                "run_length_m": ch.run_length_m,
                "die_id": ch.die_id,
                "thermal_coupling_coeff": ch.thermal_coupling_coeff,
                "duty_cycle": ch.duty_cycle,
                "on_duration_s": ch.on_duration_s,
                "off_duration_s": ch.off_duration_s,
            }
            for ch in channels
        ]
        df = pd.DataFrame(rows)
        return self._write_df(df, name)

    def write_drive_cycles(self, cycles, name: str = "drive_cycles") -> Path | None:
        """Write drive-cycle schedule metadata."""
        if not cycles:
            return None
        rows = [
            {
                "cycle_id": c.cycle_id,
                "day": c.day,
                "start_time": c.start_time,
                "end_time": c.end_time,
                "duration_s": c.duration_s,
                "ambient_temp_c": c.ambient_temp_c,
                "drive_type": c.drive_type,
            }
            for c in cycles
        ]
        df = pd.DataFrame(rows)
        return self._write_df(df, name)

    def check_disk_space(self) -> bool:
        """Return True if disk has enough free space (or threshold is 0)."""
        if self._disk_min_free_mb <= 0:
            return True
        try:
            usage = shutil.disk_usage(self._out)
            free_mb = usage.free / (1024 * 1024)
            if free_mb < self._disk_min_free_mb:
                log.warning(
                    "Low disk space: %.0f MB free (threshold: %d MB) — skipping write",
                    free_mb,
                    self._disk_min_free_mb,
                )
                return False
        except OSError:
            pass  # can't check → allow write
        return True

    def write_alerts(self, alerts: list[dict], name: str = "alerts") -> Path | None:
        p = self._out / f"{name}.json"
        if not self.check_disk_space():
            return None
        # Append-safe: read existing, extend, rewrite
        existing = []
        if p.exists():
            with open(p) as f:
                existing = json.load(f)
        existing.extend(alerts)
        with open(p, "w") as f:
            json.dump(existing, f, indent=2, default=str)
        log.info("Wrote %d alerts to %s", len(alerts), p)
        return p

    def _write_df(self, df: pd.DataFrame, name: str) -> Path | None:
        if not self.check_disk_space():
            return None
        # Serialize list columns as JSON strings for round-trip fidelity
        df_out = df.copy()
        for col in df_out.columns:
            if df_out[col].apply(lambda x: isinstance(x, list)).any():
                df_out[col] = df_out[col].apply(json.dumps)

        fmt = self.cfg.format
        if fmt == "parquet":
            p = self._out / f"{name}.parquet"
            df_out.to_parquet(p, index=False)
        elif fmt == "csv":
            p = self._out / f"{name}.csv"
            df_out.to_csv(p, index=False)
        else:
            p = self._out / f"{name}.json"
            df_out.to_json(p, orient="records", date_format="iso", indent=2)
        log.info("Wrote %d rows to %s", len(df_out), p)
        return p

    def write_run_readme(
        self,
        *,
        scenario_name: str = "",
        n_channels: int = 0,
        n_rows: int = 0,
        n_features: int = 0,
        n_labels: int = 0,
        duration_s: float = 0,
        fmt: str = "parquet",
    ) -> Path:
        """Write a short README.md into the run directory for discoverability."""
        ext = fmt if fmt != "parquet" else "parquet"
        lines = [
            f"# {scenario_name or 'eFuse Run'}",
            "",
            f"Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Files",
            "",
            "| File | Rows | Description |",
            "|------|------|-------------|",
            f"| `telemetry.{ext}` | {n_rows:,} | Raw eFuse signals (current, voltage, temperature, protection events) |",
            f"| `features.{ext}` | {n_features:,} | Rolling statistics (RMS current, spike score, temp slope, …) |",
            f"| `labels.{ext}` | {n_labels:,} | Ground-truth fault windows with type and severity |",
            f"| `channel_manifest.{ext}` | {n_channels} | Per-channel metadata (zone, load, eFuse family, electrical params) |",
            "| `config.yaml` | — | Full scenario config for exact reproducibility |",
            "",
            "## Quick Load",
            "",
            "```python",
            "import pandas as pd",
            "",
            f'telem = pd.read_{fmt}("telemetry.{ext}")',
            f'feats = pd.read_{fmt}("features.{ext}")',
            f'labels = pd.read_{fmt}("labels.{ext}")',
            "```",
            "",
            "## Visualize",
            "",
            "```bash",
            "efuse-dashboard   # interactive Streamlit dashboard",
            "```",
            "",
        ]
        p = self._out / "README.md"
        p.write_text("\n".join(lines))
        return p
