"""Overview tab — run summary metrics, drive cycle timeline, fault distribution.

Also contains ``render_fleet()`` for the fleet-level overview tab.
"""

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
    fleet_mode = kw.get("fleet_mode", False)
    selected_vehicle = kw.get("selected_vehicle")
    if fleet_mode and selected_vehicle:
        st.header(f"Vehicle Overview — {selected_vehicle}")
    else:
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


# ---------------------------------------------------------------------------
# Fleet overview
# ---------------------------------------------------------------------------


def render_fleet(
    fleet_manifest: pd.DataFrame | None,
    fleet_weather: dict | None,
    selected_run: str,
    selected_vehicle: str | None = None,
    **kw,
) -> None:
    """Fleet-level overview: manifest, archetype breakdown, regional weather."""
    if fleet_manifest is None:
        st.warning("No fleet manifest found.")
        return

    st.header("Fleet Overview")

    mf = fleet_manifest
    ok = mf[mf["status"] == "ok"]
    failed = mf[mf["status"] != "ok"]

    # KPI row
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Vehicles", f"{len(ok)}/{len(mf)}")
    col2.metric("Total Rows", f"{ok['n_telemetry_rows'].sum():,.0f}")
    col3.metric("Driving Hours", f"{ok['driving_hours'].sum():,.1f}")
    col4.metric("Fault Labels", f"{ok['n_fault_labels'].sum():,.0f}")
    col5.metric("Drive Cycles", f"{ok['n_drive_cycles'].sum():,.0f}")
    col6.metric("Archetypes", len(mf["archetype_id"].unique()))

    if not failed.empty:
        st.error(f"{len(failed)} vehicle(s) failed: {', '.join(failed['vehicle_id'].tolist())}")

    # Manifest table
    st.subheader("Vehicle Manifest")
    display_cols = [
        "vehicle_id", "archetype_id", "region", "profile",
        "age_months", "status", "n_telemetry_rows",
        "n_fault_labels", "n_drive_cycles", "driving_hours",
    ]
    _disp = mf[[c for c in display_cols if c in mf.columns]].copy()
    _disp.columns = [c.replace("_", " ").title() for c in _disp.columns]
    st.dataframe(
        _disp,
        use_container_width=True,
        hide_index=True,
        column_config={
            "N Telemetry Rows": st.column_config.NumberColumn(format="%d"),
            "Driving Hours": st.column_config.NumberColumn(format="%.1f"),
        },
    )

    # Charts row
    col_l, col_m, col_r = st.columns(3)

    with col_l:
        st.subheader("Archetype Distribution")
        arch_counts = ok["archetype_id"].value_counts()
        fig_arch = px.pie(
            names=arch_counts.index,
            values=arch_counts.values,
            hole=0.35,
        )
        fig_arch.update_layout(margin=dict(t=10, b=10), height=280)
        st.plotly_chart(fig_arch, use_container_width=True)

    with col_m:
        st.subheader("Region Distribution")
        region_counts = ok["region"].value_counts()
        fig_reg = px.pie(
            names=region_counts.index,
            values=region_counts.values,
            hole=0.35,
        )
        fig_reg.update_layout(margin=dict(t=10, b=10), height=280)
        st.plotly_chart(fig_reg, use_container_width=True)

    with col_r:
        st.subheader("Driving Hours by Vehicle")
        fig_hours = px.bar(
            ok.sort_values("vehicle_id"),
            x="vehicle_id", y="driving_hours",
            color="archetype_id",
            labels={"vehicle_id": "Vehicle", "driving_hours": "Hours", "archetype_id": "Archetype"},
        )
        fig_hours.update_layout(margin=dict(t=10, b=10), height=280, showlegend=True)
        st.plotly_chart(fig_hours, use_container_width=True)

    # Telemetry rows per vehicle
    st.subheader("Telemetry Volume by Vehicle")
    fig_rows = px.bar(
        ok.sort_values("vehicle_id"),
        x="vehicle_id", y="n_telemetry_rows",
        color="region",
        labels={"vehicle_id": "Vehicle", "n_telemetry_rows": "Rows", "region": "Region"},
    )
    fig_rows.update_layout(margin=dict(t=10, b=10), height=280)
    st.plotly_chart(fig_rows, use_container_width=True)

    # Regional weather
    if fleet_weather:
        st.subheader("Regional Weather Timelines")
        weather_frames = []
        for region_name, wdf in fleet_weather.items():
            wdf = wdf.copy()
            wdf["region"] = region_name
            weather_frames.append(wdf)
        if weather_frames:
            all_weather = pd.concat(weather_frames, ignore_index=True)

            col_wl, col_wr = st.columns(2)
            with col_wl:
                fig_temp = px.line(
                    all_weather, x="day_index", y="ambient_temp_c", color="region",
                    labels={"day_index": "Day", "ambient_temp_c": "Ambient Temp (°C)", "region": "Region"},
                )
                fig_temp.update_layout(margin=dict(t=10, b=10), height=250)
                st.plotly_chart(fig_temp, use_container_width=True)

            with col_wr:
                fig_volt = px.line(
                    all_weather, x="day_index", y="supply_voltage_v", color="region",
                    labels={"day_index": "Day", "supply_voltage_v": "Supply Voltage (V)", "region": "Region"},
                )
                fig_volt.update_layout(margin=dict(t=10, b=10), height=250)
                st.plotly_chart(fig_volt, use_container_width=True)

    # Fleet config
    cfg_path = Path(selected_run) / "fleet_config.yaml"
    if cfg_path.exists():
        with st.expander("Fleet Config YAML"):
            st.code(cfg_path.read_text(), language="yaml")
