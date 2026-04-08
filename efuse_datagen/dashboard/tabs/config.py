"""Config tab — scenario config, channel inventory, zone distribution."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


def render(
    tel: pd.DataFrame,
    manifest: pd.DataFrame | None,
    channels: list[str],
    selected_run: str,
    **kw,
) -> None:
    st.header("Scenario Config & Channel Inventory")

    col_l, col_r = st.columns([1, 2])

    with col_l:
        st.subheader("Run Info")
        run_name = Path(selected_run).name
        fleet_mode = kw.get("fleet_mode", False)
        selected_vehicle = kw.get("selected_vehicle")

        if fleet_mode and selected_vehicle:
            st.markdown(f"**Fleet Run:** `{run_name}`")
            st.markdown(f"**Vehicle:** `{selected_vehicle}`")
        else:
            st.markdown(f"**Run ID:** `{run_name}`")
        st.markdown(f"**Samples:** {len(tel):,}")
        st.markdown(f"**Channels:** {len(channels)}")
        duration_s = (tel["timestamp"].max() - tel["timestamp"].min()).total_seconds()
        st.markdown(f"**Duration:** {duration_s:.0f} s")

        # Show config YAML — check per-vehicle path first for fleet, then fleet_config, then config
        config_path = None
        if fleet_mode and selected_vehicle:
            _v_cfg = Path(selected_run) / "vehicles" / selected_vehicle / "config.yaml"
            if _v_cfg.exists():
                config_path = _v_cfg
        if config_path is None:
            for name in ("fleet_config.yaml", "config.yaml"):
                _candidate = Path(selected_run) / name
                if _candidate.exists():
                    config_path = _candidate
                    break
        if config_path is not None:
            st.subheader("Config YAML")
            st.code(config_path.read_text(), language="yaml")

    with col_r:
        st.subheader("Channel Inventory")
        if manifest is not None:
            display_cols = [
                "channel_id", "zone_id", "load_name", "system_cluster",
                "efuse_family", "load_type", "power_class",
                "nominal_current_a", "duty_cycle",
            ]
            _inv = manifest[[c for c in display_cols if c in manifest.columns]].copy()
            _inv.columns = [c.replace("_", " ").title() for c in _inv.columns]
            st.dataframe(_inv, width="stretch", hide_index=True)

            st.subheader("Zone Distribution")
            _zone_counts = manifest.groupby("zone_id").size().reset_index(name="Channels")
            _zone_bar = px.bar(
                _zone_counts, x="zone_id", y="Channels",
                labels={"zone_id": "Zone"}, color="zone_id",
            )
            _zone_bar.update_layout(showlegend=False, height=250, margin=dict(t=10, b=10))
            st.plotly_chart(_zone_bar, width="stretch")
        else:
            st.info("No channel_manifest.parquet found. Re-generate with the latest efuse-gen.")
