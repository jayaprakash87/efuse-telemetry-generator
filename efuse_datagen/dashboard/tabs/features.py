"""Features tab — derived feature time series with fault shading."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from efuse_datagen.dashboard._shared import FAULT_PALETTE, build_fault_shapes


def render(
    tel: pd.DataFrame,
    feat: pd.DataFrame,
    lab: pd.DataFrame,
    selected_channels: list[str],
    label_map: dict[str, str],
    **kw,
) -> None:
    st.header("Derived Feature Time Series")

    if feat.empty:
        st.info("No feature data available for this run.")
        return

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
        default=[f for f in ["rolling_rms_current", "spike_score", "temperature_slope", "trip_frequency"] if f in available],
    )

    if not selected_features:
        st.info("Select at least one feature.")
        return

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

        # Fault shading — per subplot y range
        y_ranges = []
        for f_name in selected_features:
            if f_name in ch_feat.columns and not ch_feat[f_name].dropna().empty:
                y_ranges.append((float(ch_feat[f_name].min()), float(ch_feat[f_name].max())))
            else:
                y_ranges.append((0, 1))
        shapes = build_fault_shapes(ch_lab, y_ranges)

        fig.update_layout(
            shapes=shapes,
            height=200 * n,
            margin=dict(t=40, b=20, l=70, r=20),
        )
        st.plotly_chart(fig, width="stretch")
        st.markdown("---")
