"""Quickstart example for the end-to-end generation pipeline.

Run:
        python examples/quickstart.py

Outputs to output/quickstart/:
    telemetry.parquet         raw eFuse signals
    features.parquet          rolling derived features
    labels.parquet            ground-truth fault windows
    channel_manifest.parquet  per-channel metadata
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from vip_datagen.config.builtin import load_bundled_config
from vip_datagen.config.models import StorageConfig
from vip_datagen.features.engine import FeatureEngine
from vip_datagen.simulation.generator import TelemetryGenerator
from vip_datagen.storage.writer import StorageWriter

# --------------------------------------------------------------------------
# 1. Load a scenario (or use the programmatic API)
# --------------------------------------------------------------------------
platform = load_bundled_config("default")
sim_cfg = platform.simulation
feat_cfg = platform.features

print(f"Scenario : {sim_cfg.name}")
print(f"Channels : {len(sim_cfg.channels)}")
print(f"Duration : {sim_cfg.duration_s}s  ({sim_cfg.duration_s / 3600:.2f}h)")

# --------------------------------------------------------------------------
# 2. Generate raw telemetry
# --------------------------------------------------------------------------
gen = TelemetryGenerator(sim_cfg)
telem_df, labels_df = gen.generate()

print(f"\nTelemetry: {len(telem_df):,} rows × {len(telem_df.columns)} columns")
print(f"Labels   : {len(labels_df):,} fault-window rows")
print(f"Columns  : {list(telem_df.columns)}")

# --------------------------------------------------------------------------
# 3. Compute rolling features
# --------------------------------------------------------------------------
engine = FeatureEngine(feat_cfg)
features_df = engine.compute(telem_df)

print(f"\nFeatures : {len(features_df):,} rows × {len(features_df.columns)} columns")
print(f"Feature columns: {[c for c in features_df.columns if c not in telem_df.columns]}")

# --------------------------------------------------------------------------
# 4. Save to disk
# --------------------------------------------------------------------------
out_dir = Path("output") / "quickstart"
writer = StorageWriter(StorageConfig(output_dir=str(out_dir), format="parquet"))
writer.write_telemetry(telem_df)
writer.write_features(features_df)
if not labels_df.empty:
    writer.write_labels(labels_df)
writer.write_channel_manifest(sim_cfg.channels)

print(f"\nFiles saved to: {out_dir.resolve()}/")

# --------------------------------------------------------------------------
# 5. Quick sanity check
# --------------------------------------------------------------------------
t = pd.read_parquet(out_dir / "telemetry.parquet")
print(f"\nSanity check — loaded {len(t):,} rows from parquet, "
      f"{t['channel_id'].nunique()} channels, "
    f"{int(t['trip_flag'].sum())} trip samples")
