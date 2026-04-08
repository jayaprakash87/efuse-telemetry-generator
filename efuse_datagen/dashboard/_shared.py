"""Shared utilities, data loaders, and constants for the dashboard."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import streamlit as st

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Output root — configurable via env var
# ---------------------------------------------------------------------------

OUTPUT_ROOT = Path(
    os.environ.get("EFUSE_TELEMETRY_OUTPUT_DIR", Path.cwd() / "output")
).expanduser()

# ---------------------------------------------------------------------------
# Fault colour palette
# ---------------------------------------------------------------------------

FAULT_PALETTE: dict[str, str] = {
    "none": "rgba(0,0,0,0)",
    "overload_spike": "#ef4444",
    "intermittent_overload": "#f97316",
    "voltage_sag": "#eab308",
    "thermal_drift": "#a855f7",
    "noisy_sensor": "#06b6d4",
    "dropped_packet": "#64748b",
    "gradual_degradation": "#f43f5e",
    "connector_aging": "#d97706",
    "open_load": "#3b82f6",
    "jump_start": "#10b981",
    "load_dump": "#dc2626",
    "cold_crank": "#0ea5e9",
    "thermal_coupling": "#8b5cf6",
    "wake_transient": "#14b8a6",
}

# ---------------------------------------------------------------------------
# Data source detection
# ---------------------------------------------------------------------------

DATA_SOURCE_LABELS = {
    "synthetic": ("🧪 Synthetic Data", "info"),
    "bench": ("🔬 Bench Recording", "success"),
    "hil": ("🏗️ HIL Recording", "success"),
    "production": ("🚗 Production Data", "warning"),
}


def detect_data_source(run_dir: str) -> str:
    p = Path(run_dir)
    marker = p / "data_source.txt"
    if marker.exists():
        return marker.read_text().strip().lower()
    # Fleet run → synthetic
    if (p / "fleet_manifest.parquet").exists():
        return "synthetic"
    # config.yaml with scenario_id → synthetic
    cfg_path = p / "config.yaml"
    if cfg_path.exists():
        import yaml

        try:
            cfg = yaml.safe_load(cfg_path.read_text())
            if isinstance(cfg, dict) and "scenario_id" in cfg and "channels" in cfg:
                return "synthetic"
        except Exception:
            pass
    if (p / "mapping.yaml").exists():
        return "bench"
    return "bench"


def render_data_source_banner(run_dir: str) -> None:
    source = detect_data_source(run_dir)
    label, kind = DATA_SOURCE_LABELS.get(source, ("❓ Unknown", "info"))
    getattr(st.sidebar, kind)(label)


# ---------------------------------------------------------------------------
# Cached data loaders
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def load_run(run_dir: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    p = Path(run_dir)

    tel_path = p / "telemetry.parquet"
    if not tel_path.exists():
        st.error(f"Missing telemetry.parquet in {p.name}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try:
        tel = pd.read_parquet(tel_path)
    except Exception as exc:
        st.error(f"Failed to read telemetry.parquet: {exc}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    _REQUIRED_TEL_COLS = {"timestamp", "channel_id", "current_a"}
    missing = _REQUIRED_TEL_COLS - set(tel.columns)
    if missing:
        st.error(f"Telemetry missing required columns: {sorted(missing)}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    feat = pd.read_parquet(p / "features.parquet") if (p / "features.parquet").exists() else pd.DataFrame()
    if (p / "labels.parquet").exists():
        try:
            lab = pd.read_parquet(p / "labels.parquet")
        except Exception:
            lab = pd.DataFrame(columns=[
                "timestamp", "channel_id", "fault_type", "severity", "description",
            ])
    else:
        # Empty labels with expected schema so downstream code doesn't KeyError
        lab = pd.DataFrame(columns=[
            "timestamp", "channel_id", "fault_type", "severity", "description",
        ])
    for df in (tel, feat, lab):
        if "timestamp" in df.columns and not df.empty:
            if pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
                if df["timestamp"].dt.tz is not None:
                    df["timestamp"] = df["timestamp"].dt.tz_convert("UTC").dt.tz_localize(None)
    return tel, feat, lab


@st.cache_data(show_spinner=False)
def load_manifest(run_dir: str) -> pd.DataFrame | None:
    p = Path(run_dir) / "channel_manifest.parquet"
    if not p.exists():
        return None
    return pd.read_parquet(p)


@st.cache_data(show_spinner=False)
def load_drive_cycles(run_dir: str) -> pd.DataFrame | None:
    p = Path(run_dir) / "drive_cycles.parquet"
    if not p.exists():
        return None
    dc = pd.read_parquet(p)
    for col in ("start_time", "end_time"):
        if col in dc.columns and dc[col].dt.tz is not None:
            dc[col] = dc[col].dt.tz_convert("UTC").dt.tz_localize(None)
    return dc


def list_runs() -> list[str]:
    """Discover run directories under OUTPUT_ROOT (1- or 2-level deep).

    Recognises both single-vehicle runs (contain ``telemetry.parquet``) and
    fleet runs (contain ``fleet_manifest.parquet``).  Fleet vehicle sub-dirs
    are NOT listed individually — select the fleet root to explore vehicles.
    """
    if not OUTPUT_ROOT.exists():
        return []
    found: list[str] = []
    for d in OUTPUT_ROOT.iterdir():
        if not d.is_dir():
            continue
        # Fleet run (fleet_manifest.parquet at root)
        if (d / "fleet_manifest.parquet").exists():
            found.append(str(d))
            continue
        # Single-vehicle run with telemetry.parquet
        if (d / "telemetry.parquet").exists():
            found.append(str(d))
            continue
        # Nested: output/<source>/<run_id>/telemetry.parquet  (e.g. bench/ingest_*)
        for sub in d.iterdir():
            if not sub.is_dir():
                continue
            if (sub / "fleet_manifest.parquet").exists():
                found.append(str(sub))
            elif (sub / "telemetry.parquet").exists():
                found.append(str(sub))
    return sorted(found, reverse=True)


def is_fleet_run(run_dir: str) -> bool:
    """Return True if the run directory is a fleet run."""
    return (Path(run_dir) / "fleet_manifest.parquet").exists()


@st.cache_data(show_spinner=False)
def load_fleet_manifest(run_dir: str) -> pd.DataFrame:
    """Load the fleet manifest — one row per vehicle with summary stats."""
    return pd.read_parquet(Path(run_dir) / "fleet_manifest.parquet")


def list_fleet_vehicles(run_dir: str) -> list[str]:
    """Return sorted list of vehicle IDs available in a fleet run."""
    vehicles_dir = Path(run_dir) / "vehicles"
    if not vehicles_dir.exists():
        return []
    return sorted(
        d.name for d in vehicles_dir.iterdir()
        if d.is_dir() and (d / "telemetry.parquet").exists()
    )


@st.cache_data(show_spinner=False)
def load_fleet_vehicle(run_dir: str, vehicle_id: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load telemetry, features, labels for a single fleet vehicle."""
    v_dir = Path(run_dir) / "vehicles" / vehicle_id
    return load_run(str(v_dir))


