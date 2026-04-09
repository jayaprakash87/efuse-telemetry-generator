"""Import / export vehicle topologies from CSV, Excel, or Parquet.

Typical workflow for an automotive engineer:

    1. Fill in a spreadsheet with one row per eFuse channel
    2. Export to CSV or keep as .xlsx
    3. Run:  efuse-gen topology import channels.xlsx -o my_vehicle.yaml
    4. Reference from any scenario config:
         simulation:
           topology_file: ./my_vehicle.yaml
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Column header aliases — engineers use inconsistent naming
# ---------------------------------------------------------------------------

_HEADER_ALIASES: dict[str, list[str]] = {
    # required
    "channel_id": ["channel_id", "ch_id", "channel", "ch", "id", "efuse_channel"],
    "zone_id": ["zone_id", "zone", "zc", "zone_controller", "zc_id"],
    "efuse_family": [
        "efuse_family", "efuse", "ic_family", "ic", "ic_type", "part_number",
        "part", "component", "efuse_ic",
    ],
    "load_name": ["load_name", "load", "consumer", "load_label", "function"],
    # zone metadata (auto-detected from zone_* columns)
    "zone_name": ["zone_name", "zc_name", "zone_label"],
    "zone_location": ["zone_location", "zc_location", "location"],
    "zone_bus": ["zone_bus", "bus_interface", "bus", "protocol", "zc_bus"],
    # common optional
    "load_type": ["load_type", "type"],
    "connected_loads": ["connected_loads", "connected", "loads", "systems"],
    "system_cluster": ["system_cluster", "cluster", "domain"],
    "system_name": ["system_name", "subsystem", "system"],
    "driver_type": ["driver_type", "driver", "side"],
    "power_class": ["power_class", "kl", "kl_class", "power"],
    "pwm_capable": ["pwm_capable", "pwm"],
    "wire_gauge_mm2": ["wire_gauge_mm2", "wire_gauge", "gauge_mm2", "awg"],
    "run_length_m": ["run_length_m", "run_length", "length_m", "cable_length"],
    "harness_r_ohm": ["harness_r_ohm", "harness_r", "wire_r"],
    "connector_r_ohm": ["connector_r_ohm", "connector_r", "contact_r"],
    "t_ambient_c": ["t_ambient_c", "t_ambient", "ambient_temp", "temp_c"],
    "die_id": ["die_id", "die", "package", "thermal_group"],
    "duty_cycle": ["duty_cycle", "duty"],
    "on_duration_s": ["on_duration_s", "on_time_s", "on_duration"],
    "off_duration_s": ["off_duration_s", "off_time_s", "off_duration"],
    "inrush_factor": ["inrush_factor", "inrush"],
    "inrush_duration_ms": ["inrush_duration_ms", "inrush_ms", "inrush_duration"],
    "safety_level": ["safety_level", "asil", "safety"],
    "nominal_current_a": ["nominal_current_a", "nominal_current", "i_nom", "i_nominal"],
    "max_current_a": ["max_current_a", "max_current", "i_max"],
}

# Channel spec fields that we pass through to YAML (excluding zone metadata)
_ZONE_META_KEYS = {"zone_name", "zone_location", "zone_bus"}

# Fields that should be numeric
_NUMERIC_FIELDS = {
    "wire_gauge_mm2", "run_length_m", "harness_r_ohm", "connector_r_ohm",
    "t_ambient_c", "duty_cycle", "on_duration_s", "off_duration_s",
    "inrush_factor", "inrush_duration_ms", "nominal_current_a", "max_current_a",
}

# Fields that should be boolean
_BOOL_FIELDS = {"pwm_capable"}

# Minimal columns for the --minimal template
_MINIMAL_HEADERS = ["channel_id", "zone_id", "efuse_family", "load_name", "load_type", "zone_name"]


def _get_known_families() -> set[str]:
    """Return the set of valid efuse_family string values from the catalog."""
    from efuse_datagen.schemas.telemetry import EFuseFamily
    return {m.value for m in EFuseFamily}


def _warn_unknown_families(channel_specs: list[dict[str, Any]]) -> list[str]:
    """Emit warnings for channel_specs with unrecognised efuse_family values.

    Returns the list of unknown family strings (useful for tests).
    """
    known = _get_known_families()
    unknown: list[str] = []
    for spec in channel_specs:
        fam = spec.get("efuse_family")
        if fam and fam not in known:
            unknown.append(fam)
    if unknown:
        unique = sorted(set(unknown))
        warnings.warn(
            f"Unrecognised efuse_family value(s): {', '.join(unique)}. "
            f"Valid families: {', '.join(sorted(known))}. "
            f"These channels will fail during generation unless you use 'custom' "
            f"and provide all electrical parameters manually.",
            stacklevel=2,
        )
    return unknown


def _read_tabular(path: Path) -> list[dict[str, Any]]:
    """Read a CSV, Excel, or Parquet file into a list of row dicts."""
    import pandas as pd

    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    elif suffix in (".xlsx", ".xls"):
        try:
            df = pd.read_excel(path, dtype=str, keep_default_na=False)
        except ImportError as exc:
            raise ImportError(
                f"Reading Excel files requires the 'openpyxl' package. "
                f"Install it with:  pip install openpyxl"
            ) from exc
    elif suffix == ".parquet":
        df = pd.read_parquet(path).astype(str)
    else:
        raise ValueError(
            f"Unsupported file type '{suffix}'. Use .csv, .xlsx, .xls, or .parquet."
        )

    # Normalise headers: lowercase, strip whitespace, replace spaces with underscores
    df.columns = [c.strip().lower().replace(" ", "_").replace("-", "_") for c in df.columns]

    return df.to_dict("records")


def _resolve_column(header: str, alias_map: dict[str, list[str]]) -> str | None:
    """Map a raw column header to a canonical field name, or None if unknown."""
    h = header.strip().lower().replace(" ", "_").replace("-", "_")
    for canonical, aliases in alias_map.items():
        if h in aliases:
            return canonical
    return None


def _coerce_value(key: str, value: str) -> Any:
    """Coerce string cell values to appropriate Python types."""
    if value == "" or value is None:
        return None

    if key in _BOOL_FIELDS:
        return value.strip().lower() in ("true", "1", "yes", "y")

    if key in _NUMERIC_FIELDS:
        try:
            f = float(value)
            return int(f) if f == int(f) and "." not in value else f
        except (ValueError, TypeError):
            return value

    return value


def import_topology(
    source: str | Path,
    output: str | Path | None = None,
    *,
    zone_defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Import a topology from CSV / Excel / Parquet and return as a dict.

    Parameters
    ----------
    source
        Path to the input file (.csv, .xlsx, .xls, .parquet).
    output
        If given, write the topology YAML to this file.
    zone_defaults
        Default zone attributes (location, bus_interface) when not in the spreadsheet.

    Returns
    -------
    dict with "zones" and "channel_specs" keys.
    """
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source}")

    rows = _read_tabular(source)
    if not rows:
        raise ValueError(f"No data rows found in {source}")

    # Map raw columns to canonical names
    raw_headers = list(rows[0].keys())
    col_map: dict[str, str] = {}  # raw_header -> canonical
    for h in raw_headers:
        canonical = _resolve_column(h, _HEADER_ALIASES)
        if canonical is not None:
            col_map[h] = canonical

    # Check required columns
    mapped_fields = set(col_map.values())
    missing = {"channel_id", "zone_id"} - mapped_fields
    if missing:
        raise ValueError(
            f"Required column(s) missing: {', '.join(sorted(missing))}. "
            f"Available columns: {', '.join(raw_headers)}"
        )

    # Process rows → channel_specs + zone info
    channel_specs: list[dict[str, Any]] = []
    zone_info: dict[str, dict[str, Any]] = {}  # zone_id → {name, location, bus}

    for i, row in enumerate(rows, start=2):  # start=2 for spreadsheet row numbers
        spec: dict[str, Any] = {}
        z_meta: dict[str, Any] = {}

        for raw_h, canonical in col_map.items():
            raw_val = row.get(raw_h, "")
            if raw_val == "" or raw_val is None:
                continue

            if canonical in _ZONE_META_KEYS:
                z_meta[canonical] = raw_val
            else:
                val = _coerce_value(canonical, str(raw_val))
                if val is not None:
                    spec[canonical] = val

        # Handle connected_loads — could be comma-separated string
        if "connected_loads" in spec and isinstance(spec["connected_loads"], str):
            spec["connected_loads"] = [
                s.strip() for s in spec["connected_loads"].split(",") if s.strip()
            ]

        if "channel_id" not in spec:
            raise ValueError(f"Row {i}: missing channel_id")
        if "zone_id" not in spec:
            raise ValueError(f"Row {i}: missing zone_id")

        channel_specs.append(spec)

        # Collect zone metadata
        zid = spec["zone_id"]
        if zid not in zone_info:
            zone_info[zid] = {}
        if "zone_name" in z_meta:
            zone_info[zid]["name"] = z_meta["zone_name"]
        if "zone_location" in z_meta:
            zone_info[zid]["location"] = z_meta["zone_location"]
        if "zone_bus" in z_meta:
            zone_info[zid]["bus_interface"] = z_meta["zone_bus"]

    # Build zones list (preserve insertion order = order of first appearance)
    defaults = zone_defaults or {}
    zones: list[dict[str, Any]] = []
    for zid, meta in zone_info.items():
        zone: dict[str, Any] = {"zone_id": zid}
        zone["name"] = meta.get("name", zid.replace("_", " ").title())
        zone["location"] = meta.get("location", defaults.get("location", "body"))
        zone["bus_interface"] = meta.get("bus_interface", defaults.get("bus_interface", "can"))
        zones.append(zone)

    topology: dict[str, Any] = {"zones": zones, "channel_specs": channel_specs}

    # Warn on unrecognised efuse_family values
    _warn_unknown_families(channel_specs)

    if output is not None:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        n_ch = len(channel_specs)
        n_z = len(zones)
        header = (
            f"# Vehicle Topology — {n_z} zones, {n_ch} channels\n"
            f"# Imported from {source.name}\n"
            f"#\n"
            f"# Usage:\n"
            f"#   simulation:\n"
            f"#     topology_file: ./{output.name}\n"
            f"#\n"
        )
        with open(output, "w") as f:
            f.write(header)
            yaml.dump(topology, f, default_flow_style=False, sort_keys=False, width=120)

    return topology


