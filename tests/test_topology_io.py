"""Tests for topology import/export."""

import csv
from pathlib import Path

import pytest

from efuse_datagen.config.topology_io import export_template_csv, import_topology


@pytest.fixture()
def sample_csv(tmp_path: Path) -> Path:
    """Create a minimal CSV topology file."""
    p = tmp_path / "channels.csv"
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["channel_id", "zone_id", "efuse_family", "load_name", "wire_gauge_mm2", "pwm_capable"])
        w.writerow(["ch_01", "zc_front", "inf_hs_14a", "headlamp", "1.0", "false"])
        w.writerow(["ch_02", "zc_front", "st_hs_30a", "blower", "2.5", "true"])
        w.writerow(["ch_03", "zc_rear", "inf_hs_9a", "seat_heater", "1.5", "yes"])
    return p


@pytest.fixture()
def aliased_csv(tmp_path: Path) -> Path:
    """CSV with non-canonical column names that should be auto-mapped."""
    p = tmp_path / "aliased.csv"
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Ch", "Zone", "IC", "Consumer", "Gauge mm2", "Zone Name", "Location"])
        w.writerow(["ch_01", "zc_a", "inf_hs_5a", "pump", "2.5", "Zone A", "front"])
        w.writerow(["ch_02", "zc_b", "st_hs_14a", "fan", "1.0", "Zone B", "rear"])
    return p


def test_import_basic(sample_csv: Path, tmp_path: Path):
    """Import produces correct zones and channel count."""
    out = tmp_path / "topo.yaml"
    topo = import_topology(sample_csv, out)

    assert len(topo["zones"]) == 2
    assert len(topo["channel_specs"]) == 3
    assert topo["zones"][0]["zone_id"] == "zc_front"
    assert topo["zones"][1]["zone_id"] == "zc_rear"
    assert out.exists()


def test_import_types(sample_csv: Path):
    """Numeric and boolean values are coerced correctly."""
    topo = import_topology(sample_csv)
    ch1 = topo["channel_specs"][0]
    ch3 = topo["channel_specs"][2]

    assert ch1["wire_gauge_mm2"] == 1.0
    assert ch1["pwm_capable"] is False
    assert ch3["pwm_capable"] is True  # "yes" → True


def test_import_aliased_headers(aliased_csv: Path):
    """Non-canonical column headers are resolved via aliases."""
    topo = import_topology(aliased_csv)

    assert len(topo["zones"]) == 2
    assert topo["zones"][0]["name"] == "Zone A"
    assert topo["zones"][0]["location"] == "front"
    assert topo["channel_specs"][0]["efuse_family"] == "inf_hs_5a"
    assert topo["channel_specs"][1]["load_name"] == "fan"


def test_import_missing_required(tmp_path: Path):
    """Missing required columns raise ValueError."""
    p = tmp_path / "bad.csv"
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["efuse_family", "load_name"])
        w.writerow(["inf_hs_14a", "lamp"])

    with pytest.raises(ValueError, match="channel_id"):
        import_topology(p)


def test_export_template(tmp_path: Path):
    """Template CSV has headers and example rows."""
    out = tmp_path / "template.csv"
    export_template_csv(out)

    with open(out) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 3
    assert "channel_id" in reader.fieldnames
    assert "zone_id" in reader.fieldnames
    assert rows[0]["channel_id"] == "ch_001"


def test_roundtrip_template(tmp_path: Path):
    """Export template → import it → produces valid topology."""
    csv_path = tmp_path / "tmpl.csv"
    yaml_path = tmp_path / "topo.yaml"

    export_template_csv(csv_path)
    topo = import_topology(csv_path, yaml_path)

    assert len(topo["zones"]) == 2  # zone_front, zone_rear
    assert len(topo["channel_specs"]) == 3
    assert yaml_path.exists()

    # Verify the YAML can be loaded by the config system
    from efuse_datagen.config.models import load_config_data

    cfg = load_config_data({
        "simulation": {
            "topology_file": str(yaml_path),
            "duration_s": 5,
        }
    })
    assert len(cfg.simulation.channels) == 3


def test_connected_loads_split(tmp_path: Path):
    """Comma-separated connected_loads string is split into a list."""
    p = tmp_path / "multi_loads.csv"
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["channel_id", "zone_id", "load_name", "connected_loads"])
        w.writerow(["ch_01", "z1", "multi_load", "lamp_left, lamp_right, drl"])

    topo = import_topology(p)
    assert topo["channel_specs"][0]["connected_loads"] == ["lamp_left", "lamp_right", "drl"]
