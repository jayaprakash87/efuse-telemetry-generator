"""Protection tab — fault timeline, severity distribution, protection events."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from efuse_datagen.dashboard._shared import FAULT_PALETTE


def render(
    tel: pd.DataFrame,
    feat: pd.DataFrame,
    lab: pd.DataFrame,
    selected_channels: list[str],
    label_map: dict[str, str],
    **kw,
) -> None:
    st.header("Fault & Protection Analysis")

    # ── Fault timeline (Gantt) ── ─────────────────────────────────────
    col_l, col_r = st.columns([2, 1])

    with col_l:
        st.subheader("Fault Timeline")
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
                            Channel=label_map.get(ch, ch),
                            FaultType=fault_type.replace("_", " ").title(),
                            Start=start, Finish=prev,
                        ))
                        start = t
                    prev = t
                fault_rows.append(dict(
                    Channel=label_map.get(ch, ch),
                    FaultType=fault_type.replace("_", " ").title(),
                    Start=start, Finish=prev,
                ))

        if fault_rows:
            gantt_df = pd.DataFrame(fault_rows)
            fig_gantt = px.timeline(
                gantt_df,
                x_start="Start", x_end="Finish", y="Channel", color="FaultType",
                labels={"FaultType": "Fault Type"},
            )
            fig_gantt.update_layout(height=max(300, len(ch_order) * 60 + 80), margin=dict(t=10, b=10))
            st.plotly_chart(fig_gantt, use_container_width=True)
        else:
            st.info("No fault windows for selected channels.")

    with col_r:
        st.subheader("Severity Distribution")
        sev_data = lab[(lab["channel_id"].isin(selected_channels)) & (lab["fault_type"] != "none")]
        if not sev_data.empty:
            hist = px.histogram(
                sev_data, x="severity", color="fault_type",
                color_discrete_map=FAULT_PALETTE, nbins=20,
                labels={"severity": "Severity Score"},
            )
            hist.update_layout(showlegend=False, margin=dict(t=10, b=10))
            st.plotly_chart(hist, use_container_width=True)
        else:
            st.info("No fault data.")

    # ── Fault table ──────────────────────────────────────────────────
    st.subheader("Fault Window Table")
    fault_table = (
        lab[
            (lab["channel_id"].isin(selected_channels)) & (lab["fault_type"] != "none")
        ]
        .sort_values(["channel_id", "timestamp"])
        .assign(timestamp=lambda d: d["timestamp"].dt.strftime("%H:%M:%S.%f").str[:-3])
        [["timestamp", "channel_id", "fault_type", "severity", "description"]]
        .rename(columns={
            "timestamp": "Time", "channel_id": "Channel",
            "fault_type": "Fault Type", "severity": "Severity",
            "description": "Description",
        })
    )
    st.dataframe(fault_table, use_container_width=True, hide_index=True)

    # ── Protection events ────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Protection Events by Type")

    col_l2, col_r2 = st.columns(2)

    with col_l2:
        if "protection_event_rate" in feat.columns:
            ch_data = feat[feat["channel_id"].isin(selected_channels)].sort_values("timestamp")
            fig_prot = px.line(
                ch_data, x="timestamp", y="protection_event_rate", color="channel_id",
                labels={"protection_event_rate": "Event Rate", "channel_id": "Channel"},
            )
            fig_prot.update_layout(height=300, margin=dict(t=10, b=10))
            st.plotly_chart(fig_prot, use_container_width=True)
        else:
            st.info("`protection_event_rate` not in features.")

    with col_r2:
        _event_vals = ["scp", "i2t", "latch_off", "thermal_shutdown", "open_load_diag", "over_voltage"]
        event_rows = []
        for _ch in selected_channels:
            _ch_tel = tel[tel["channel_id"] == _ch].sort_values("timestamp")
            for _ev in _event_vals:
                _is_active = (_ch_tel["protection_event"] == _ev).astype(int)
                _edges = int(_is_active.diff().clip(lower=0).sum())
                if _edges > 0:
                    event_rows.append({
                        "channel_id": label_map.get(_ch, _ch),
                        "Event Type": _ev.upper().replace("_", " "),
                        "Count": _edges,
                    })
        if event_rows:
            _totals_df = pd.DataFrame(event_rows)
            bar_prot = px.bar(
                _totals_df, x="channel_id", y="Count", color="Event Type",
                barmode="group", labels={"channel_id": "Channel"},
            )
            bar_prot.update_layout(height=300, margin=dict(t=10, b=10))
            st.plotly_chart(bar_prot, use_container_width=True)
        else:
            st.info("No protection events for selected channels.")

    # ── Heatmap ──────────────────────────────────────────────────────
    if event_rows and len(selected_channels) > 1:
        st.subheader("Protection Event Heatmap")
        _heat_df = (
            pd.DataFrame(event_rows)
            .pivot_table(index="channel_id", columns="Event Type", values="Count", fill_value=0)
        )
        fig_heat = px.imshow(
            _heat_df, text_auto=True, color_continuous_scale="Reds",
            labels={"x": "Event Type", "y": "Channel", "color": "Count"},
            aspect="auto",
        )
        fig_heat.update_layout(height=300, margin=dict(t=10, b=10))
        st.plotly_chart(fig_heat, use_container_width=True)
