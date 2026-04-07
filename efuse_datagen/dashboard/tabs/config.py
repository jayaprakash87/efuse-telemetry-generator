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
        st.markdown(f"**Run ID:** `{run_name}`")
        st.markdown(f"**Samples:** {len(tel):,}")
        st.markdown(f"**Channels:** {len(channels)}")
        duration_s = (tel["timestamp"].max() - tel["timestamp"].min()).total_seconds()
        st.markdown(f"**Duration:** {duration_s:.0f} s")

        config_path = Path(selected_run) / "config.yaml"
        if config_path.exists():
            st.subheader("Config YAML")
            _yaml_text = config_path.read_text()
            st.code(_yaml_text, language="yaml")

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
            st.dataframe(_inv, use_container_width=True, hide_index=True)

            st.subheader("Zone Distribution")
            _zone_counts = manifest.groupby("zone_id").size().reset_index(name="Channels")
            _zone_bar = px.bar(
                _zone_counts, x="zone_id", y="Channels",
                labels={"zone_id": "Zone"}, color="zone_id",
            )
            _zone_bar.update_layout(showlegend=False, height=250, margin=dict(t=10, b=10))
            st.plotly_chart(_zone_bar, use_container_width=True)
        else:
            st.info("No channel_manifest.parquet found. Re-generate with the latest efuse-gen.")
