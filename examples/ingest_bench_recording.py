"""Example: ingest a bench recording CSV into the standard run format.

This script creates a tiny sample CSV to simulate a bench measurement file,
then uses MeasurementAdapter to convert it into the standard telemetry schema
that the dashboard and feature engine expect.

Run:
    python examples/ingest_bench_recording.py

Outputs to output/bench/ingest_demo/:
    telemetry.parquet         schema-conformant telemetry
    data_source.txt           "bench" marker for the dashboard
    mapping.yaml              column mapping used
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from efuse_datagen.ingestion import MeasurementAdapter, save_as_run

# --------------------------------------------------------------------------
# 1. Create a fake bench recording CSV (in real usage, point to your file)
# --------------------------------------------------------------------------
rng = np.random.default_rng(42)
n_samples = 500
timestamps = pd.date_range("2026-01-15 10:00:00", periods=n_samples, freq="100ms")

bench_df = pd.DataFrame({
    "time": timestamps,
    "I_ch01": rng.normal(3.5, 0.2, n_samples),        # current in amps
    "U_bat": rng.normal(13.8, 0.1, n_samples),         # voltage in volts
    "T_junction": rng.normal(45.0, 2.0, n_samples),    # temperature in °C
})

tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
bench_df.to_csv(tmp.name, index=False)
print(f"Sample bench CSV: {tmp.name} ({n_samples} rows)")

# --------------------------------------------------------------------------
# 2. Configure the adapter with a column mapping
# --------------------------------------------------------------------------
adapter = MeasurementAdapter(
    column_map={
        "I_ch01": "current_a",
        "U_bat": "voltage_v",
        "T_junction": "temperature_c",
    },
    time_column="time",
)

# --------------------------------------------------------------------------
# 3. Load and transform
# --------------------------------------------------------------------------
tel_df = adapter.load(tmp.name, channel_id="ch_001")

print(f"\nIngested telemetry: {len(tel_df):,} rows × {len(tel_df.columns)} columns")
print(f"Columns: {list(tel_df.columns)}")
print(f"Time range: {tel_df['timestamp'].min()} → {tel_df['timestamp'].max()}")

# --------------------------------------------------------------------------
# 4. Save as a standard run (ready for the dashboard)
# --------------------------------------------------------------------------
out_dir = Path("output") / "bench" / "ingest_demo"
save_as_run(
    tel_df,
    output_dir=out_dir,
    data_source="bench",
)

print(f"\nRun saved to: {out_dir.resolve()}/")
print("Files:")
for f in sorted(out_dir.iterdir()):
    print(f"  {f.name}")

# --------------------------------------------------------------------------
# 5. Verify round-trip
# --------------------------------------------------------------------------
reloaded = pd.read_parquet(out_dir / "telemetry.parquet")
print(f"\nRound-trip check: {len(reloaded):,} rows, "
      f"channels={sorted(reloaded['channel_id'].unique().tolist())}")
