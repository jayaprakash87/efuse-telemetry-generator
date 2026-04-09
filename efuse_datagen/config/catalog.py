"""eFuse IC catalog — electrical / thermal presets for 19 production families.

The catalog provides defaults per eFuse IC family so users can write compact
channel specs (referencing a family name) rather than specifying every
electrical parameter from scratch.  Individual channels can override any
catalog default.

Topologies (zones + channels) are defined in YAML files — bundled in
``config/topologies/`` or imported from CSV / Excel via ``topology_io.py``.
See ``config/templates/`` for example scenario configs.

Architecture reference:
    eFuse IC (HW) → SPI → CDD (Complex Device Driver, SW) → COM → CAN/LIN
    Zone Controller = physical ECU running the CDD software

Supported IC families:
    Infineon PROFET+2 (BTS70xx), TLE92104, BTS81000
    ST VIPower VN (single HS), VND (dual HS), VNH (H-bridge), VNL (low-side)
    CUSTOM — user-defined ASIC with user-provided parameters
"""

from __future__ import annotations

from efuse_datagen.schemas.telemetry import (
    ChannelMeta,
    DriverType,
    EFuseFamily,
    EFuseProfile,
    LoadType,
    PowerClass,
    SafetyLevel,
    SourceProtocol,
    ZoneController,
)

# Enum fields on ChannelMeta that arrive as raw strings from YAML specs
_ENUM_COERCE = {
    "load_type": LoadType,
    "driver_type": DriverType,
    "power_class": PowerClass,
    "source_protocol": SourceProtocol,
}

# ---------------------------------------------------------------------------
# Catalog of eFuse IC families with realistic electrical parameters
# ---------------------------------------------------------------------------
# Each entry maps an EFuseFamily to a specific production IC.
#
# Sources: Infineon PROFET+2 datasheets (BTS70xx), Infineon TLE92104 / BTS81000,
# STMicroelectronics VIPower datasheets (VN, VND, VNH, VNL).
#
# Key relationships:
#   - r_ds_on falls with higher current ratings (bigger die / parallel FETs)
#   - r_thermal_kw in °C/W (junction-to-ambient, with PCB copper)
#   - tau_thermal_s = R_th × C_th time constant
#   - Multi-channel ICs (e.g. TLE92104 4ch) share thermal mass on the die
#
# CUSTOM entry provides safe defaults — users MUST override for real ASICs.

