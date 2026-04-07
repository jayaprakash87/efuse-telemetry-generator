"""Signals tab — per-channel I / V / T time series with fault shading."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from efuse_datagen.dashboard._shared import FAULT_PALETTE, build_fault_shapes


def render(
    tel: pd.DataFrame,
    feat: pd.DataFrame,
    lab: pd.DataFrame,
    manifest: pd.DataFrame | None,
    selected_channels: list[str],
    label_map: dict[str, str],
    **kw,
) -> None:
    st.header("Raw Signal Time Series")

    for ch in selected_channels:
        ch_label = label_map.get(ch, ch)
        st.markdown(f"#### `{ch_label}`")

        ch_tel = tel[tel["channel_id"] == ch].sort_values("timestamp")
        ch_lab = lab[lab["channel_id"] == ch]

        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=["Current (A)", "Voltage (V)", "Temperature (°C)"],
        )

        # Current
        fig.add_trace(
            go.Scatter(
                x=ch_tel["timestamp"], y=ch_tel["current_a"],
                name="I", line=dict(color="#ef4444", width=1), showlegend=False,
            ),
            row=1, col=1,
        )
        # Voltage
        fig.add_trace(
            go.Scatter(
                x=ch_tel["timestamp"], y=ch_tel["voltage_v"],
                name="V", line=dict(color="#3b82f6", width=1), showlegend=False,
            ),
            row=2, col=1,
        )
        # Temperature
        fig.add_trace(
            go.Scatter(
                x=ch_tel["timestamp"], y=ch_tel["temperature_c"],
                name="T", line=dict(color="#f97316", width=1), showlegend=False,
            ),
            row=3, col=1,
        )

        # Trip markers
        trips = ch_tel[ch_tel["trip_flag"]]
        if not trips.empty:
            for row_idx, col_name in enumerate(["current_a", "voltage_v", "temperature_c"], start=1):
                fig.add_trace(
                    go.Scatter(
                        x=trips["timestamp"], y=trips[col_name],
                        mode="markers",
                        marker=dict(size=6, color="#dc2626", symbol="x"),
                        name="Trip" if row_idx == 1 else None,
                        showlegend=(row_idx == 1),
                    ),
                    row=row_idx, col=1,
                )

        # Fault legend entries
        fault_types = ch_lab[ch_lab["fault_type"] != "none"]["fault_type"].unique()
        for ft in fault_types:
            c = FAULT_PALETTE.get(ft, "#999999")
            fig.add_trace(
                go.Scatter(
                    x=[None], y=[None], mode="markers",
                    marker=dict(size=10, color=c, symbol="square"),
                    name=ft.replace("_", " ").title(), showlegend=True,
                ),
                row=1, col=1,
            )

        # Fault shading
        i_min, i_max = float(ch_tel["current_a"].min()), float(ch_tel["current_a"].max())
        v_min, v_max = float(ch_tel["voltage_v"].min()), float(ch_tel["voltage_v"].max())
        t_min, t_max = float(ch_tel["temperature_c"].min()), float(ch_tel["temperature_c"].max())
        shapes = build_fault_shapes(ch_lab, [(i_min, i_max), (v_min, v_max), (t_min, t_max)])

        # Power-off shading
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
                            type="rect", xref="x",
                            yref=f"y{row_idx if row_idx > 1 else ''}",
                            x0=start, x1=prev, y0=y0, y1=y1,
                            fillcolor="rgba(100,100,100,0.12)",
                            line=dict(width=0), layer="below",
                        ))
                    start = t
                prev = t
            for row_idx, (y0, y1) in enumerate(_ranges, start=1):
                shapes.append(dict(
                    type="rect", xref="x",
                    yref=f"y{row_idx if row_idx > 1 else ''}",
                    x0=start, x1=prev, y0=y0, y1=y1,
                    fillcolor="rgba(100,100,100,0.12)",
                    line=dict(width=0), layer="below",
                ))
            fig.add_trace(
                go.Scatter(
                    x=[None], y=[None], mode="markers",
                    marker=dict(size=10, color="rgba(100,100,100,0.3)", symbol="square"),
                    name="Channel off", showlegend=True,
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

        st.plotly_chart(fig, use_container_width=True)
        st.markdown("---")