@st.cache_data(show_spinner=False)
def load_fleet_combined(run_dir: str) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Load combined fleet telemetry and labels (if --combined was used)."""
    p = Path(run_dir)
    tel = pd.read_parquet(p / "fleet_telemetry.parquet") if (p / "fleet_telemetry.parquet").exists() else None
    lab = pd.read_parquet(p / "fleet_labels.parquet") if (p / "fleet_labels.parquet").exists() else None
    for df in (tel, lab):
        if df is not None and "timestamp" in df.columns and not df.empty:
            if pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
                if df["timestamp"].dt.tz is not None:
                    df["timestamp"] = df["timestamp"].dt.tz_convert("UTC").dt.tz_localize(None)
    return tel, lab


@st.cache_data(show_spinner=False)
def load_regional_weather(run_dir: str) -> dict[str, pd.DataFrame]:
    """Load regional weather timelines from a fleet run."""
    regions_dir = Path(run_dir) / "regions"
    if not regions_dir.exists():
        return {}
    result: dict[str, pd.DataFrame] = {}
    for f in sorted(regions_dir.glob("*_weather.parquet")):
        name = f.stem.replace("_weather", "")
        result[name] = pd.read_parquet(f)
    return result


# ---------------------------------------------------------------------------
# Fault shading helper (reused across tabs)
# ---------------------------------------------------------------------------


def build_fault_shapes(
    ch_lab: pd.DataFrame,
    y_ranges: list[tuple[float, float]],
) -> list[dict]:
    """Build plotly shape dicts for fault-coloured rectangles.

    Parameters
    ----------
    ch_lab : DataFrame
        Label rows for one channel (with timestamp, fault_type).
    y_ranges : list of (y0, y1) per subplot row

    Returns
    -------
    list of plotly shape dicts
    """
    shapes: list[dict] = []
    faults = ch_lab[ch_lab["fault_type"] != "none"]
    if faults.empty:
        return shapes

    for fault_type in faults["fault_type"].unique():
        color = FAULT_PALETTE.get(fault_type, "#999999")
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        fill = f"rgba({r},{g},{b},0.19)"
        windows = faults[faults["fault_type"] == fault_type]
        ts_sorted = windows["timestamp"].sort_values()
        gap = pd.Timedelta("500ms")
        start = prev = ts_sorted.iloc[0]
        for t in ts_sorted.iloc[1:]:
            if t - prev > gap:
                for row_idx, (y0, y1) in enumerate(y_ranges, start=1):
                    shapes.append(dict(
                        type="rect", xref="x",
                        yref=f"y{row_idx if row_idx > 1 else ''}",
                        x0=start, x1=prev, y0=y0, y1=y1,
                        fillcolor=fill, line=dict(width=0), layer="below",
                    ))
                start = t
            prev = t
        # Final window
        for row_idx, (y0, y1) in enumerate(y_ranges, start=1):
            shapes.append(dict(
                type="rect", xref="x",
                yref=f"y{row_idx if row_idx > 1 else ''}",
                x0=start, x1=prev, y0=y0, y1=y1,
                fillcolor=fill, line=dict(width=0), layer="below",
            ))

    return shapes
