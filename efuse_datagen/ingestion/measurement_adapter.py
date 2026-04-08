"""Measurement data ingestion adapter.

Converts bench / HIL / production CAN/MDF/CSV recordings into the
standard eFuse telemetry schema so the entire analysis pipeline,
feature engine, and dashboard work identically on real data.

Supported input formats:
  - CSV / TSV  (.csv, .tsv)
  - Parquet    (.parquet)
  - MDF / MF4  (.mdf, .mf4)  — requires ``asammdf`` package
  - BLF / ASC  (.blf, .asc)  — requires ``python-can`` + ``cantools``

Usage::

    from efuse_datagen.ingestion import MeasurementAdapter

    adapter = MeasurementAdapter(column_map={
        "I_ch01": "current_a",
        "U_bat": "voltage_v",
        "T_junction": "temperature_c",
    })
    tel_df = adapter.load("bench_recording.csv", channel_id="ch_001")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)

# ── Standard telemetry columns (the contract) ────────────────────────────
REQUIRED_COLUMNS = ["timestamp", "channel_id", "current_a", "voltage_v", "temperature_c"]

OPTIONAL_COLUMNS = [
    "state_on_off",
    "trip_flag",
    "overload_flag",
    "protection_event",
    "reset_counter",
    "pwm_duty_pct",
    "device_status",
]

DEFAULTS: dict[str, Any] = {
    "state_on_off": True,
    "trip_flag": False,
    "overload_flag": False,
    "protection_event": "none",
    "reset_counter": 0,
    "pwm_duty_pct": 100.0,
    "device_status": "ok",
}


class MeasurementAdapter:
    """Load real measurement files and map them to the standard telemetry schema.

    Parameters
    ----------
    column_map : dict[str, str]
        Maps *source column name* → *schema column name*.
        Example: ``{"I_ch01": "current_a", "U_bat": "voltage_v"}``
    time_column : str
        Name of the timestamp column in the source file.  If the column
        contains numeric seconds (relative), the adapter converts to
        ``pd.Timestamp`` starting from ``time_origin``.
    time_origin : str | pd.Timestamp
        Base timestamp when the recording started.  Only used when
        ``time_column`` contains relative seconds.
    default_channel_id : str
        Channel ID assigned when the source has no channel column.
    resample_ms : float | None
        If set, resample the data to this interval after loading.
    """

    def __init__(
        self,
        column_map: dict[str, str] | None = None,
        time_column: str = "timestamp",
        time_origin: str | pd.Timestamp = "2026-01-01",
        default_channel_id: str = "ch_001",
        resample_ms: float | None = None,
    ) -> None:
        self.column_map = column_map or {}
        self.time_column = time_column
        self.time_origin = pd.Timestamp(time_origin)
        self.default_channel_id = default_channel_id
        self.resample_ms = resample_ms

    # ── Public API ────────────────────────────────────────────────────

    def load(
        self,
        path: str | Path,
        channel_id: str | None = None,
        **read_kwargs: Any,
    ) -> pd.DataFrame:
        """Load a single file and return a schema-conformant telemetry DataFrame.

        Parameters
        ----------
        path : str | Path
            Path to the source file.
        channel_id : str | None
            Override for the channel_id column.  Falls back to
            ``default_channel_id`` if the source has no channel column.
        **read_kwargs
            Passed through to the format-specific reader (e.g.
            ``sep=";"`` for CSV).
        """
        path = Path(path)
        suffix = path.suffix.lower()

        if suffix in (".csv", ".tsv"):
            log.debug("Detected format: CSV/TSV (%s)", suffix)
            raw = self._read_csv(path, **read_kwargs)
        elif suffix == ".parquet":
            log.debug("Detected format: Parquet")
            raw = pd.read_parquet(path, **read_kwargs)
        elif suffix in (".mdf", ".mf4"):
            log.debug("Detected format: MDF/MF4 (requires asammdf)")
            raw = self._read_mdf(path, **read_kwargs)
        elif suffix in (".blf", ".asc"):
            log.debug("Detected format: CAN log %s (requires python-can)", suffix)
            raw = self._read_can_log(path, **read_kwargs)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

        df = self._apply_column_map(raw)
        df = self._ensure_timestamp(df)
        df = self._ensure_channel_id(df, channel_id)
        df = self._fill_defaults(df)
        df = self._validate(df)

        if self.resample_ms is not None:
            df = self._resample(df, self.resample_ms)

        log.info(
            "Loaded %s: %d samples, channels=%s",
            path.name, len(df), sorted(df["channel_id"].unique().tolist()),
        )
        return df

    def load_multi_channel(
        self,
        file_channel_pairs: list[tuple[str | Path, str]],
        **read_kwargs: Any,
    ) -> pd.DataFrame:
        """Load multiple files (one per channel) and concatenate.

        Parameters
        ----------
        file_channel_pairs : list of (path, channel_id)
            Each tuple maps a file to a channel identifier.
        """
        frames = []
        for fpath, ch_id in file_channel_pairs:
            df = self.load(fpath, channel_id=ch_id, **read_kwargs)
            frames.append(df)
        combined = pd.concat(frames, ignore_index=True).sort_values("timestamp")
        log.info("Combined %d files → %d total samples", len(file_channel_pairs), len(combined))
        return combined

    def load_directory(
        self,
        directory: str | Path,
        glob_pattern: str = "*.csv",
        channel_id_from_filename: bool = True,
        **read_kwargs: Any,
    ) -> pd.DataFrame:
        """Load all matching files from a directory.

        If ``channel_id_from_filename`` is True, the stem of each file
        is used as the channel_id (e.g. ``ch_001.csv`` → ``ch_001``).
        """
        d = Path(directory)
        files = sorted(d.glob(glob_pattern))
        if not files:
            raise FileNotFoundError(f"No files matching {glob_pattern} in {d}")

        pairs = []
        for f in files:
            ch = f.stem if channel_id_from_filename else self.default_channel_id
            pairs.append((f, ch))
        return self.load_multi_channel(pairs, **read_kwargs)

    # ── Format readers ────────────────────────────────────────────────

    @staticmethod
    def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
        defaults = {"sep": None, "engine": "python"}  # auto-detect separator
        defaults.update(kwargs)
        return pd.read_csv(path, **defaults)

    @staticmethod
    def _read_mdf(path: Path, **kwargs: Any) -> pd.DataFrame:
        try:
            from asammdf import MDF
        except ImportError:
            raise ImportError(
                "Reading MDF/MF4 files requires the 'asammdf' package. "
                "Install it with: pip install asammdf"
            ) from None
        log.debug("Reading MDF file: %s", path.name)
        mdf = MDF(str(path))
        return mdf.to_dataframe(**kwargs)

    @staticmethod
    def _read_can_log(path: Path, **kwargs: Any) -> pd.DataFrame:
        try:
            import can
        except ImportError:
            raise ImportError(
                "Reading BLF/ASC CAN logs requires the 'python-can' package. "
                "Install it with: pip install python-can"
            ) from None

        dbc_path = kwargs.pop("dbc", None)
        db = None
        if dbc_path:
            try:
                import cantools
                db = cantools.database.load_file(str(dbc_path))
            except ImportError:
                raise ImportError(
                    "Decoding CAN signals requires the 'cantools' package. "
                    "Install it with: pip install cantools"
                ) from None

        suffix = path.suffix.lower()
        reader_cls = can.BLFReader if suffix == ".blf" else can.ASCReader
        rows: list[dict] = []

        with reader_cls(str(path)) as reader:
            for msg in reader:
                row: dict[str, Any] = {
                    "timestamp": msg.timestamp,
                    "arbitration_id": msg.arbitration_id,
                }
                if db:
                    try:
                        decoded = db.decode_message(msg.arbitration_id, msg.data)
                        row.update(decoded)
                    except Exception:
                        pass
                rows.append(row)

        return pd.DataFrame(rows) if rows else pd.DataFrame()

    # ── Transformation helpers ────────────────────────────────────────

    def _apply_column_map(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.column_map:
            rename = {src: dst for src, dst in self.column_map.items() if src in df.columns}
            df = df.rename(columns=rename)
        return df

    def _ensure_timestamp(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.time_column != "timestamp" and self.time_column in df.columns:
            df = df.rename(columns={self.time_column: "timestamp"})

        if "timestamp" not in df.columns:
            raise ValueError(
                "No timestamp column found after mapping. Set time_column parameter."
            )

        if pd.api.types.is_numeric_dtype(df["timestamp"]):
            # Relative seconds → absolute timestamps
            df["timestamp"] = self.time_origin + pd.to_timedelta(df["timestamp"], unit="s")
        elif not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Strip timezone if present (match synthetic convention)
        if df["timestamp"].dt.tz is not None:
            df["timestamp"] = df["timestamp"].dt.tz_convert("UTC").dt.tz_localize(None)

        return df

    def _ensure_channel_id(self, df: pd.DataFrame, override: str | None) -> pd.DataFrame:
        if override:
            df["channel_id"] = override
        elif "channel_id" not in df.columns:
            df["channel_id"] = self.default_channel_id
        return df

    @staticmethod
    def _fill_defaults(df: pd.DataFrame) -> pd.DataFrame:
        for col, default in DEFAULTS.items():
            if col not in df.columns:
                df[col] = default
        return df

    @staticmethod
    def _validate(df: pd.DataFrame) -> pd.DataFrame:
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(
                f"Missing required columns after mapping: {missing}. "
                f"Provide a column_map to map your source columns to: {REQUIRED_COLUMNS}"
            )

        n_before = len(df)
        df = df.dropna(subset=["current_a", "voltage_v"])
        n_dropped = n_before - len(df)
        if n_dropped > 0:
            log.warning("Dropped %d rows with NaN current/voltage", n_dropped)

        return df.sort_values("timestamp").reset_index(drop=True)

    @staticmethod
    def _resample(df: pd.DataFrame, interval_ms: float) -> pd.DataFrame:
        interval = pd.Timedelta(milliseconds=interval_ms)
        frames = []
        for ch_id, grp in df.groupby("channel_id"):
            r = (
                grp.set_index("timestamp")
                .resample(interval)
                .last()
                .dropna(subset=["current_a"])
                .reset_index()
            )
            r["channel_id"] = ch_id
            frames.append(r)
        return pd.concat(frames, ignore_index=True).sort_values("timestamp")


# ── Detect data source from a run directory ───────────────────────────────

class DataSource:
    """Metadata tag indicating where data came from."""

    SYNTHETIC = "synthetic"
    BENCH = "bench"
    HIL = "hil"
    PRODUCTION = "production"

    @staticmethod
    def detect(run_dir: str | Path) -> str:
        """Detect data source from metadata files in a run directory.

        Returns one of: 'synthetic', 'bench', 'hil', 'production'.
        """
        p = Path(run_dir)

        marker = p / "data_source.txt"
        if marker.exists():
            return marker.read_text().strip().lower()

        config_yaml = p / "config.yaml"
        if config_yaml.exists():
            import yaml

            try:
                cfg = yaml.safe_load(config_yaml.read_text())
                if isinstance(cfg, dict) and "scenario_id" in cfg and "channels" in cfg:
                    return DataSource.SYNTHETIC
            except Exception:
                pass

        if (p / "mapping.yaml").exists():
            return DataSource.BENCH

        return DataSource.BENCH


def save_as_run(
    telemetry_df: pd.DataFrame,
    output_dir: str | Path,
    labels_df: pd.DataFrame | None = None,
    channel_manifest: pd.DataFrame | None = None,
    data_source: str = DataSource.BENCH,
    metadata: dict | None = None,
) -> Path:
    """Save measurement data in the standard run directory format.

    Creates the same file structure the synthetic generator produces so
    the dashboard and all analysis tools work without modification.

    Parameters
    ----------
    telemetry_df : pd.DataFrame
        Schema-conformant telemetry (from MeasurementAdapter.load()).
    output_dir : str | Path
        Directory to write the run into.
    labels_df : pd.DataFrame | None
        Optional ground-truth fault labels.
    channel_manifest : pd.DataFrame | None
        Optional per-channel metadata.
    data_source : str
        Tag: 'bench', 'hil', or 'production'.
    metadata : dict | None
        Arbitrary metadata to store alongside the run.

    Returns
    -------
    Path
        The run directory path.
    """
    from efuse_datagen.features.engine import FeatureEngine

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    telemetry_df.to_parquet(out / "telemetry.parquet", index=False)

    try:
        engine = FeatureEngine()
        feat_df = engine.compute(telemetry_df)
        feat_df.to_parquet(out / "features.parquet", index=False)
    except Exception as e:
        log.warning("Feature extraction failed: %s — writing empty features", e)
        telemetry_df[[]].to_parquet(out / "features.parquet", index=False)

    if labels_df is not None and not labels_df.empty:
        labels_df.to_parquet(out / "labels.parquet", index=False)
    else:
        pd.DataFrame(
            columns=["timestamp", "channel_id", "fault_type", "severity", "description"]
        ).to_parquet(out / "labels.parquet", index=False)

    if channel_manifest is not None:
        channel_manifest.to_parquet(out / "channel_manifest.parquet", index=False)

    (out / "data_source.txt").write_text(data_source)

    if metadata:
        import json

        (out / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str))

    log.info("Saved %s run to %s (%d samples)", data_source, out, len(telemetry_df))
    return out