def export_template_csv(output: str | Path, *, minimal: bool = False) -> Path:
    """Write an empty CSV template with the recommended column headers.

    The engineer fills this in from their EE design data, then imports it.

    Parameters
    ----------
    minimal
        If True, emit only the essential columns (channel_id, zone_id,
        efuse_family, load_name, load_type, zone_name).
    """
    import csv

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Core columns in a sensible order for an engineer
    if minimal:
        headers = list(_MINIMAL_HEADERS)
    else:
        headers = [
        "channel_id",
        "zone_id",
        "efuse_family",
        "load_name",
        "load_type",
        "connected_loads",
        "system_cluster",
        "system_name",
        "driver_type",
        "power_class",
        "pwm_capable",
        "nominal_current_a",
        "wire_gauge_mm2",
        "run_length_m",
        "harness_r_ohm",
        "connector_r_ohm",
        "t_ambient_c",
        "die_id",
        "inrush_factor",
        "inrush_duration_ms",
        "duty_cycle",
        # Zone metadata (optional — auto-generates zone names if omitted)
        "zone_name",
        "zone_location",
        "zone_bus",
    ]

    # Write a few example rows to help the engineer get started
    examples = [
        {
            "channel_id": "ch_001",
            "zone_id": "zone_front",
            "efuse_family": "inf_hs_14a",
            "load_name": "headlamp_left",
            "load_type": "resistive",
            "connected_loads": "headlamp_left",
            "system_cluster": "exterior_lighting",
            "system_name": "front_lighting",
            "driver_type": "high_side",
            "power_class": "ignition",
            "pwm_capable": "false",
            "nominal_current_a": "6.0",
            "wire_gauge_mm2": "1.0",
            "run_length_m": "2.5",
            "harness_r_ohm": "0.043",
            "connector_r_ohm": "0.012",
            "t_ambient_c": "40.0",
            "die_id": "front_die_A",
            "inrush_factor": "1.0",
            "inrush_duration_ms": "0",
            "duty_cycle": "1.0",
            "zone_name": "Front Zone Controller",
            "zone_location": "front",
            "zone_bus": "can",
        },
        {
            "channel_id": "ch_002",
            "zone_id": "zone_front",
            "efuse_family": "st_hs_30a",
            "load_name": "blower_motor",
            "load_type": "motor",
            "connected_loads": "hvac_blower",
            "system_cluster": "climate",
            "system_name": "hvac",
            "driver_type": "high_side",
            "power_class": "ignition",
            "pwm_capable": "true",
            "nominal_current_a": "15.0",
            "wire_gauge_mm2": "2.5",
            "run_length_m": "3.0",
            "harness_r_ohm": "0.021",
            "connector_r_ohm": "0.015",
            "t_ambient_c": "45.0",
            "die_id": "front_die_A",
            "inrush_factor": "5.0",
            "inrush_duration_ms": "200",
            "duty_cycle": "0.7",
            "zone_name": "Front Zone Controller",
            "zone_location": "front",
            "zone_bus": "can",
        },
        {
            "channel_id": "ch_003",
            "zone_id": "zone_rear",
            "efuse_family": "inf_hs_9a",
            "load_name": "seat_heater_left",
            "load_type": "ptc",
            "connected_loads": "seat_heater_left",
            "system_cluster": "body_comfort",
            "system_name": "seat_heating",
            "driver_type": "high_side",
            "power_class": "ignition",
            "pwm_capable": "true",
            "nominal_current_a": "8.0",
            "wire_gauge_mm2": "1.5",
            "run_length_m": "4.0",
            "harness_r_ohm": "0.046",
            "connector_r_ohm": "0.012",
            "t_ambient_c": "30.0",
            "die_id": "rear_die_A",
            "inrush_factor": "1.2",
            "inrush_duration_ms": "50",
            "duty_cycle": "0.8",
            "zone_name": "Rear Zone Controller",
            "zone_location": "rear",
            "zone_bus": "can",
        },
    ]

    with open(output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in examples:
            filtered = {k: v for k, v in row.items() if k in headers}
            writer.writerow(filtered)

    return output


def export_topology_csv(
    source: str | Path,
    output: str | Path,
) -> Path:
    """Export a topology YAML file back to CSV for editing in a spreadsheet.

    Parameters
    ----------
    source
        Path to the topology YAML file.
    output
        Path for the output CSV file.

    Returns
    -------
    Path to the written CSV file.
    """
    import csv

    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Topology file not found: {source}")

    with open(source) as f:
        topo = yaml.safe_load(f)

    if not isinstance(topo, dict) or "channel_specs" not in topo:
        raise ValueError(f"'{source}' must be a YAML mapping with a 'channel_specs' key.")

    # Build zone_id → zone metadata lookup
    zone_meta: dict[str, dict[str, str]] = {}
    for z in topo.get("zones", []):
        zid = z.get("zone_id", "")
        zone_meta[zid] = {
            "zone_name": z.get("name", ""),
            "zone_location": z.get("location", ""),
            "zone_bus": z.get("bus_interface", ""),
        }

    # Collect all unique keys across channel_specs for headers
    all_keys: list[str] = []
    seen: set[str] = set()
    # Start with canonical order
    for k in _HEADER_ALIASES:
        if k not in _ZONE_META_KEYS:
            all_keys.append(k)
            seen.add(k)
    # Add zone meta columns at the end
    for k in ("zone_name", "zone_location", "zone_bus"):
        all_keys.append(k)
        seen.add(k)

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        for spec in topo["channel_specs"]:
            row = dict(spec)
            # Flatten connected_loads list to comma-separated string
            if isinstance(row.get("connected_loads"), list):
                row["connected_loads"] = ", ".join(row["connected_loads"])
            # Inject zone metadata
            zid = row.get("zone_id", "")
            if zid in zone_meta:
                row.update(zone_meta[zid])
            writer.writerow(row)

    return output
