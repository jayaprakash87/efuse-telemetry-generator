"""Streamlit dashboard for eFuse Telemetry Generator outputs.

Slim orchestrator — each tab lives in ``efuse_datagen.dashboard.tabs.*``.

Launch via the ``efuse-dashboard`` entry point or ``dashboard/app.py``.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from efuse_datagen.dashboard._shared import (
    list_runs,
    load_drive_cycles,
    load_manifest,
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

selected_run = st.sidebar.selectbox("Output run", runs, index=0, format_func=lambda p: Path(p).name)
render_data_source_banner(selected_run)

tel, feat, lab = load_run(selected_run)
manifest = load_manifest(selected_run)
dc_df = load_drive_cycles(selected_run)

# Drive cycle filter (multi-cycle runs only)
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
    feat = feat[feat["drive_cycle_id"].isin(_cycle_ids)]
    if "drive_cycle_id" in lab.columns:
        lab = lab[lab["drive_cycle_id"].isin(_cycle_ids)]

# Zone filter
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
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_overview, tab_signals, tab_features, tab_protection, tab_config = st.tabs([
    "📊 Overview",
    "📡 Signals",
    "🔬 Features",
    "🛡️ Fault & Protection",
    "📋 Config",
])

with tab_overview:
    overview.render(**ctx)

with tab_signals:
    signals.render(**ctx)

with tab_features:
    features.render(**ctx)

with tab_protection:
    protection.render(**ctx)

with tab_config:
    config.render(**ctx)
