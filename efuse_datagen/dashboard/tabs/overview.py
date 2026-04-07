"""Overview tab — run summary metrics, drive cycle timeline, fault distribution."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


def render(
    tel: pd.DataFrame,
    feat: pd.DataFrame,
    lab: pd.DataFrame,
    manifest: pd.DataFrame | None,
    dc_df: pd.DataFrame | None,
    selected_channels: list[str],
    channels: list[str],
    selected_run: str,
    label_map: dict[str, str],
    is_multi_cycle: bool,
    **kw,
) -> None:
    st.header("Run Overview")

    duration_s = (tel["timestamp"].max() - tel["timestamp"].min()).total_seconds()
    total_faults = (lab["fault_type"] != "none").sum()
    trip_events = tel["trip_flag"].sum()

    if is_multi_cycle and dc_df is not None:
        _cycle_ids = set(tel["drive_cycle_id"].unique()) if "drive_cycle_id" in tel.columns else set()
        _dc_sel = dc_df[dc_df["cycle_id"].isin(_cycle_ids)] if _cycle_ids else dc_df
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
        col4.metric("Fault Labels", f"{total_faults:,}")
        col5.metric("Trip Events", f"{int(trip_events):,}")

    # Drive-cycle timeline for multi-cycle runs
    if is_multi_cycle and dc_df is not None:
        st.subheader("Drive Cycle Timeline")
        _cycle_ids = set(tel["drive_cycle_id"].unique()) if "drive_cycle_id" in tel.columns else set()
        _dc_sel = dc_df[dc_df["cycle_id"].isin(_cycle_ids)] if _cycle_ids else dc_df
        if not _dc_sel.empty:
            fig_dc = px.timeline(
                _dc_sel,
                x_start="start_time",
                x_end="end_time",
                y="day",
                color="profile",
                hover_data=["duration_s", "cycle_id"],
                labels={"day": "Day"},
            )
            fig_dc.update_layout(height=250, margin=dict(t=10, b=10))
            st.plotly_chart(fig_dc, use_container_width=True)

    # Fault distribution
    st.subheader("Fault Distribution")
    col_l, col_r = st.columns(2)

    with col_l:
        fault_counts = lab[lab["fault_type"] != "none"]["fault_type"].value_counts()
        if not fault_counts.empty:
            from efuse_datagen.dashboard._shared import FAULT_PALETTE

            fig_pie = px.pie(
                names=fault_counts.index,
                values=fault_counts.values,
                color=fault_counts.index,
                color_discrete_map=FAULT_PALETTE,
            )
            fig_pie.update_layout(margin=dict(t=10, b=10))
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No fault windows in this run.")

    with col_r:
        st.markdown("**Channel Summary**")
        rows = []
        for ch in selected_channels:
            ch_tel = tel[tel["channel_id"] == ch]
            ch_lab = lab[lab["channel_id"] == ch]
            rows.append({
                "Channel": label_map.get(ch, ch),
                "Samples": len(ch_tel),
                "Trips": int(ch_tel["trip_flag"].sum()),
                "Fault Labels": int((ch_lab["fault_type"] != "none").sum()),
                "Fault Types": ", ".join(
                    ch_lab[ch_lab["fault_type"] != "none"]["fault_type"].unique()
                ) or "—",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
