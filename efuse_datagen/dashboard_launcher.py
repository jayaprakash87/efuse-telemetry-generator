"""Console launcher for the packaged Streamlit dashboard."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> None:
    """Launch the packaged dashboard via Streamlit."""
    parser = argparse.ArgumentParser(description="Launch the eFuse Telemetry Generator dashboard.")
    parser.add_argument(
        "--output-root",
        default=None,
        help="Directory containing run outputs. Defaults to ./output in the current working directory.",
    )
    args = parser.parse_args()

    if args.output_root:
        output_root = str(Path(args.output_root).expanduser())
        os.environ["EFUSE_TELEMETRY_OUTPUT_DIR"] = output_root
        os.environ["VIP_DATA_GENERATOR_OUTPUT_DIR"] = output_root

    try:
        from streamlit.web import bootstrap
    except ImportError as exc:
        raise SystemExit(
            "The dashboard dependencies are not installed. Run: pip install 'efuse-telemetry-generator[dashboard]'"
        ) from exc

    app_path = Path(__file__).with_name("dashboard_app.py")
    bootstrap.run(str(app_path), is_hello=False, args=[], flag_options={})