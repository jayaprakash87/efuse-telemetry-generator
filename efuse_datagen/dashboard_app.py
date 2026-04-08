"""Streamlit dashboard for eFuse Telemetry Generator outputs.

Slim orchestrator — each tab lives in ``efuse_datagen.dashboard.tabs.*``.
Supports both single-vehicle and fleet runs.

Launch via the ``efuse-dashboard`` entry point or ``dashboard/app.py``.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from efuse_datagen.dashboard._shared import (
    is_fleet_run,
    list_fleet_vehicles,
    list_runs,
    load_drive_cycles,
    load_fleet_manifest,
    load_fleet_vehicle,
    load_manifest,
    load_regional_weather,
    load_run,
    render_data_source_banner,
)
from efuse_datagen.dashboard.tabs import config, features, overview, protection, signals

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="eFuse Telemetry Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sidebar — run + channel selector
# ---------------------------------------------------------------------------

st.sidebar.title("⚡ eFuse Telemetry Dashboard")
st.sidebar.markdown("---")

runs = list_runs()
if not runs:
    st.error(
        "No output runs found. Run `efuse-gen` first to generate data.\n\n"
        "```\nefuse-gen --duration 120\n```"
    )
    st.stop()


def _run_display_name(p: str) -> str:
    name = Path(p).name
    if is_fleet_run(p):
        return f"🚛 {name}"
    return name


selected_run = st.sidebar.selectbox("Output run", runs, index=0, format_func=_run_display_name)

fleet_mode = is_fleet_run(selected_run)

# ---------------------------------------------------------------------------
# Fleet run — vehicle selector & fleet-level data
# ---------------------------------------------------------------------------

fleet_manifest = None
fleet_weather = None
selected_vehicle = None

if fleet_mode:
    st.sidebar.info("🚛 Fleet run")
    fleet_manifest = load_fleet_manifest(selected_run)
    fleet_weather = load_regional_weather(selected_run)

    vehicles = list_fleet_vehicles(selected_run)
    if not vehicles:
        st.error("Fleet run has no vehicle directories.")
        st.stop()

    selected_vehicle = st.sidebar.selectbox(
        "Vehicle",
        vehicles,
        index=0,
        format_func=lambda v: (
            f"{v} — {fleet_manifest.loc[fleet_manifest['vehicle_id'] == v, 'archetype_id'].values[0]}"
            if v in fleet_manifest["vehicle_id"].values
            else v
        ),
    )
    # Load the selected vehicle's data
    tel, feat, lab = load_fleet_vehicle(selected_run, selected_vehicle)
    manifest = load_manifest(str(Path(selected_run) / "vehicles" / selected_vehicle))
    dc_df = load_drive_cycles(str(Path(selected_run) / "vehicles" / selected_vehicle))
else:
    render_data_source_banner(selected_run)
    tel, feat, lab = load_run(selected_run)
    manifest = load_manifest(selected_run)
    dc_df = load_drive_cycles(selected_run)

# ---------------------------------------------------------------------------
# Drive cycle filter (multi-cycle runs only)
# ---------------------------------------------------------------------------

is_multi_cycle = "drive_cycle_id" in tel.columns and dc_df is not None
if is_multi_cycle:
    _day_opts = sorted(dc_df["day"].unique().tolist())
    _day_labels = {d: f"Day {d}" for d in _day_opts}
    sel_days = st.sidebar.multiselect(
        "Days",
        _day_opts,
        default=_day_opts,
        format_func=lambda d: _day_labels.get(d, str(d)),
    )
    _cycle_ids = set(dc_df[dc_df["day"].isin(sel_days)]["cycle_id"].tolist())
    tel = tel[tel["drive_cycle_id"].isin(_cycle_ids)]
    if not feat.empty and "drive_cycle_id" in feat.columns:
        feat = feat[feat["drive_cycle_id"].isin(_cycle_ids)]
    if not lab.empty and "drive_cycle_id" in lab.columns:
        lab = lab[lab["drive_cycle_id"].isin(_cycle_ids)]

# ---------------------------------------------------------------------------
# Zone + channel filter
# ---------------------------------------------------------------------------

if manifest is not None:
    all_zones = sorted(manifest["zone_id"].dropna().unique().tolist())
    sel_zones = st.sidebar.multiselect("Zone filter", all_zones, default=all_zones)
    zone_ch_ids = set(manifest[manifest["zone_id"].isin(sel_zones)]["channel_id"].tolist())
    channels = sorted([c for c in tel["channel_id"].unique() if c in zone_ch_ids])
    label_map: dict[str, str] = {
        row.channel_id: f"{row.channel_id} — {row.load_name}" if row.load_name else row.channel_id
        for row in manifest.itertuples()
    }
else:
    channels = sorted(tel["channel_id"].unique().tolist())
    label_map = {}

selected_channels = st.sidebar.multiselect(
    "Channels",
    channels,
    default=channels[:4],
    format_func=lambda c: label_map.get(c, c),
)
if not selected_channels:
    st.warning("Select at least one channel.")
    st.stop()

st.sidebar.markdown("---")
if fleet_mode and selected_vehicle:
    st.sidebar.caption(f"Fleet: `{Path(selected_run).name}`")
    st.sidebar.caption(f"Vehicle: `{selected_vehicle}`")
else:
    st.sidebar.caption(f"Run: `{Path(selected_run).name}`")
st.sidebar.caption(f"Samples: {len(tel):,} | Channels: {len(channels)}")

# ---------------------------------------------------------------------------
# Shared context dict passed to every tab
# ---------------------------------------------------------------------------

ctx = dict(
    tel=tel, feat=feat, lab=lab,
    manifest=manifest, dc_df=dc_df,
    selected_channels=selected_channels,
    channels=channels,
    selected_run=selected_run,
    label_map=label_map,
    is_multi_cycle=is_multi_cycle,
    fleet_mode=fleet_mode,
    fleet_manifest=fleet_manifest,
    fleet_weather=fleet_weather,
    selected_vehicle=selected_vehicle,
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_labels = ["📊 Overview", "📡 Signals", "🔬 Features", "🛡️ Fault & Protection", "📋 Config"]
if fleet_mode:
    tab_labels.insert(0, "🚛 Fleet")

tabs = st.tabs(tab_labels)
tab_idx = 0

if fleet_mode:
    with tabs[tab_idx]:
        overview.render_fleet(**ctx)
    tab_idx += 1

with tabs[tab_idx]:
    overview.render(**ctx)
tab_idx += 1

with tabs[tab_idx]:
    signals.render(**ctx)
tab_idx += 1

with tabs[tab_idx]:
    features.render(**ctx)
tab_idx += 1

with tabs[tab_idx]:
    protection.render(**ctx)
tab_idx += 1

with tabs[tab_idx]:
    config.render(**ctx)