EFUSE_CATALOG: dict[EFuseFamily, EFuseProfile] = {
    # ── Infineon PROFET+2 — BTS70xx, Rdson-parametric ────────────────────────
    #
    # BTS7040-1EPA: 40mΩ, ~2.8A, single-channel
    EFuseFamily.INF_HS_2A: EFuseProfile(
        efuse_family=EFuseFamily.INF_HS_2A,
        ic_part_number="BTS7040-1EPA",
        manufacturer="Infineon",
        nominal_current_a=1.5,
        max_current_a=4.0,
        fuse_rating_a=2.8,
        r_ds_on_ohm=0.040,
        r_thermal_kw=80.0,
        tau_thermal_s=8.0,
        cooldown_s=0.5,
        max_retries=5,
        current_adc_bits=12,
        load_type="resistive",
        k_ilis=8500.0,  # BTS7040 ILIS ratio (datasheet typ.)
    ),
    # BTS7020-2EPA: 20mΩ, ~5.5A, dual-channel
    EFuseFamily.INF_HS_5A: EFuseProfile(
        efuse_family=EFuseFamily.INF_HS_5A,
        ic_part_number="BTS7020-2EPA",
        manufacturer="Infineon",
        nominal_current_a=3.5,
        max_current_a=8.0,
        fuse_rating_a=5.5,
        r_ds_on_ohm=0.020,
        r_thermal_kw=65.0,
        tau_thermal_s=10.0,
        cooldown_s=0.5,
        max_retries=5,
        current_adc_bits=12,
        load_type="resistive",
        k_ilis=6400.0,  # BTS7020 ILIS ratio
    ),
    # BTS7012-1EPA: 12mΩ, ~9A, single-channel
    EFuseFamily.INF_HS_9A: EFuseProfile(
        efuse_family=EFuseFamily.INF_HS_9A,
        ic_part_number="BTS7012-1EPA",
        manufacturer="Infineon",
        nominal_current_a=6.0,
        max_current_a=12.0,
        fuse_rating_a=9.0,
        r_ds_on_ohm=0.012,
        r_thermal_kw=50.0,
        tau_thermal_s=12.0,
        cooldown_s=0.8,
        max_retries=4,
        current_adc_bits=12,
        load_type="resistive",
        k_ilis=4580.0,  # BTS7012 ILIS ratio
    ),
    # BTS7010-1EPA: 10mΩ, ~11A, single-channel
    EFuseFamily.INF_HS_11A: EFuseProfile(
        efuse_family=EFuseFamily.INF_HS_11A,
        ic_part_number="BTS7010-1EPA",
        manufacturer="Infineon",
        nominal_current_a=7.0,
        max_current_a=15.0,
        fuse_rating_a=11.0,
        r_ds_on_ohm=0.010,
        r_thermal_kw=45.0,
        tau_thermal_s=14.0,
        cooldown_s=1.0,
        max_retries=4,
        current_adc_bits=12,
        load_type="resistive",
        k_ilis=3640.0,  # BTS7010 ILIS ratio
    ),
    # BTS7008-1EPA: 8mΩ, ~14A, single-channel
    EFuseFamily.INF_HS_14A: EFuseProfile(
        efuse_family=EFuseFamily.INF_HS_14A,
        ic_part_number="BTS7008-1EPA",
        manufacturer="Infineon",
        nominal_current_a=9.0,
        max_current_a=18.0,
        fuse_rating_a=14.0,
        r_ds_on_ohm=0.008,
        r_thermal_kw=40.0,
        tau_thermal_s=15.0,
        cooldown_s=1.0,
        max_retries=3,
        current_adc_bits=12,
        load_type="resistive",
        k_ilis=3640.0,  # BTS7008 ILIS ratio
    ),
    # BTS7006-1EPZ: 6mΩ, ~18A, single-channel
    EFuseFamily.INF_HS_18A: EFuseProfile(
        efuse_family=EFuseFamily.INF_HS_18A,
        ic_part_number="BTS7006-1EPZ",
        manufacturer="Infineon",
        nominal_current_a=12.0,
        max_current_a=24.0,
        fuse_rating_a=18.0,
        r_ds_on_ohm=0.006,
        r_thermal_kw=35.0,
        tau_thermal_s=18.0,
        cooldown_s=1.0,
        max_retries=3,
        current_adc_bits=12,
        load_type="resistive",
        k_ilis=2830.0,  # BTS7006 ILIS ratio
    ),
    # BTS7004-1EPP: 4mΩ, ~28A, single-channel
    EFuseFamily.INF_HS_28A: EFuseProfile(
        efuse_family=EFuseFamily.INF_HS_28A,
        ic_part_number="BTS7004-1EPP",
        manufacturer="Infineon",
        nominal_current_a=18.0,
        max_current_a=35.0,
        fuse_rating_a=28.0,
        r_ds_on_ohm=0.004,
        r_thermal_kw=28.0,
        tau_thermal_s=20.0,
        cooldown_s=1.5,
        max_retries=3,
        current_adc_bits=14,
        load_type="resistive",
        k_ilis=1550.0,  # BTS7004 ILIS ratio (large die → lower ratio)
    ),
    # ── Infineon multi-channel and high-current ──────────────────────────────
    #
    # TLE92104-232QX: 4ch smart switch, ≤10A/ch (only HS used per R30 spec)
    EFuseFamily.INF_MULTI_10A: EFuseProfile(
        efuse_family=EFuseFamily.INF_MULTI_10A,
        ic_part_number="TLE92104-232QX",
        manufacturer="Infineon",
        nominal_current_a=6.0,
        max_current_a=15.0,
        fuse_rating_a=10.0,
        r_ds_on_ohm=0.025,
        r_thermal_kw=40.0,
        tau_thermal_s=15.0,
        cooldown_s=1.0,
        max_retries=3,
        current_adc_bits=12,
        load_type="resistive",
        k_ilis=3640.0,  # TLE92104 ILIS ratio
        safety_level=SafetyLevel.ASIL_B,
    ),
    # BTS81000-SSGI-6ET: high-current PDU, ≤100A
    EFuseFamily.INF_HS_100A: EFuseProfile(
        efuse_family=EFuseFamily.INF_HS_100A,
        ic_part_number="BTS81000-SSGI-6ET",
        manufacturer="Infineon",
        nominal_current_a=60.0,
        max_current_a=120.0,
        fuse_rating_a=100.0,
        r_ds_on_ohm=0.001,
        r_thermal_kw=15.0,
        tau_thermal_s=35.0,
        cooldown_s=3.0,
        max_retries=2,
        current_adc_bits=10,
        load_type="resistive",
        k_ilis=1000.0,  # BTS81000 high-current sense ratio
        safety_level=SafetyLevel.ASIL_B,
    ),
    # ── ST VIPower single high-side ──────────────────────────────────────────
    #
    # VN7140AS: single HS, ~14A
    EFuseFamily.ST_HS_14A: EFuseProfile(
        efuse_family=EFuseFamily.ST_HS_14A,
        ic_part_number="VN7140AS",
        manufacturer="STMicroelectronics",
        nominal_current_a=9.0,
        max_current_a=18.0,
        fuse_rating_a=14.0,
        r_ds_on_ohm=0.040,
        r_thermal_kw=42.0,
        tau_thermal_s=14.0,
        cooldown_s=1.0,
        max_retries=4,
        current_adc_bits=12,
        load_type="resistive",
        k_ilis=7500.0,  # ST VN7140 CS ratio
    ),
    # VN9E30F: single HS, ~30A
    EFuseFamily.ST_HS_30A: EFuseProfile(
        efuse_family=EFuseFamily.ST_HS_30A,
        ic_part_number="VN9E30F",
        manufacturer="STMicroelectronics",
        nominal_current_a=20.0,
        max_current_a=40.0,
        fuse_rating_a=30.0,
        r_ds_on_ohm=0.005,
        r_thermal_kw=25.0,
        tau_thermal_s=22.0,
        cooldown_s=2.0,
        max_retries=2,
        current_adc_bits=12,
        load_type="resistive",
        k_ilis=4000.0,  # ST VN9E30F CS ratio
    ),
    # VN7050AS: single HS, ~50A
    EFuseFamily.ST_HS_50A: EFuseProfile(
        efuse_family=EFuseFamily.ST_HS_50A,
        ic_part_number="VN7050AS",
        manufacturer="STMicroelectronics",
        nominal_current_a=35.0,
        max_current_a=65.0,
        fuse_rating_a=50.0,
        r_ds_on_ohm=0.003,
        r_thermal_kw=18.0,
        tau_thermal_s=28.0,
        cooldown_s=2.5,
        max_retries=2,
        current_adc_bits=12,
        load_type="resistive",
        k_ilis=2500.0,  # ST VN7050 CS ratio
    ),
    # ── ST VIPower dual, H-bridge, low-side ──────────────────────────────────
    #
    # VND7140AJ: dual HS, ~14A/ch
    EFuseFamily.ST_DUAL_14A: EFuseProfile(
        efuse_family=EFuseFamily.ST_DUAL_14A,
        ic_part_number="VND7140AJ",
        manufacturer="STMicroelectronics",
        nominal_current_a=9.0,
        max_current_a=18.0,
        fuse_rating_a=14.0,
        r_ds_on_ohm=0.060,
        r_thermal_kw=38.0,
        tau_thermal_s=16.0,
        cooldown_s=1.0,
        max_retries=3,
        current_adc_bits=12,
        load_type="resistive",
        k_ilis=7500.0,  # ST VND7140 CS ratio
    ),
    # VNH9045AQTR: H-bridge motor driver, ~30A
    EFuseFamily.ST_HB_30A: EFuseProfile(
        efuse_family=EFuseFamily.ST_HB_30A,
        ic_part_number="VNH9045AQTR",
        manufacturer="STMicroelectronics",
        nominal_current_a=20.0,
        max_current_a=40.0,
        fuse_rating_a=30.0,
        r_ds_on_ohm=0.015,
        r_thermal_kw=30.0,
        tau_thermal_s=18.0,
        cooldown_s=1.5,
        max_retries=3,
        current_adc_bits=12,
        load_type="resistive",
        k_ilis=4000.0,  # ST VNH9045 CS ratio
    ),
    # VNL5050S5-E: low-side, ~50A
    EFuseFamily.ST_LS_50A: EFuseProfile(
        efuse_family=EFuseFamily.ST_LS_50A,
        ic_part_number="VNL5050S5-E",
        manufacturer="STMicroelectronics",
        nominal_current_a=35.0,
        max_current_a=65.0,
        fuse_rating_a=50.0,
        r_ds_on_ohm=0.004,
        r_thermal_kw=20.0,
        tau_thermal_s=25.0,
        cooldown_s=2.0,
        max_retries=2,
        current_adc_bits=10,
        load_type="resistive",
        k_ilis=2500.0,  # ST VNL5050 CS ratio
    ),
    # ── Custom / ASIC ─────────────────────────────────────────────────────────
    # Safe generic defaults — users MUST override for real custom ASICs.
    EFuseFamily.CUSTOM: EFuseProfile(
        efuse_family=EFuseFamily.CUSTOM,
        ic_part_number="CUSTOM_ASIC",
        manufacturer="custom",
        nominal_current_a=5.0,
        max_current_a=10.0,
        fuse_rating_a=8.0,
        r_ds_on_ohm=0.025,
        r_thermal_kw=50.0,
        tau_thermal_s=12.0,
        cooldown_s=1.0,
        max_retries=3,
        current_adc_bits=12,
        load_type="resistive",
        k_ilis=5000.0,  # CUSTOM — override for real ASIC
    ),
}


