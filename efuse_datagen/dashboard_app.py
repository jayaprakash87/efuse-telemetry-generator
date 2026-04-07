"""Streamlit dashboard for eFuse Telemetry Generator outputs.

This module is packaged so the dashboard can be launched from an installed
wheel via the ``efuse-dashboard`` entry point or via the repo compatibility
wrapper at ``dashboard/app.py``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="eFuse Telemetry Generator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OUTPUT_ROOT = Path(
    os.environ.get(
        "EFUSE_TELEMETRY_OUTPUT_DIR",
        os.environ.get("VIP_DATA_GENERATOR_OUTPUT_DIR", Path.cwd() / "output"),
    )
).expanduser()

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


@st.cache_data(show_spinner=False)
def load_run(run_dir: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    p = Path(run_dir)
    tel = pd.read_parquet(p / "telemetry.parquet")
    feat = pd.read_parquet(p / "features.parquet")
    lab = pd.read_parquet(p / "labels.parquet")
    # Ensure timezone-naive for plotly compat
    for df in (tel, feat, lab):
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
    if not OUTPUT_ROOT.exists():
        return []
    return sorted(
        [str(d) for d in OUTPUT_ROOT.iterdir() if d.is_dir()],
        reverse=True,
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

# Zone filter (only when manifest is available)
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
# Tabs
# ---------------------------------------------------------------------------

tab_overview, tab_telemetry, tab_features, tab_faults, tab_protection, tab_config = st.tabs([
    "📊 Overview",
    "📡 Telemetry",
    "🔬 Features",
    "⚠️ Fault Analysis",
    "🛡️ Protection Events",
    "📋 Config",
])

# ============================================================
# TAB 1 — OVERVIEW
# ============================================================
with tab_overview:
    st.header("Run Overview")

    duration_s = (tel["timestamp"].max() - tel["timestamp"].min()).total_seconds()
    total_faults = (lab["fault_type"] != "none").sum()
    trip_events = tel["trip_flag"].sum()
    active_faults = lab[lab["fault_type"] != "none"]["fault_type"].nunique()

    if is_multi_cycle:
        _dc_sel = dc_df[dc_df["cycle_id"].isin(_cycle_ids)]
        _total_h = _dc_sel["duration_s"].sum() / 3600
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("Drive Cycles", len(_dc_sel))
        col2.metric("Driving", f"{_total_h:.1f} h")
        col3.metric("Channels", len(channels))
        col4.metric("Total Samples", f"{len(tel):,}")
        col5.metric("Fault Labels", f"{total_faults:,}")
        col6.metric("Trip Events", f"{int(trip_events):,}")
    else:
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Duration", f"{duration_s:.0f} s")
        col2.metric("Channels", len(channels))
        col3.metric("Total Samples", f"{len(tel):,}")
        col4.metric("Fault Windows", f"{total_faults:,}")
        col5.metric("Trip Events", f"{int(trip_events):,}")

    # Drive cycle timeline (multi-cycle only)
    if is_multi_cycle:
        st.markdown("---")
        st.subheader("Drive Cycle Timeline")
        _dc_plot = _dc_sel.copy()
        _dc_plot["label"] = _dc_plot.apply(
            lambda r: f"Day {r['day']} — {r['drive_type']} ({r['duration_s']/60:.0f} min, {r['ambient_temp_c']:.0f}°C)",
            axis=1,
        )
        fig_dc = px.timeline(
            _dc_plot,
            x_start="start_time",
            x_end="end_time",
            y="drive_type",
            color="drive_type",
            hover_name="label",
            labels={"drive_type": "Type"},
        )
        fig_dc.update_layout(height=250, margin=dict(t=10, b=10), showlegend=False)
        st.plotly_chart(fig_dc, width="stretch")

    st.markdown("---")
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Fault Type Distribution")
        fault_counts = (
            lab[lab["fault_type"] != "none"]
            .groupby("fault_type")
            .size()
            .reset_index(name="count")
        )
        if fault_counts.empty:
            st.info("No faults injected in this run.")
        else:
            pie = px.pie(
                fault_counts,
                names="fault_type",
                values="count",
                color="fault_type",
                color_discrete_map=FAULT_PALETTE,
                hole=0.35,
            )
            pie.update_traces(textposition="inside", textinfo="percent+label")
            pie.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(pie, width="stretch")

    with col_r:
        st.subheader("Fault Exposure per Channel")
        ch_fault = (
            lab[lab["fault_type"] != "none"]
            .groupby(["channel_id", "fault_type"])
            .size()
            .reset_index(name="samples")
        )
        if ch_fault.empty:
            st.info("No faults injected in this run.")
        else:
            bar = px.bar(
                ch_fault,
                x="channel_id",
                y="samples",
                color="fault_type",
                color_discrete_map=FAULT_PALETTE,
                labels={"samples": "Fault Samples", "channel_id": "Channel"},
            )
            bar.update_layout(
                legend_title_text="Fault Type",
                margin=dict(t=10, b=10, l=10, r=10),
            )
            st.plotly_chart(bar, width="stretch")

    st.subheader("Channel Summary")
    summary = (
        tel.groupby("channel_id")
        .agg(
            mean_current=("current_a", "mean"),
            max_current=("current_a", "max"),
            mean_temp=("temperature_c", "mean"),
            max_temp=("temperature_c", "max"),
            trip_count=("trip_flag", "sum"),
        )
        .round(2)
        .reset_index()
    )
    summary.columns = ["Channel", "Mean I (A)", "Max I (A)", "Mean T (°C)", "Max T (°C)", "Trips"]
    st.dataframe(summary, width="stretch", hide_index=True)

# ============================================================
# TAB 2 — TELEMETRY
# ============================================================
with tab_telemetry:
    st.header("Raw Telemetry Time Series")
    st.caption("Fault injection windows shown as shaded regions. Grey shading = channel powered off.")

    vis_channels = selected_channels
    if len(vis_channels) > 8:
        st.warning(
            f"Displaying first 8 of {len(selected_channels)} selected channels to keep the page responsive."
        )
        vis_channels = vis_channels[:8]

    for ch in vis_channels:
        ch_label = label_map.get(ch, ch)
        st.markdown(f"#### `{ch_label}`")
        ch_tel = tel[tel["channel_id"] == ch].sort_values("timestamp")
        ch_lab = lab[lab["channel_id"] == ch]

        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            subplot_titles=["Current (A)", "Voltage (V)", "Temperature (°C)"],
        )

        # Current
        fig.add_trace(
            go.Scatter(
                x=ch_tel["timestamp"], y=ch_tel["current_a"],
                name="I (A)", line=dict(color="#3b82f6", width=1),
                showlegend=False,
            ),
            row=1, col=1,
        )
        # Trip events as markers
        trips = ch_tel[ch_tel["trip_flag"]]
        if not trips.empty:
            fig.add_trace(
                go.Scatter(
                    x=trips["timestamp"], y=trips["current_a"],
                    mode="markers",
                    marker=dict(color="#ef4444", size=5, symbol="x"),
                    name="Trip",
                    showlegend=True,
                ),
                row=1, col=1,
            )

        # Voltage
        fig.add_trace(
            go.Scatter(
                x=ch_tel["timestamp"], y=ch_tel["voltage_v"],
                name="V (V)", line=dict(color="#10b981", width=1),
                showlegend=False,
            ),
            row=2, col=1,
        )

        # Temperature
        fig.add_trace(
            go.Scatter(
                x=ch_tel["timestamp"], y=ch_tel["temperature_c"],
                name="T (°C)", line=dict(color="#f97316", width=1),
                showlegend=False,
            ),
            row=3, col=1,
        )

        # Fault shading on all rows
        i_min = float(ch_tel["current_a"].min())
        i_max = float(ch_tel["current_a"].max())
        v_min = float(ch_tel["voltage_v"].min())
        v_max = float(ch_tel["voltage_v"].max())
        t_min = float(ch_tel["temperature_c"].min())
        t_max = float(ch_tel["temperature_c"].max())

        legend_shown: set = set()
        fault_legend_traces: dict[str, bool] = {}
        for fault_type in ch_lab[ch_lab["fault_type"] != "none"]["fault_type"].unique():
            color = FAULT_PALETTE.get(fault_type, "#999999")
            r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
            fill = f"rgba({r},{g},{b},0.19)"  # noqa: F841
            fault_legend_traces[fault_type] = color

        # Add one invisible scatter per fault type for the legend
        for fault_type, color in fault_legend_traces.items():
            fig.add_trace(
                go.Scatter(
                    x=[None], y=[None],
                    mode="markers",
                    marker=dict(size=10, color=color, symbol="square"),
                    name=fault_type.replace("_", " ").title(),
                    showlegend=True,
                ),
                row=1, col=1,
            )

        shapes = []
        for fault_type in ch_lab[ch_lab["fault_type"] != "none"]["fault_type"].unique():
            color = FAULT_PALETTE.get(fault_type, "#999999")
            r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
            fill = f"rgba({r},{g},{b},0.19)"
            windows = ch_lab[ch_lab["fault_type"] == fault_type]
            ts_sorted = windows["timestamp"].sort_values()
            gap = pd.Timedelta("500ms")
            start = prev = ts_sorted.iloc[0]
            for t in ts_sorted.iloc[1:]:
                if t - prev > gap:
                    for row_idx, (y0, y1) in enumerate(
                        [(i_min, i_max), (v_min, v_max), (t_min, t_max)], start=1
                    ):
                        shapes.append(dict(
                            type="rect", xref="x", yref=f"y{row_idx if row_idx > 1 else ''}",
                            x0=start, x1=prev, y0=y0, y1=y1,
                            fillcolor=fill, line=dict(width=0), layer="below",
                        ))
                    start = t
                prev = t
            for row_idx, (y0, y1) in enumerate(
                [(i_min, i_max), (v_min, v_max), (t_min, t_max)], start=1
            ):
                shapes.append(dict(
                    type="rect", xref="x", yref=f"y{row_idx if row_idx > 1 else ''}",
                    x0=start, x1=prev, y0=y0, y1=y1,
                    fillcolor=fill, line=dict(width=0), layer="below",
                ))

            # state_on_off: grey ribbon where the channel is unpowered because of
            # sleep, duty-cycle gating, or a protection shutdown.
        off_mask = ~ch_tel["state_on_off"].astype(bool)
        if off_mask.any():
            off_ts = ch_tel.loc[off_mask, "timestamp"]
            gap = pd.Timedelta("200ms")
            start = prev = off_ts.iloc[0]
            _ranges = [(i_min, i_max), (v_min, v_max), (t_min, t_max)]
            for t in off_ts.iloc[1:]:
                if t - prev > gap:
                    for row_idx, (y0, y1) in enumerate(_ranges, start=1):
                        shapes.append(dict(
                            type="rect", xref="x", yref=f"y{row_idx if row_idx > 1 else ''}",
                            x0=start, x1=prev, y0=y0, y1=y1,
                            fillcolor="rgba(100,100,100,0.12)", line=dict(width=0), layer="below",
                        ))
                    start = t
                prev = t
            for row_idx, (y0, y1) in enumerate(_ranges, start=1):
                shapes.append(dict(
                    type="rect", xref="x", yref=f"y{row_idx if row_idx > 1 else ''}",
                    x0=start, x1=prev, y0=y0, y1=y1,
                    fillcolor="rgba(100,100,100,0.12)", line=dict(width=0), layer="below",
                ))
            # Legend entry for off state
            fig.add_trace(
                go.Scatter(
                    x=[None], y=[None],
                    mode="markers",
                    marker=dict(size=10, color="rgba(100,100,100,0.3)", symbol="square"),
                    name="Channel off",
                    showlegend=True,
                ),
                row=1, col=1,
            )

        fig.update_layout(
            shapes=shapes,
            height=500,
            margin=dict(t=40, b=20, l=60, r=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        fig.update_yaxes(title_text="A", row=1, col=1)
        fig.update_yaxes(title_text="V", row=2, col=1)
        fig.update_yaxes(title_text="°C", row=3, col=1)

        st.plotly_chart(fig, width="stretch")
        st.markdown("---")

# ============================================================
# TAB 3 — FEATURES
# ============================================================
with tab_features:
    st.header("Derived Feature Time Series")

    feature_options = [
        "rolling_rms_current",
        "rolling_mean_current",
        "spike_score",
        "temperature_slope",
        "trip_frequency",
        "degradation_trend",
        "recovery_time_s",
        "protection_event_rate",
        "rolling_voltage_drop",
    ]
    available = [c for c in feature_options if c in feat.columns]
    selected_features = st.multiselect(
        "Features to plot",
        available,
        default=["rolling_rms_current", "spike_score", "temperature_slope", "trip_frequency"],
    )

    if not selected_features:
        st.info("Select at least one feature.")
    else:
        for ch in selected_channels:
            ch_label = label_map.get(ch, ch)
            st.markdown(f"#### `{ch_label}`")
            ch_feat = feat[feat["channel_id"] == ch].sort_values("timestamp")
            ch_lab = lab[lab["channel_id"] == ch]

            n = len(selected_features)
            fig = make_subplots(
                rows=n, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.04,
                subplot_titles=selected_features,
            )

            colors = px.colors.qualitative.Plotly
            for i, feature in enumerate(selected_features, start=1):
                fig.add_trace(
                    go.Scatter(
                        x=ch_feat["timestamp"],
                        y=ch_feat[feature],
                        name=feature,
                        line=dict(color=colors[(i - 1) % len(colors)], width=1.2),
                        showlegend=False,
                    ),
                    row=i, col=1,
                )

            # Fault shading — use full y range per subplot
            shapes = []
            for fault_type in ch_lab[ch_lab["fault_type"] != "none"]["fault_type"].unique():
                color = FAULT_PALETTE.get(fault_type, "#999999")
                r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
                fill = f"rgba({r},{g},{b},0.19)"
                windows = ch_lab[ch_lab["fault_type"] == fault_type]
                ts_sorted = windows["timestamp"].sort_values()
                gap = pd.Timedelta("500ms")
                start = prev = ts_sorted.iloc[0]
                for t in ts_sorted.iloc[1:]:
                    if t - prev > gap:
                        for row_idx in range(1, n + 1):
                            f_name = selected_features[row_idx - 1]
                            y0 = float(ch_feat[f_name].min())
                            y1 = float(ch_feat[f_name].max())
                            shapes.append(dict(
                                type="rect",
                                xref="x",
                                yref=f"y{row_idx if row_idx > 1 else ''}",
                                x0=start, x1=prev, y0=y0, y1=y1,
                                fillcolor=fill, line=dict(width=0), layer="below",
                            ))
                        start = t
                    prev = t
                for row_idx in range(1, n + 1):
                    f_name = selected_features[row_idx - 1]
                    y0 = float(ch_feat[f_name].min())
                    y1 = float(ch_feat[f_name].max())
                    shapes.append(dict(
                        type="rect",
                        xref="x",
                        yref=f"y{row_idx if row_idx > 1 else ''}",
                        x0=start, x1=prev, y0=y0, y1=y1,
                        fillcolor=fill, line=dict(width=0), layer="below",
                    ))

            fig.update_layout(
                shapes=shapes,
                height=200 * n,
                margin=dict(t=40, b=20, l=70, r=20),
            )
            st.plotly_chart(fig, width="stretch")
            st.markdown("---")

# ============================================================
# TAB 4 — FAULT ANALYSIS
# ============================================================
with tab_faults:
    st.header("Fault Analysis")

    col_l, col_r = st.columns([2, 1])

    with col_l:
        st.subheader("Fault Timeline (Gantt)")
        ch_order = sorted(selected_channels)
        fault_rows = []
        for ch in ch_order:
            ch_lab = lab[(lab["channel_id"] == ch) & (lab["fault_type"] != "none")]
            for fault_type in ch_lab["fault_type"].unique():
                windows = ch_lab[ch_lab["fault_type"] == fault_type]["timestamp"].sort_values()
                gap = pd.Timedelta("500ms")
                start = prev = windows.iloc[0]
                for t in windows.iloc[1:]:
                    if t - prev > gap:
                        fault_rows.append(dict(
                            Channel=ch,
                            FaultType=fault_type.replace("_", " ").title(),
                            Start=start,
                            Finish=prev,
                        ))
                        start = t
                    prev = t
                fault_rows.append(dict(
                    Channel=ch,
                    FaultType=fault_type.replace("_", " ").title(),
                    Start=start,
                    Finish=prev,
                ))

        if fault_rows:
            gantt_df = pd.DataFrame(fault_rows)
            fig_gantt = px.timeline(
                gantt_df,
                x_start="Start",
                x_end="Finish",
                y="Channel",
                color="FaultType",
                labels={"FaultType": "Fault Type"},
            )
            fig_gantt.update_layout(height=max(300, len(ch_order) * 60 + 80), margin=dict(t=10, b=10))
            st.plotly_chart(fig_gantt, width="stretch")
        else:
            st.info("No fault windows found for selected channels.")

    with col_r:
        st.subheader("Severity Distribution")
        sev_data = lab[(lab["channel_id"].isin(selected_channels)) & (lab["fault_type"] != "none")]
        if not sev_data.empty:
            hist = px.histogram(
                sev_data,
                x="severity",
                color="fault_type",
                color_discrete_map=FAULT_PALETTE,
                nbins=20,
                labels={"severity": "Severity Score"},
            )
            hist.update_layout(showlegend=False, margin=dict(t=10, b=10))
            st.plotly_chart(hist, width="stretch")
        else:
            st.info("No fault data.")

    st.subheader("Fault Window Table")
    fault_table = (
        lab[
            (lab["channel_id"].isin(selected_channels)) & (lab["fault_type"] != "none")
        ]
        .sort_values(["channel_id", "timestamp"])
        .assign(timestamp=lambda d: d["timestamp"].dt.strftime("%H:%M:%S.%f").str[:-3])
        [["timestamp", "channel_id", "fault_type", "severity", "description"]]
        .rename(columns={
            "timestamp": "Time",
            "channel_id": "Channel",
            "fault_type": "Fault Type",
            "severity": "Severity",
            "description": "Description",
        })
    )
    st.dataframe(fault_table, width="stretch", hide_index=True)

# ============================================================
# TAB 5 — PROTECTION EVENTS
# ============================================================
with tab_protection:
    st.header("Protection Event Analysis")

    prot_cols = [
        "protection_event_rate",
        "scp_count",
        "i2t_count",
        "latch_off_count",
        "thermal_shutdown_count",
        "open_load_diag_count",
        "over_voltage_count",
    ]
    avail_prot = [c for c in prot_cols if c in feat.columns]

    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Protection Event Rate Over Time")
        if "protection_event_rate" in feat.columns:
            ch_data = feat[feat["channel_id"].isin(selected_channels)].sort_values("timestamp")
            fig_prot = px.line(
                ch_data,
                x="timestamp",
                y="protection_event_rate",
                color="channel_id",
                labels={"protection_event_rate": "Event Rate", "channel_id": "Channel"},
            )
            fig_prot.update_layout(height=300, margin=dict(t=10, b=10))
            st.plotly_chart(fig_prot, width="stretch")
        else:
            st.info("protection_event_rate not in features.")

    with col_r:
        st.subheader("Protection Events by Type")
        _event_vals = ["scp", "i2t", "latch_off", "thermal_shutdown", "open_load_diag", "over_voltage"]
        event_rows = []
        for _ch in selected_channels:
            _ch_tel = tel[tel["channel_id"] == _ch].sort_values("timestamp")
            for _ev in _event_vals:
                _is_active = (_ch_tel["protection_event"] == _ev).astype(int)
                _edges = int(_is_active.diff().clip(lower=0).sum())
                if _edges > 0:
                    event_rows.append({
                        "channel_id": _ch,
                        "Event Type": _ev.upper().replace("_", " "),
                        "Count": _edges,
                    })
        if event_rows:
            _totals_df = pd.DataFrame(event_rows)
            bar_prot = px.bar(
                _totals_df,
                x="channel_id",
                y="Count",
                color="Event Type",
                barmode="group",
                labels={"channel_id": "Channel"},
            )
            bar_prot.update_layout(height=300, margin=dict(t=10, b=10))
            st.plotly_chart(bar_prot, width="stretch")
        else:
            st.info("No protection events for selected channels.")

    st.subheader("Protection Event Heatmap")
    if event_rows and len(selected_channels) > 1:
        _heat_df = (
            pd.DataFrame(event_rows)
            .pivot_table(index="channel_id", columns="Event Type", values="Count", fill_value=0)
        )
        fig_heat = px.imshow(
            _heat_df,
            text_auto=True,
            color_continuous_scale="Reds",
            labels={"x": "Event Type", "y": "Channel", "color": "Count"},
            aspect="auto",
        )
        fig_heat.update_layout(height=300, margin=dict(t=10, b=10))
        st.plotly_chart(fig_heat, width="stretch")
    elif len(selected_channels) == 1:
        st.info("Select multiple channels to see the heatmap.")

# ============================================================
# TAB 6 — CONFIG / METADATA
# ============================================================
with tab_config:
    st.header("Scenario Config & Channel Inventory")

    col_l, col_r = st.columns([1, 2])

    with col_l:
        st.subheader("Run info")
        run_name = Path(selected_run).name
        st.markdown(f"**Run ID:** `{run_name}`")
        st.markdown(f"**Samples:** {len(tel):,}")
        st.markdown(f"**Channels:** {len(channels)}")
        duration_s = (tel["timestamp"].max() - tel["timestamp"].min()).total_seconds()
        st.markdown(f"**Duration:** {duration_s:.0f} s")

        config_path = Path(selected_run) / "config.yaml"
        if config_path.exists():
            st.subheader("Config YAML")
            with open(config_path) as _f:
                _yaml_text = _f.read()
            st.code(_yaml_text, language="yaml")

    with col_r:
        st.subheader("Channel inventory")
        if manifest is not None:
            display_cols = [
                "channel_id", "zone_id", "load_name", "system_cluster",
                "efuse_family", "load_type", "power_class",
                "nominal_current_a", "duty_cycle",
            ]
            _inv = manifest[[c for c in display_cols if c in manifest.columns]].copy()
            _inv.columns = [c.replace("_", " ").title() for c in _inv.columns]
            st.dataframe(_inv, width="stretch", hide_index=True)

            st.subheader("Zone distribution")
            _zone_counts = manifest.groupby("zone_id").size().reset_index(name="Channels")
            _zone_bar = px.bar(
                _zone_counts,
                x="zone_id",
                y="Channels",
                labels={"zone_id": "Zone"},
                color="zone_id",
            )
            _zone_bar.update_layout(showlegend=False, height=250, margin=dict(t=10, b=10))
            st.plotly_chart(_zone_bar, width="stretch")
        else:
            st.info("No channel_manifest.parquet found for this run. Re-generate with the latest efuse-gen.")
