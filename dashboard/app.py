"""eFuse Telemetry Dashboard — vip-data-generator.

Launch:
    streamlit run dashboard/app.py
    streamlit run dashboard/app.py -- --output path/to/run
"""

from __future__ import annotations

import sys
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
    page_title="eFuse Telemetry — VIP",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OUTPUT_ROOT = Path(__file__).parent.parent / "output"

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


def list_runs() -> list[str]:
    if not OUTPUT_ROOT.exists():
        return []
    return sorted(
        [str(d) for d in OUTPUT_ROOT.iterdir() if d.is_dir()],
        reverse=True,
    )


def fault_shapes(
    labels: pd.DataFrame,
    channel: str,
    y_range: tuple[float, float] = (0, 1),
    show_in_legend_for: set | None = None,
) -> list[dict]:
    """Return Plotly shape + annotation dicts for fault windows on a channel."""
    ch_lab = labels[labels["channel_id"] == channel]
    shapes = []
    if show_in_legend_for is None:
        show_in_legend_for = set()

    for fault_type in ch_lab["fault_type"].unique():
        if fault_type == "none":
            continue
        color = FAULT_PALETTE.get(fault_type, "#999999")
        fill = color.replace(")", ", 0.18)").replace("rgb(", "rgba(") if color.startswith("rgb") else (
            color + "30" if color.startswith("#") else color
        )
        windows = ch_lab[ch_lab["fault_type"] == fault_type]
        # Merge consecutive timestamps into contiguous windows
        ts = windows["timestamp"].sort_values()
        gap = pd.Timedelta("500ms")
        start = ts.iloc[0]
        prev = ts.iloc[0]
        for t in ts.iloc[1:]:
            if t - prev > gap:
                shapes.append({
                    "type": "rect",
                    "x0": str(start), "x1": str(prev),
                    "y0": y_range[0], "y1": y_range[1],
                    "fillcolor": fill,
                    "line": {"width": 0},
                    "layer": "below",
                    "label": fault_type if fault_type not in show_in_legend_for else None,
                })
                show_in_legend_for.add(fault_type)
                start = t
            prev = t
        shapes.append({
            "type": "rect",
            "x0": str(start), "x1": str(prev),
            "y0": y_range[0], "y1": y_range[1],
            "fillcolor": fill,
            "line": {"width": 0},
            "layer": "below",
        })
    return shapes


# ---------------------------------------------------------------------------
# Sidebar — run + channel selector
# ---------------------------------------------------------------------------

st.sidebar.title("⚡ eFuse VIP Dashboard")
st.sidebar.markdown("---")

runs = list_runs()
if not runs:
    st.error(
        "No output runs found. Run `vip-gen` first to generate data.\n\n"
        "```\nvip-gen --duration 120\n```"
    )
    st.stop()

selected_run = st.sidebar.selectbox("Output run", runs, index=0, format_func=lambda p: Path(p).name)
tel, feat, lab = load_run(selected_run)

channels = sorted(tel["channel_id"].unique().tolist())
selected_channels = st.sidebar.multiselect("Channels", channels, default=channels[:4])
if not selected_channels:
    st.warning("Select at least one channel.")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.caption(f"Run: `{Path(selected_run).name}`")
st.sidebar.caption(f"Samples: {len(tel):,} | Channels: {len(channels)}")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_overview, tab_telemetry, tab_features, tab_faults, tab_protection = st.tabs([
    "📊 Overview",
    "📡 Telemetry",
    "🔬 Features",
    "⚠️ Fault Analysis",
    "🛡️ Protection Events",
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

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Duration", f"{duration_s:.0f} s")
    col2.metric("Channels", len(channels))
    col3.metric("Total Samples", f"{len(tel):,}")
    col4.metric("Fault Windows", f"{total_faults:,}")
    col5.metric("Trip Events", f"{int(trip_events):,}")

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
    st.caption("Fault injection windows shown as shaded regions.")

    for ch in selected_channels:
        st.markdown(f"#### Channel: `{ch}`")
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
        "anomaly_score",
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
            st.markdown(f"#### Channel: `{ch}`")
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
        st.subheader("Cumulative Protection Events by Type")
        count_cols = [c for c in avail_prot if c.endswith("_count")]
        if count_cols:
            ch_prot = feat[feat["channel_id"].isin(selected_channels)]
            totals = (
                ch_prot.groupby("channel_id")[count_cols]
                .max()
                .reset_index()
                .melt(id_vars="channel_id", var_name="Event Type", value_name="Count")
            )
            totals["Event Type"] = totals["Event Type"].str.replace("_count", "").str.replace("_", " ").str.upper()
            bar_prot = px.bar(
                totals,
                x="channel_id",
                y="Count",
                color="Event Type",
                barmode="group",
                labels={"channel_id": "Channel"},
            )
            bar_prot.update_layout(height=300, margin=dict(t=10, b=10))
            st.plotly_chart(bar_prot, width="stretch")
        else:
            st.info("No protection event count columns found.")

    st.subheader("Protection Event Heatmap")
    if count_cols and len(selected_channels) > 1:
        ch_prot = feat[feat["channel_id"].isin(selected_channels)]
        heat_df = (
            ch_prot.groupby("channel_id")[count_cols]
            .max()
            .rename(columns=lambda c: c.replace("_count", "").upper())
        )
        fig_heat = px.imshow(
            heat_df,
            text_auto=True,
            color_continuous_scale="Reds",
            labels={"x": "Event Type", "y": "Channel", "color": "Count"},
            aspect="auto",
        )
        fig_heat.update_layout(height=300, margin=dict(t=10, b=10))
        st.plotly_chart(fig_heat, width="stretch")
    else:
        if len(selected_channels) == 1:
            st.info("Select multiple channels to see the heatmap.")