def get_profile(family: EFuseFamily) -> EFuseProfile:
    """Look up the default electrical profile for an eFuse family."""
    return EFUSE_CATALOG[family]


# ---------------------------------------------------------------------------
# Vehicle topology definition — compact input format
# ---------------------------------------------------------------------------


class ChannelSpec(dict):
    """Lightweight dict subclass for type clarity in YAML configs.

    Keys map directly to ChannelMeta fields. At minimum:
        channel_id, load_name, efuse_family
    Optional overrides: nominal_current_a, load_type, inrush_factor, etc.
    Any field not specified is inherited from the eFuse catalog.
    """

    pass


# ---------------------------------------------------------------------------
# Channel factory — expand topology into full ChannelMeta list
# ---------------------------------------------------------------------------


def build_channels(
    zones: list[ZoneController],
    channel_specs: list[dict],
) -> list[ChannelMeta]:
    """Expand compact channel specs into fully specified ChannelMeta objects.

    For each spec:
      1. Look up the eFuse family profile from the catalog
      2. Apply catalog defaults for all electrical / thermal params
      3. Apply any per-channel overrides from the spec
      4. Inherit zone_id and source_protocol from the assigned Zone Controller

    Parameters
    ----------
    zones : list[ZoneController]
        Zone Controllers in this vehicle.
    channel_specs : list[dict]
        Minimal channel definitions. Required keys: channel_id, efuse_family.
        Optional: load_name, zone_id, connected_loads, load_type, and any
        ChannelMeta field to override catalog defaults.

    Returns
    -------
    list[ChannelMeta]
        Fully populated channel list ready for SimulationConfig.
    """
    zone_map = {z.zone_id: z for z in zones}
    channels: list[ChannelMeta] = []

    # Validate zone cross-references upfront
    if zone_map:
        orphans = [
            s.get("channel_id", f"<index {i}>")
            for i, s in enumerate(channel_specs)
            if s.get("zone_id") and s["zone_id"] not in zone_map
        ]
        if orphans:
            raise ValueError(
                f"Channel(s) reference unknown zone_id: {orphans}. "
                f"Defined zones: {sorted(zone_map)}"
            )

    for spec in channel_specs:
        spec = dict(spec)  # shallow copy

        # Resolve eFuse family
        family_raw = spec.pop("efuse_family", "hs_15a")
        if isinstance(family_raw, str):
            family = EFuseFamily(family_raw)
        else:
            family = family_raw
        profile = get_profile(family)

        # Start from catalog defaults
        defaults = {
            "efuse_family": family,
            "nominal_current_a": profile.nominal_current_a,
            "max_current_a": profile.max_current_a,
            "fuse_rating_a": profile.fuse_rating_a,
            "r_ds_on_ohm": profile.r_ds_on_ohm,
            "r_thermal_kw": profile.r_thermal_kw,
            "tau_thermal_s": profile.tau_thermal_s,
            "cooldown_s": profile.cooldown_s,
            "max_retries": profile.max_retries,
            "current_adc_bits": profile.current_adc_bits,
            "voltage_adc_bits": profile.voltage_adc_bits,
            "fit_threshold_a2s": profile.fit_threshold_a2s,
            "short_circuit_threshold_a": profile.short_circuit_threshold_a,
            "thermal_shutdown_c": profile.thermal_shutdown_c,
            "load_type": profile.load_type,
            "k_ilis": profile.k_ilis,
            "k_ilis_tempco_ppm_c": profile.k_ilis_tempco_ppm_c,
            "r_ilis_ohm": profile.r_ilis_ohm,
            "r_ilis_tolerance": profile.r_ilis_tolerance,
            "ol_blank_time_ms": profile.ol_blank_time_ms,
            "ol_threshold_a": profile.ol_threshold_a,
            "rds_on_tempco_exp": profile.rds_on_tempco_exp,
            # harness_r_ohm + connector_r_ohm are board/vehicle-level, not IC-level
            # — keep ChannelMeta defaults (20 mΩ + 10 mΩ); spec overrides apply below
        }

        # Inherit from zone controller if assigned
        zone_id = spec.get("zone_id", "")
        if zone_id and zone_id in zone_map:
            zone = zone_map[zone_id]
            defaults["source_protocol"] = zone.bus_interface

        # Merge: catalog defaults < spec overrides
        merged = {**defaults, **spec}
        # Coerce string enum fields so model_construct() stores proper enums
        for key, enum_cls in _ENUM_COERCE.items():
            val = merged.get(key)
            if isinstance(val, str):
                merged[key] = enum_cls(val)
        # Use model_construct() — catalog defaults are pre-validated, so skip
        # Pydantic field validation for ~10-50x faster channel expansion.
        channels.append(ChannelMeta.model_construct(**merged))

    return channels

