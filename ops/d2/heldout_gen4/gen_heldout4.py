#!/usr/bin/env python3
"""Synthetic multi-cycle website benchmark generator (heldout-v4).

Produces synthetic multi-format, two-level-navigation websites across 5 cycles
(cycle 0 baseline + 4 evolution cycles drawn from {F, F, N, Z}) along with a
markdown report template and a deterministic manifest.json + manifest.sha256.

Python 3.12 stdlib only.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import html as html_mod
import io
import json
import os
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape, quoteattr as xml_quoteattr

SCHEMA_VERSION = "vacant.d2.manifest/1"
GENERATOR_NAME = "heldout-v4"
CYCLE_TYPES_MULTISET = ["F", "F", "N", "Z"]
ALL_CONTENT_FORMATS = ["json", "csv", "tsv", "yaml", "xml", "txt", "md", "html"]
REQUIRED_SPECIAL_FORMATS = ["yaml", "xml", "tsv"]
PAGINABLE_FORMATS = ["csv", "tsv", "txt", "md", "html"]

FETCH_TS = "{{FETCH_TS}}"
FETCH_COUNT = "{{FETCH_COUNT}}"
FETCH_ID = "{{FETCH_ID}}"


# ---------------------------------------------------------------------------
# Domain catalog (rich, varied, realistic operational domains)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AttrSpec:
    key: str          # snake_case key used in structured formats
    label: str        # human label used in template & table headers
    kind: str         # "int", "dec1", "dec2", "ver"
    unit: str         # unit/currency with NO digits (e.g. "USD", "units", "kg", "%", "")
    lo: float
    hi: float


@dataclass(frozen=True)
class TopicSpec:
    slug: str
    title: str
    section_idx: int  # 0, 1, or 2
    attrs: tuple[AttrSpec, AttrSpec, AttrSpec, AttrSpec]  # attrs[0] & attrs[1] share unit/scale


@dataclass(frozen=True)
class DomainSpec:
    domain_id: str
    title: str
    sections: tuple[tuple[str, str], tuple[str, str], tuple[str, str]]  # (slug, title)
    topics: tuple[TopicSpec, ...]  # 7 topics: topics[0] is paginated (2 pages), topics[1..6] singletons
    word_entities: tuple[str, ...]
    numbered_entities: tuple[str, ...]
    notices: tuple[str, ...]


def _a(key: str, label: str, kind: str, unit: str, lo: float, hi: float) -> AttrSpec:
    return AttrSpec(key=key, label=label, kind=kind, unit=unit, lo=lo, hi=hi)


DOMAINS: tuple[DomainSpec, ...] = (
    DomainSpec(
        domain_id="maritime_logistics",
        title="Maritime Port Logistics",
        sections=(
            ("fleet", "Fleet & Vessel Registry"),
            ("tariffs", "Berth & Cargo Tariffs"),
            ("telemetry", "Terminal Systems"),
        ),
        topics=(
            TopicSpec(
                slug="vessel-roster",
                title="Active Vessel Roster",
                section_idx=0,
                attrs=(
                    _a("draft_limit", "draft limit", "dec1", "m", 6.2, 14.8),
                    _a("berth_depth", "berth depth", "dec1", "m", 6.2, 14.8),
                    _a("fuel_reserve", "fuel reserve", "int", "t", 120, 680),
                    _a("crew_quota", "crew quota", "int", "crew", 14, 42),
                ),
            ),
            TopicSpec(
                slug="berth-tariffs",
                title="Berth Tariff Schedule",
                section_idx=1,
                attrs=(
                    _a("berth_fee", "berth fee", "dec2", "USD", 180.0, 950.0),
                    _a("anchorage_fee", "anchorage fee", "dec2", "USD", 180.0, 950.0),
                    _a("mooring_rate", "mooring rate", "dec2", "USD", 65.0, 290.0),
                    _a("free_window", "free window", "int", "hrs", 6, 48),
                ),
            ),
            TopicSpec(
                slug="crane-capacity",
                title="Gantry Crane Allocations",
                section_idx=1,
                attrs=(
                    _a("min_lift_batch", "min lift batch", "int", "units", 20, 95),
                    _a("target_batch", "target batch", "int", "units", 20, 95),
                    _a("rated_load", "rated load", "dec1", "t", 35.0, 82.0),
                    _a("duty_factor", "duty factor", "int", "%", 52, 94),
                ),
            ),
            TopicSpec(
                slug="bunker-depots",
                title="Bunker Fuel Depots",
                section_idx=0,
                attrs=(
                    _a("pump_rate", "pump rate", "dec1", "L/min", 140.0, 520.0),
                    _a("bypass_rate", "bypass rate", "dec1", "L/min", 140.0, 520.0),
                    _a("tank_temperature", "tank temperature", "dec1", "deg C", 18.0, 48.0),
                    _a("line_pressure", "line pressure", "int", "kPa", 210, 490),
                ),
            ),
            TopicSpec(
                slug="navigation-beacons",
                title="Harbor Beacon Controllers",
                section_idx=2,
                attrs=(
                    _a("active_firmware", "active firmware", "ver", "", 2, 7),
                    _a("backup_firmware", "backup firmware", "ver", "", 2, 7),
                    _a("signal_gain", "signal gain", "dec1", "dB", 12.0, 38.0),
                    _a("poll_latency", "poll latency", "int", "ms", 18, 160),
                ),
            ),
            TopicSpec(
                slug="cold-storage-bays",
                title="Reefer Storage Bays",
                section_idx=1,
                attrs=(
                    _a("pallet_capacity", "pallet capacity", "int", "pallets", 110, 460),
                    _a("reserved_pallets", "reserved pallets", "int", "pallets", 110, 460),
                    _a("daily_tariff", "daily tariff", "dec2", "EUR", 24.0, 88.0),
                    _a("power_draw", "power draw", "dec1", "kW", 14.5, 68.0),
                ),
            ),
            TopicSpec(
                slug="shore-power-feeders",
                title="Shore Power Feeders",
                section_idx=2,
                attrs=(
                    _a("peak_output", "peak output", "dec1", "MW", 2.4, 16.5),
                    _a("nominal_output", "nominal output", "dec1", "MW", 2.4, 16.5),
                    _a("feeder_efficiency", "feeder efficiency", "dec1", "%", 88.0, 98.5),
                    _a("active_firmware", "active firmware", "ver", "", 2, 7),
                ),
            ),
        ),
        word_entities=(
            "Amber Falcon", "Cobalt Heron", "Granite Wharf", "Meridian Gate",
            "Cedar Channel", "Silver Osprey", "Tidal Spire", "Ochre Basin",
            "Boreal Quay", "Iron Lantern", "Velvet Cormorant", "Sable Pier",
            "Cinder Shoal", "Linden Lock", "Quartz Jetty", "Copper Gull",
            "Alder Reach", "Fathom Crest", "Harbor Plover", "Marlin Point",
            "Slate Breakwater", "Vesper Buoy", "Garnet Slipway", "Kestrel Sound",
            "Coral Anchorage", "Solstice Mooring", "Pebble Bar", "Dusk Beacon",
            "Rowan Dock", "Opal Headland",
        ),
        numbered_entities=(
            "Kestrel 200", "Berth 14 West", "Pier 7 North", "Crane 42",
            "Channel 9 East", "Tug 18", "Bunker 305", "Lock 4 South",
            "Feeder 12", "Reefer 88", "Gantry 6", "Slip 21",
            "Buoy 104", "Beacon 3", "Tank 55", "Derrick 11",
            "Terminal 8", "Barge 240", "Gate 16 North", "Dock 32",
            "Quay 5 East", "Pump 71", "Silo 19", "Bay 64",
        ),
        notices=(
            "Standard quarterly maritime tariff ledger; all times UTC.",
            "Seasonal tide tables applied to outer harbor berths.",
            "Harbor master audit notice: verify pilotage clearances prior to arrival.",
            "Scheduled dredging underway in outer approach lane.",
            "Automated AIS synchronization enabled across terminal desks.",
        ),
    ),
    DomainSpec(
        domain_id="alpine_rail_ops",
        title="Alpine Rail Operations",
        sections=(
            ("rolling-stock", "Rolling Stock & Consists"),
            ("corridors", "Corridor & Track Limits"),
            ("signaling", "Signaling & Traction Power"),
        ),
        topics=(
            TopicSpec(
                slug="corridor-segments",
                title="Mountain Corridor Segments",
                section_idx=1,
                attrs=(
                    _a("speed_ceiling", "speed ceiling", "int", "km/h", 65, 165),
                    _a("advisory_speed", "advisory speed", "int", "km/h", 65, 165),
                    _a("axle_limit", "axle limit", "dec1", "t", 16.5, 24.5),
                    _a("track_length", "track length", "dec1", "km", 4.2, 38.6),
                ),
            ),
            TopicSpec(
                slug="locomotive-specs",
                title="Locomotive Fleet Specs",
                section_idx=0,
                attrs=(
                    _a("continuous_power", "continuous power", "dec1", "MW", 3.2, 8.8),
                    _a("traction_power", "traction power", "dec1", "MW", 3.2, 8.8),
                    _a("tare_mass", "tare mass", "dec1", "t", 68.0, 124.0),
                    _a("service_interval", "service interval", "int", "days", 14, 90),
                ),
            ),
            TopicSpec(
                slug="coach-inventory",
                title="Passenger Coach Inventory",
                section_idx=0,
                attrs=(
                    _a("seat_quota", "seat quota", "int", "seats", 48, 128),
                    _a("reserved_seats", "reserved seats", "int", "seats", 48, 128),
                    _a("base_fare", "base fare", "dec2", "EUR", 14.5, 76.0),
                    _a("brake_pressure", "brake pressure", "int", "kPa", 420, 620),
                ),
            ),
            TopicSpec(
                slug="tunnel-ventilation",
                title="Tunnel Ventilation Fans",
                section_idx=1,
                attrs=(
                    _a("airflow_target", "airflow target", "int", "rpm", 620, 1480),
                    _a("standby_speed", "standby speed", "int", "rpm", 620, 1480),
                    _a("noise_floor", "noise floor", "dec1", "dB", 54.0, 86.0),
                    _a("filter_load", "filter load", "int", "%", 18, 84),
                ),
            ),
            TopicSpec(
                slug="interlocking-nodes",
                title="Interlocking Signal Nodes",
                section_idx=2,
                attrs=(
                    _a("primary_firmware", "primary firmware", "ver", "", 3, 9),
                    _a("fallback_firmware", "fallback firmware", "ver", "", 3, 9),
                    _a("relay_latency", "relay latency", "dec1", "ms", 8.5, 58.0),
                    _a("uptime_ratio", "uptime ratio", "dec1", "%", 96.0, 99.9),
                ),
            ),
            TopicSpec(
                slug="substation-feeders",
                title="Traction Substation Feeders",
                section_idx=2,
                attrs=(
                    _a("rated_capacity", "rated capacity", "dec1", "MW", 8.0, 26.0),
                    _a("peak_allowance", "peak allowance", "dec1", "MW", 8.0, 26.0),
                    _a("unit_tariff", "unit tariff", "dec2", "EUR", 92.0, 215.0),
                    _a("primary_firmware", "primary firmware", "ver", "", 3, 9),
                ),
            ),
            TopicSpec(
                slug="freight-depots",
                title="Freight Yard Buffers",
                section_idx=0,
                attrs=(
                    _a("min_consist", "min consist", "int", "cars", 10, 44),
                    _a("reorder_consist", "reorder consist", "int", "cars", 10, 44),
                    _a("yard_charge", "yard charge", "dec2", "CHF", 45.0, 220.0),
                    _a("turnaround_time", "turnaround time", "int", "hrs", 4, 24),
                ),
            ),
        ),
        word_entities=(
            "Glacier Express", "Larch Viaduct", "Brenner Crest", "Valais Saddle",
            "Granite Portal", "Ibex Switchback", "Marmot Ridge", "Pine Trestle",
            "Summit Loop", "Spruce Crossing", "Cairn Tunnel", "Chamois Pass",
            "Timber Siding", "Slate Grade", "Kestrel Spur", "Alpen Junction",
            "Frost Gallery", "Basalt Approach", "Edelweiss Yard", "Torrent Bridge",
            "Cobalt Cutting", "Ochre Embankment", "Cedar Gorge", "Rime Overpass",
            "Solstice Platform", "Alder Ramp", "Quartz Portal", "Mica Descent",
            "Tarn Causeway", "Ridge Depot",
        ),
        numbered_entities=(
            "Line 4 North", "Tunnel 12", "Track 8 West", "Consist 310",
            "Engine 72", "Substation 19", "Signal 204", "Switch 15",
            "Viaduct 6", "Corridor 3 East", "Coach 418", "Blower 27",
            "Relay 90", "Depot 5 South", "Siding 14", "Feeder 22",
            "Portal 11", "Grade 7", "Sector 45", "Yard 2 North",
            "Loop 16", "Span 33", "Node 81", "Carriage 502",
        ),
        notices=(
            "Winter timetable active across high-elevation corridors.",
            "Canton rail inspectorate verification completed for north loops.",
            "Avalanche gallery sensors operating in automated mode.",
            "Catenary de-icing schedule posted for overnight windows.",
            "Central dispatch telemetry synchronized at regular intervals.",
        ),
    ),
    DomainSpec(
        domain_id="biolab_coldchain",
        title="Biolab Cold-Chain Inventory",
        sections=(
            ("cryo-vaults", "Cryo Vaults & Freezers"),
            ("reagents", "Reagent & Assay Stocks"),
            ("sensors", "Environmental Telemetry"),
        ),
        topics=(
            TopicSpec(
                slug="reagent-lots",
                title="Controlled Reagent Lots",
                section_idx=1,
                attrs=(
                    _a("min_order", "min order", "int", "units", 25, 140),
                    _a("reorder_point", "reorder point", "int", "units", 25, 140),
                    _a("unit_cost", "unit cost", "dec2", "USD", 16.0, 148.0),
                    _a("shelf_window", "shelf window", "int", "days", 30, 360),
                ),
            ),
            TopicSpec(
                slug="cryo-freezers",
                title="Cryogenic Freezer Units",
                section_idx=0,
                attrs=(
                    _a("setpoint_load", "setpoint load", "dec1", "kW", 1.8, 12.4),
                    _a("peak_load", "peak load", "dec1", "kW", 1.8, 12.4),
                    _a("chamber_mass", "chamber mass", "dec1", "kg", 85.0, 310.0),
                    _a("holdover_time", "holdover time", "int", "hrs", 12, 72),
                ),
            ),
            TopicSpec(
                slug="assay-kits",
                title="Diagnostic Assay Kits",
                section_idx=1,
                attrs=(
                    _a("batch_quota", "batch quota", "int", "kits", 40, 260),
                    _a("safety_quota", "safety quota", "int", "kits", 40, 260),
                    _a("kit_price", "kit price", "dec2", "USD", 28.0, 195.0),
                    _a("yield_rate", "yield rate", "dec1", "%", 82.0, 99.2),
                ),
            ),
            TopicSpec(
                slug="cleanroom-airlocks",
                title="Cleanroom Airlock Suites",
                section_idx=0,
                attrs=(
                    _a("target_pressure", "target pressure", "int", "Pa", 18, 68),
                    _a("alarm_pressure", "alarm pressure", "int", "Pa", 18, 68),
                    _a("flow_velocity", "flow velocity", "dec2", "m/s", 0.32, 0.88),
                    _a("humidity_band", "humidity band", "int", "%", 32, 58),
                ),
            ),
            TopicSpec(
                slug="probe-controllers",
                title="Thermal Probe Controllers",
                section_idx=2,
                attrs=(
                    _a("probe_firmware", "probe firmware", "ver", "", 2, 8),
                    _a("staged_firmware", "staged firmware", "ver", "", 2, 8),
                    _a("sample_latency", "sample latency", "int", "ms", 12, 140),
                    _a("battery_level", "battery level", "int", "%", 64, 99),
                ),
            ),
            TopicSpec(
                slug="nitrogen-manifolds",
                title="Liquid Nitrogen Manifolds",
                section_idx=0,
                attrs=(
                    _a("supply_pressure", "supply pressure", "int", "kPa", 140, 380),
                    _a("relief_pressure", "relief pressure", "int", "kPa", 140, 380),
                    _a("boiloff_rate", "boiloff rate", "dec1", "L/day", 1.5, 14.8),
                    _a("valve_service_fee", "valve service fee", "dec2", "USD", 75.0, 340.0),
                ),
            ),
            TopicSpec(
                slug="courier-shippers",
                title="Validated Cold Shippers",
                section_idx=2,
                attrs=(
                    _a("tare_weight", "tare weight", "dec1", "kg", 4.5, 24.0),
                    _a("payload_weight", "payload weight", "dec1", "kg", 4.5, 24.0),
                    _a("lease_rate", "lease rate", "dec2", "USD", 38.0, 165.0),
                    _a("probe_firmware", "probe firmware", "ver", "", 2, 8),
                ),
            ),
        ),
        word_entities=(
            "Amber Vial", "Cobalt Cryo", "Linden Vault", "Meridian Suite",
            "Boreal Chamber", "Quartz Manifold", "Silver Dewar", "Ochre Assay",
            "Cedar Rack", "Velvet Buffer", "Granite Airlock", "Sable Cassette",
            "Garnet Shipper", "Rowan Incubator", "Tidal Centrifuge", "Vesper Probe",
            "Alder Cabinet", "Opal Isolator", "Cinder Cooler", "Mica Bank",
            "Slate Carousel", "Harbor Box", "Dusk Sensor", "Kestrel Cryostat",
            "Pebble Locker", "Coral Tray", "Iron Canister", "Fathom Fridge",
            "Solstice Dock", "Spruce Logger",
        ),
        numbered_entities=(
            "Vault 12 North", "Freezer 402", "Chamber 7", "Lot 88",
            "Probe 31", "Airlock 5 West", "Manifold 19", "Shipper 205",
            "Kit 64", "Dewar 14", "Rack 9 East", "Sensor 510",
            "Suite 3", "Bay 22", "Buffer 108", "Isolator 16",
            "Unit 75", "Tray 41", "Node 112", "Bank 8 South",
            "Cryo 29", "Cabinet 6", "Logger 94", "Cassette 300",
        ),
        notices=(
            "GMP cold-chain calibration ledger; audited daily.",
            "Secondary nitrogen reserve tanks verified at nominal fill.",
            "Temperature excursion alerts route to campus operations desk.",
            "All lot quantities reflect validated quarantine release counts.",
            "Sensor calibration certificates valid through end of fiscal year.",
        ),
    ),
    DomainSpec(
        domain_id="grid_substation_ops",
        title="Regional Grid Substations",
        sections=(
            ("transformers", "Transformers & Breakers"),
            ("feeders", "Distribution Feeders"),
            ("scada", "SCADA & Protection Relays"),
        ),
        topics=(
            TopicSpec(
                slug="feeder-circuits",
                title="Distribution Feeder Circuits",
                section_idx=1,
                attrs=(
                    _a("rated_load", "rated load", "dec1", "MW", 12.0, 64.0),
                    _a("summer_limit", "summer limit", "dec1", "MW", 12.0, 64.0),
                    _a("line_loss", "line loss", "dec1", "%", 1.4, 7.2),
                    _a("circuit_span", "circuit span", "dec1", "km", 5.5, 48.0),
                ),
            ),
            TopicSpec(
                slug="power-transformers",
                title="Main Power Transformers",
                section_idx=0,
                attrs=(
                    _a("cooling_flow", "cooling flow", "dec1", "L/min", 85.0, 340.0),
                    _a("bypass_flow", "bypass flow", "dec1", "L/min", 85.0, 340.0),
                    _a("winding_temp", "winding temp", "dec1", "deg C", 48.0, 88.0),
                    _a("oil_mass", "oil mass", "int", "kg", 2400, 9800),
                ),
            ),
            TopicSpec(
                slug="breaker-bays",
                title="Circuit Breaker Bays",
                section_idx=0,
                attrs=(
                    _a("gas_pressure", "gas pressure", "int", "kPa", 480, 720),
                    _a("alarm_threshold", "alarm threshold", "int", "kPa", 480, 720),
                    _a("trip_time", "trip time", "dec1", "ms", 18.0, 56.0),
                    _a("cycle_budget", "cycle budget", "int", "ops", 150, 850),
                ),
            ),
            TopicSpec(
                slug="protection-relays",
                title="Digital Protection Relays",
                section_idx=2,
                attrs=(
                    _a("active_firmware", "active firmware", "ver", "", 4, 11),
                    _a("standby_firmware", "standby firmware", "ver", "", 4, 11),
                    _a("scan_latency", "scan latency", "dec1", "ms", 4.2, 28.5),
                    _a("signal_margin", "signal margin", "dec1", "dB", 14.0, 42.0),
                ),
            ),
            TopicSpec(
                slug="capacitor-banks",
                title="Reactive Capacitor Banks",
                section_idx=1,
                attrs=(
                    _a("min_steps", "min steps", "int", "units", 8, 36),
                    _a("target_steps", "target steps", "int", "units", 8, 36),
                    _a("step_tariff", "step tariff", "dec2", "USD", 110.0, 480.0),
                    _a("utilization", "utilization", "int", "%", 38, 92),
                ),
            ),
            TopicSpec(
                slug="battery-rooms",
                title="Station Battery Rooms",
                section_idx=0,
                attrs=(
                    _a("reserve_window", "reserve window", "int", "hrs", 8, 48),
                    _a("design_window", "design window", "int", "hrs", 8, 48),
                    _a("bank_weight", "bank weight", "dec1", "kg", 320.0, 1450.0),
                    _a("charge_state", "charge state", "dec1", "%", 88.0, 99.6),
                ),
            ),
            TopicSpec(
                slug="metering-gateways",
                title="Revenue Metering Gateways",
                section_idx=2,
                attrs=(
                    _a("active_firmware", "active firmware", "ver", "", 4, 11),
                    _a("recovery_firmware", "recovery firmware", "ver", "", 4, 11),
                    _a("settlement_fee", "settlement fee", "dec2", "USD", 42.0, 195.0),
                    _a("packet_loss", "packet loss", "dec2", "%", 0.05, 1.85),
                ),
            ),
        ),
        word_entities=(
            "Cedar Tap", "Granite Bus", "Meridian Tie", "Boreal Ring",
            "Amber Switchyard", "Cobalt Tie", "Ochre Spur", "Silver Intertie",
            "Alder Feeder", "Quartz Bay", "Iron Breaker", "Velvet Reactor",
            "Sable Sub", "Linden Yard", "Garnet Line", "Rowan Circuit",
            "Vesper Tap", "Slate Busbar", "Harbor Grid", "Kestrel Tie",
            "Coral Node", "Solstice Bank", "Pebble Loop", "Dusk Feeder",
            "Mica Ring", "Tarn Station", "Ridge Switch", "Spruce Bay",
            "Cinder Intertie", "Fathom Bus",
        ),
        numbered_entities=(
            "Substation 14", "Feeder 208", "Bay 9 North", "Bus 32",
            "Breaker 64", "Relay 112", "Bank 5 West", "Tap 41",
            "Circuit 18", "Tie 7 South", "Gateway 301", "Room 12",
            "Switch 85", "Ring 4 East", "Node 56", "Transformer 23",
            "Unit 90", "Span 15", "Line 27", "Grid 6",
            "Station 39", "Meter 410", "Reactor 11", "Yard 2",
        ),
        notices=(
            "Regional ISO operational telemetry bulletin; values reflect live bus state.",
            "Peak summer thermal deratings reviewed by transmission engineering.",
            "Protection relay coordination study updated for northern tie lines.",
            "Scheduled breaker maintenance active on auxiliary bays.",
            "Revenue metering reconciliation runs every billing interval.",
        ),
    ),
    DomainSpec(
        domain_id="aerospace_spares",
        title="Aerospace Spares Depot",
        sections=(
            ("airframe", "Airframe & Landing Gear"),
            ("avionics", "Avionics & Actuators"),
            ("tooling", "Ground Support Tooling"),
        ),
        topics=(
            TopicSpec(
                slug="spares-catalog",
                title="Rotable Spares Catalog",
                section_idx=0,
                attrs=(
                    _a("min_stock", "min stock", "int", "units", 12, 85),
                    _a("reorder_level", "reorder level", "int", "units", 12, 85),
                    _a("unit_price", "unit price", "dec2", "USD", 240.0, 1850.0),
                    _a("part_mass", "part mass", "dec1", "kg", 2.4, 48.5),
                ),
            ),
            TopicSpec(
                slug="actuator-benches",
                title="Hydraulic Actuator Benches",
                section_idx=1,
                attrs=(
                    _a("test_pressure", "test pressure", "int", "kPa", 1800, 3600),
                    _a("proof_pressure", "proof pressure", "int", "kPa", 1800, 3600),
                    _a("stroke_time", "stroke time", "dec1", "ms", 42.0, 210.0),
                    _a("seal_life", "seal life", "int", "hrs", 400, 2400),
                ),
            ),
            TopicSpec(
                slug="avionics-modules",
                title="Line-Replaceable Avionics",
                section_idx=1,
                attrs=(
                    _a("flight_firmware", "flight firmware", "ver", "", 3, 10),
                    _a("bench_firmware", "bench firmware", "ver", "", 3, 10),
                    _a("power_budget", "power budget", "dec1", "W", 18.0, 115.0),
                    _a("module_weight", "module weight", "dec2", "kg", 1.25, 9.85),
                ),
            ),
            TopicSpec(
                slug="landing-assemblies",
                title="Landing Gear Assemblies",
                section_idx=0,
                attrs=(
                    _a("strut_charge", "strut charge", "int", "kPa", 920, 2150),
                    _a("reserve_charge", "reserve charge", "int", "kPa", 920, 2150),
                    _a("overhaul_fee", "overhaul fee", "dec2", "USD", 620.0, 2850.0),
                    _a("wear_index", "wear index", "int", "%", 12, 78),
                ),
            ),
            TopicSpec(
                slug="torque-rigs",
                title="Calibrated Torque Rigs",
                section_idx=2,
                attrs=(
                    _a("min_torque", "min torque", "dec1", "Nm", 45.0, 280.0),
                    _a("check_torque", "check torque", "dec1", "Nm", 45.0, 280.0),
                    _a("calibration_cycle", "calibration cycle", "int", "days", 30, 180),
                    _a("accuracy_band", "accuracy band", "dec2", "%", 0.25, 2.45),
                ),
            ),
            TopicSpec(
                slug="ground-carts",
                title="Ground Power Carts",
                section_idx=2,
                attrs=(
                    _a("rated_output", "rated output", "dec1", "kW", 28.0, 115.0),
                    _a("continuous_load", "continuous load", "dec1", "kW", 28.0, 115.0),
                    _a("fuel_burn", "fuel burn", "dec1", "L/hr", 8.5, 34.0),
                    _a("lease_tariff", "lease tariff", "dec2", "EUR", 95.0, 410.0),
                ),
            ),
            TopicSpec(
                slug="test-harnesses",
                title="Diagnostic Test Harnesses",
                section_idx=1,
                attrs=(
                    _a("harness_firmware", "harness firmware", "ver", "", 1, 6),
                    _a("golden_firmware", "golden firmware", "ver", "", 1, 6),
                    _a("bus_latency", "bus latency", "dec1", "ms", 2.4, 24.0),
                    _a("flight_firmware", "flight firmware", "ver", "", 3, 10),
                ),
            ),
        ),
        word_entities=(
            "Amber Strut", "Cobalt Gimbal", "Kestrel Servo", "Meridian Bus",
            "Boreal Fairing", "Granite Yoke", "Silver Pylon", "Ochre Clevis",
            "Cedar Harness", "Velvet Valve", "Quartz Transducer", "Sable Rotor",
            "Linden Bracket", "Garnet Actuator", "Rowan Collar", "Vesper Coupling",
            "Slate Flapper", "Harbor Manifold", "Alder Sensor", "Coral Baffle",
            "Solstice Pod", "Pebble Latch", "Dusk Relay", "Mica Casing",
            "Tarn Duct", "Ridge Bearing", "Spruce Mount", "Cinder Shaft",
            "Fathom Link", "Opal Shroud",
        ),
        numbered_entities=(
            "Rack 14 West", "Bench 204", "Cart 18", "Bay 7 North",
            "Rig 55", "Module 310", "Strut 9", "Harness 42",
            "Valve 108", "Servo 63", "Crate 19", "Kit 805",
            "Bin 27 East", "Dock 4", "Shelf 71", "Cell 16",
            "Pod 33", "Bus 12", "Unit 490", "Stand 25",
            "Depot 8 South", "Lot 60", "Line 15", "Frame 220",
        ),
        notices=(
            "FAA/EASA dual-release rotable spares inventory ledger.",
            "All bench calibration seals verified for current inspection quarter.",
            "Priority AOG allocation rules apply to flight-critical avionics.",
            "Serial traceability logs archived in depot quality system.",
            "Ground support carts subject to weekly load-bank checks.",
        ),
    ),
)


# ---------------------------------------------------------------------------
# Helpers for values, entity twins, formatting
# ---------------------------------------------------------------------------

def format_value(spec: AttrSpec, rng: random.Random, avoid: set[str] | None = None) -> str:
    avoid = avoid or set()
    for _ in range(200):
        if spec.kind == "ver":
            major = rng.randint(int(spec.lo), int(spec.hi))
            minor = rng.randint(0, 18)
            patch = rng.randint(0, 9)
            val = f"v{major}.{minor}.{patch}"
        elif spec.kind == "int":
            num = rng.randint(int(spec.lo), int(spec.hi))
            val = f"{num}{spec.unit}" if spec.unit == "%" else (f"{num} {spec.unit}" if spec.unit else f"{num}")
        elif spec.kind == "dec1":
            raw = round(rng.uniform(spec.lo, spec.hi), 1)
            num_s = f"{raw:.1f}"
            val = f"{num_s}{spec.unit}" if spec.unit == "%" else (f"{num_s} {spec.unit}" if spec.unit else num_s)
        elif spec.kind == "dec2":
            raw = round(rng.uniform(spec.lo, spec.hi), 2)
            num_s = f"{raw:.2f}"
            val = f"{num_s}{spec.unit}" if spec.unit == "%" else (f"{num_s} {spec.unit}" if spec.unit else num_s)
        else:
            raise ValueError(f"Unknown kind: {spec.kind}")
        if val not in avoid:
            return val
    raise RuntimeError(f"Unable to sample distinct value for {spec}")


def make_near_twin(entity: str, used: set[str], rng: random.Random) -> str:
    """Create a near-identical distractor entity name (e.g. 'Amber Falcon' -> 'Amber Falconer')."""
    has_digit = any(ch.isdigit() for ch in entity)
    candidates: list[str] = []
    if has_digit:
        # Perturb suffix or numeric token while keeping near-identical form
        candidates.extend([
            f"{entity}A",
            f"{entity}X",
            f"{entity}B",
            re.sub(r"(\d+)", lambda m: f"{m.group(1)}0", entity, count=1),
            re.sub(r"(\d+)", lambda m: str(int(m.group(1)) + 1), entity, count=1),
            f"{entity} Prime",
        ])
    else:
        # Word-only near-identical variants (no digits introduced)
        if entity.endswith("n"):
            candidates.append(f"{entity}er")
        if entity.endswith("e"):
            candidates.append(f"{entity}r")
        candidates.extend([
            f"{entity}er",
            f"{entity}s",
            f"{entity} East",
            f"{entity} West",
            f"{entity} Annex",
            f"{entity} Upper",
        ])
    rng.shuffle(candidates)
    for cand in candidates:
        if cand != entity and cand not in used:
            return cand
    # Fallback guaranteed unique
    idx = 1
    while True:
        cand = f"{entity} Alt" if idx == 1 else f"{entity} Alt {'I' * idx}"
        if cand not in used:
            return cand
        idx += 1


def derange_indices(n: int, rng: random.Random) -> list[int]:
    """Return a permutation of range(n) that is guaranteed not to be the identity."""
    if n < 2:
        return list(range(n))
    orig = list(range(n))
    perm = list(orig)
    for _ in range(30):
        rng.shuffle(perm)
        if perm != orig:
            return perm
    return perm[1:] + perm[:1]


def title_header(label: str) -> str:
    return " ".join(w.capitalize() for w in label.split())


# ---------------------------------------------------------------------------
# Data model for a generated set
# ---------------------------------------------------------------------------

@dataclass
class HistoryEntry:
    date: str
    entity: str
    field_key: str
    field_label: str
    previous: str
    updated: str
    note: str


@dataclass
class RecordRow:
    entity: str
    fields: dict[str, str]  # attr.key -> value string
    status: str = "verified"


@dataclass
class ContentPageState:
    filename: str
    slug: str
    title: str
    fmt: str  # one of ALL_CONTENT_FORMATS
    section_idx: int
    attrs: tuple[AttrSpec, AttrSpec, AttrSpec, AttrSpec]
    has_history: bool
    row_placeholder: bool
    notice: str
    records: list[RecordRow]
    history: list[HistoryEntry] = field(default_factory=list)
    is_paginated: bool = False
    page_num: int = 0  # 1 or 2 if paginated, else 0


@dataclass
class ClaimDef:
    cid: str
    entity: str
    attr: AttrSpec
    template_line: str
    section_idx: int
    is_shared_unclaimed: bool = False
    is_shared_claimed_pair: bool = False


# ---------------------------------------------------------------------------
# Renderers for all 8 content formats + index pages
# ---------------------------------------------------------------------------

def render_json(page: ContentPageState, domain_title: str, section_title: str) -> str:
    lines: list[str] = [
        "{",
        f'  "title": {json.dumps(f"{domain_title} — {page.title}")},',
        f'  "section": {json.dumps(section_title)},',
        f'  "notice": {json.dumps(page.notice)},',
        '  "meta": {',
        f'    "fetch_ts": "{FETCH_TS}",',
        f'    "fetch_id": "{FETCH_ID}",',
        f'    "fetch_count": "{FETCH_COUNT}"',
        "  },",
        '  "records": [',
    ]
    for i, rec in enumerate(page.records):
        obj: dict[str, str] = {"entity": rec.entity}
        for attr in page.attrs:
            obj[attr.key] = rec.fields[attr.key]
        obj["status"] = rec.status
        if page.row_placeholder:
            obj["fetch_ref"] = FETCH_ID
        comma = "," if i < len(page.records) - 1 else ""
        lines.append(f"    {json.dumps(obj, ensure_ascii=False)}{comma}")
    if page.has_history:
        lines.append("  ],")
        lines.append('  "history": [')
        for i, h in enumerate(page.history):
            hobj = {
                "date": h.date,
                "entity": h.entity,
                "field": h.field_key,
                "previous": h.previous,
                "updated": h.updated,
                "note": h.note,
            }
            comma = "," if i < len(page.history) - 1 else ""
            lines.append(f"    {json.dumps(hobj, ensure_ascii=False)}{comma}")
        lines.append("  ]")
    else:
        lines.append("  ]")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _yaml_quote(s: str) -> str:
    escaped = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_yaml(page: ContentPageState, domain_title: str, section_title: str) -> str:
    lines: list[str] = [
        f"title: {_yaml_quote(f'{domain_title} — {page.title}')}",
        f"section: {_yaml_quote(section_title)}",
        f"notice: {_yaml_quote(page.notice)}",
        f'fetch_ts: "{FETCH_TS}"',
        f'fetch_id: "{FETCH_ID}"',
        f'fetch_count: "{FETCH_COUNT}"',
        "records:",
    ]
    for rec in page.records:
        lines.append(f"  - entity: {_yaml_quote(rec.entity)}")
        for attr in page.attrs:
            suffix = f"  # {FETCH_ID}" if page.row_placeholder else ""
            lines.append(f"    {attr.key}: {_yaml_quote(rec.fields[attr.key])}{suffix}")
        lines.append(f"    status: {_yaml_quote(rec.status)}")
        if page.row_placeholder:
            lines.append(f'    fetch_ref: "{FETCH_ID}"')
    if page.has_history:
        lines.append("history:")
        for h in page.history:
            lines.append(f"  - date: {_yaml_quote(h.date)}")
            lines.append(f"    entity: {_yaml_quote(h.entity)}")
            lines.append(f"    field: {_yaml_quote(h.field_key)}")
            lines.append(f"    previous: {_yaml_quote(h.previous)}")
            lines.append(f"    updated: {_yaml_quote(h.updated)}")
            lines.append(f"    note: {_yaml_quote(h.note)}")
    return "\n".join(lines) + "\n"


def render_xml(page: ContentPageState, domain_title: str, section_title: str) -> str:
    full_title = f"{domain_title} — {page.title}"
    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f"<dataset title={xml_quoteattr(full_title)} section={xml_quoteattr(section_title)}>",
        "  <meta>",
        f"    <fetch_ts>{FETCH_TS}</fetch_ts>",
        f"    <fetch_id>{FETCH_ID}</fetch_id>",
        f"    <fetch_count>{FETCH_COUNT}</fetch_count>",
        f"    <notice>{xml_escape(page.notice)}</notice>",
        "  </meta>",
        "  <records>",
    ]
    for rec in page.records:
        parts = [f"<entity>{xml_escape(rec.entity)}</entity>"]
        for attr in page.attrs:
            parts.append(f"<{attr.key}>{xml_escape(rec.fields[attr.key])}</{attr.key}>")
        parts.append(f"<status>{xml_escape(rec.status)}</status>")
        if page.row_placeholder:
            parts.append(f"<fetch_ref>{FETCH_ID}</fetch_ref>")
        lines.append(f"    <record>{''.join(parts)}</record>")
    lines.append("  </records>")
    if page.has_history:
        lines.append("  <history>")
        for h in page.history:
            lines.append(
                f"    <entry date={xml_quoteattr(h.date)}>"
                f"<entity>{xml_escape(h.entity)}</entity>"
                f"<field>{xml_escape(h.field_key)}</field>"
                f"<previous>{xml_escape(h.previous)}</previous>"
                f"<updated>{xml_escape(h.updated)}</updated>"
                f"<note>{xml_escape(h.note)}</note>"
                f"</entry>"
            )
        lines.append("  </history>")
    lines.append("</dataset>")
    return "\n".join(lines) + "\n"


def render_delimited(page: ContentPageState, delimiter: str) -> str:
    buf = io.StringIO()
    fieldnames = ["entity"] + [a.key for a in page.attrs] + ["status", "fetch_ts", "fetch_id", "fetch_count"]
    writer = csv.DictWriter(buf, fieldnames=fieldnames, delimiter=delimiter, lineterminator="\n")
    writer.writeheader()
    for rec in page.records:
        row: dict[str, str] = {"entity": rec.entity}
        for attr in page.attrs:
            row[attr.key] = rec.fields[attr.key]
        row["status"] = rec.status
        row["fetch_ts"] = FETCH_TS
        row["fetch_id"] = FETCH_ID
        row["fetch_count"] = FETCH_COUNT
        writer.writerow(row)
    return buf.getvalue()


def render_txt(page: ContentPageState, domain_title: str, section_title: str) -> str:
    headers = ["ENTITY"] + [a.label.upper() for a in page.attrs] + ["STATUS"]
    if page.row_placeholder:
        headers.append("FETCH REF")

    rows: list[list[str]] = []
    for rec in page.records:
        row = [rec.entity] + [rec.fields[a.key] for a in page.attrs] + [rec.status]
        if page.row_placeholder:
            row.append(FETCH_ID)
        rows.append(row)

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if len(cell) > widths[i]:
                widths[i] = len(cell)
    col_widths = [w + 4 for w in widths]
    total_w = max(84, sum(col_widths) - 2)

    def fmt_row(cells: list[str]) -> str:
        parts = [cells[i].ljust(col_widths[i]) for i in range(len(cells) - 1)]
        parts.append(cells[-1])
        return "".join(parts)

    lines: list[str] = [
        "=" * total_w,
        f"{domain_title.upper()} — {page.title.upper()}",
        f"Section: {section_title}",
        f"Snapshot: {FETCH_TS} | Request: {FETCH_ID} | Count: {FETCH_COUNT}",
        f"Notice: {page.notice}",
        "=" * total_w,
        "",
        fmt_row(headers),
        "-" * total_w,
    ]
    for row in rows:
        lines.append(fmt_row(row))

    if page.has_history:
        lines.extend([
            "",
            "REVISION HISTORY",
            "-" * total_w,
        ])
        for h in page.history:
            lines.append(
                f"{h.date}  |  {h.entity}  |  {title_header(h.field_label)}: "
                f"adjusted from {h.previous} to {h.updated} ({h.note})"
            )
    return "\n".join(lines) + "\n"


def render_md(page: ContentPageState, domain_title: str, section_title: str) -> str:
    headers = ["Entity"] + [title_header(a.label) for a in page.attrs] + ["Status"]
    if page.row_placeholder:
        headers.append("Fetch Ref")

    lines: list[str] = [
        f"# {domain_title} — {page.title}",
        "",
        f"Section: {section_title}",
        "",
        f"> Snapshot: `{FETCH_TS}` | Request: `{FETCH_ID}` | Count: `{FETCH_COUNT}`",
        "",
        f"Notice: {page.notice}",
        "",
        "## Current Values",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for rec in page.records:
        cells = [rec.entity] + [rec.fields[a.key] for a in page.attrs] + [rec.status]
        if page.row_placeholder:
            cells.append(FETCH_ID)
        lines.append("| " + " | ".join(cells) + " |")

    if page.has_history:
        lines.extend([
            "",
            "## Revision History",
            "",
        ])
        for h in page.history:
            lines.append(
                f"- `{h.date}` — **{h.entity}** ({title_header(h.field_label)}): "
                f"adjusted from `{h.previous}` to `{h.updated}` ({h.note})."
            )
    return "\n".join(lines) + "\n"


def render_html(page: ContentPageState, domain_title: str, section_title: str) -> str:
    full_title = f"{domain_title} — {page.title}"
    headers = ["Entity"] + [title_header(a.label) for a in page.attrs] + ["Status"]
    if page.row_placeholder:
        headers.append("Fetch Ref")

    th_cells = "".join(f"<th>{html_mod.escape(h)}</th>" for h in headers)
    lines: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        f"  <title>{html_mod.escape(full_title)}</title>",
        "</head>",
        "<body>",
        "  <header>",
        f"    <h1>{html_mod.escape(full_title)}</h1>",
        f'    <p class="section">Section: {html_mod.escape(section_title)}</p>',
        f'    <p class="meta">Timestamp: <span>{FETCH_TS}</span> | Request: <span>{FETCH_ID}</span> | Count: <span>{FETCH_COUNT}</span></p>',
        f'    <p class="notice">{html_mod.escape(page.notice)}</p>',
        "  </header>",
        '  <section id="current">',
        "    <h2>Current Values</h2>",
        "    <table>",
        f"      <thead><tr>{th_cells}</tr></thead>",
        "      <tbody>",
    ]
    for rec in page.records:
        cells = [rec.entity] + [rec.fields[a.key] for a in page.attrs] + [rec.status]
        if page.row_placeholder:
            cells.append(FETCH_ID)
        td_cells = "".join(f"<td>{html_mod.escape(c)}</td>" for c in cells)
        lines.append(f"        <tr>{td_cells}</tr>")
    lines.extend([
        "      </tbody>",
        "    </table>",
        "  </section>",
    ])
    if page.has_history:
        lines.extend([
            '  <section id="history">',
            "    <h2>Revision History</h2>",
            "    <ul>",
        ])
        for h in page.history:
            entry_text = (
                f"{h.date} — {h.entity} ({title_header(h.field_label)}): "
                f"adjusted from {h.previous} to {h.updated} ({h.note})."
            )
            lines.append(f"      <li>{html_mod.escape(entry_text)}</li>")
        lines.extend([
            "    </ul>",
            "  </section>",
        ])
    lines.extend(["</body>", "</html>"])
    return "\n".join(lines) + "\n"


def render_content_page(page: ContentPageState, domain_title: str, section_title: str) -> str:
    if page.fmt == "json":
        return render_json(page, domain_title, section_title)
    if page.fmt == "yaml":
        return render_yaml(page, domain_title, section_title)
    if page.fmt == "xml":
        return render_xml(page, domain_title, section_title)
    if page.fmt == "csv":
        return render_delimited(page, ",")
    if page.fmt == "tsv":
        return render_delimited(page, "\t")
    if page.fmt == "txt":
        return render_txt(page, domain_title, section_title)
    if page.fmt == "md":
        return render_md(page, domain_title, section_title)
    if page.fmt == "html":
        return render_html(page, domain_title, section_title)
    raise ValueError(f"Unsupported format: {page.fmt}")


def render_top_index(
    filename: str,
    domain_title: str,
    section_entries: list[tuple[str, str]],  # (sec_filename, sec_title)
) -> str:
    if filename.endswith(".html"):
        lines = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            f"  <title>{html_mod.escape(domain_title)} — Portal Index</title>",
            "</head>",
            "<body>",
            "  <header>",
            f"    <h1>{html_mod.escape(domain_title)} — Operations Portal</h1>",
            f'    <p class="meta">Timestamp: <span>{FETCH_TS}</span> | Request: <span>{FETCH_ID}</span> | Count: <span>{FETCH_COUNT}</span></p>',
            "  </header>",
            "  <nav>",
            "    <h2>Sections</h2>",
            "    <ul>",
        ]
        for sec_file, sec_title in section_entries:
            lines.append(f'      <li><a href="{html_mod.escape(sec_file)}">{html_mod.escape(sec_title)}</a></li>')
        lines.extend(["    </ul>", "  </nav>", "</body>", "</html>"])
        return "\n".join(lines) + "\n"
    else:
        lines = [
            f"# {domain_title} — Operations Portal",
            "",
            f"> Snapshot: `{FETCH_TS}` | Request: `{FETCH_ID}` | Count: `{FETCH_COUNT}`",
            "",
            "## Sections",
            "",
        ]
        for sec_file, sec_title in section_entries:
            lines.append(f"- [{sec_title}]({sec_file})")
        return "\n".join(lines) + "\n"


def render_section_index(
    filename: str,
    domain_title: str,
    section_title: str,
    content_entries: list[tuple[str, str, str]],  # (content_filename, page_title, fmt)
) -> str:
    if filename.endswith(".html"):
        lines = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            f"  <title>{html_mod.escape(domain_title)} — {html_mod.escape(section_title)}</title>",
            "</head>",
            "<body>",
            "  <header>",
            f"    <h1>{html_mod.escape(section_title)}</h1>",
            f"    <p>{html_mod.escape(domain_title)} directory of live data pages.</p>",
            f'    <p class="meta">Timestamp: <span>{FETCH_TS}</span> | Request: <span>{FETCH_ID}</span> | Count: <span>{FETCH_COUNT}</span></p>',
            "  </header>",
            "  <main>",
            "    <h2>Data Pages</h2>",
            "    <ul>",
        ]
        for c_file, c_title, c_fmt in content_entries:
            lines.append(
                f'      <li><a href="{html_mod.escape(c_file)}">{html_mod.escape(c_title)}</a> '
                f'({html_mod.escape(c_fmt.upper())})</li>'
            )
        lines.extend(["    </ul>", "  </main>", "</body>", "</html>"])
        return "\n".join(lines) + "\n"
    else:
        lines = [
            f"# {section_title}",
            "",
            f"{domain_title} directory of live data pages.",
            "",
            f"> Snapshot: `{FETCH_TS}` | Request: `{FETCH_ID}` | Count: `{FETCH_COUNT}`",
            "",
            "## Data Pages",
            "",
        ]
        for c_file, c_title, c_fmt in content_entries:
            lines.append(f"- [{c_title}]({c_file}) ({c_fmt.upper()})")
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Set construction & 4-cycle evolution
# ---------------------------------------------------------------------------

def select_formats_for_set(set_idx: int, rng: random.Random) -> tuple[str, list[str]]:
    """Choose paginated format + 6 distinct singleton formats (= 7 distinct formats total).

    Guarantees:
    - 7 distinct content formats per set (>= 5)
    - All 3 of {yaml, xml, tsv} are included (>= 2)
    - Across consecutive sets, all 8 formats appear reliably.
    """
    # Pick paginated format (rotate across sets so variety is guaranteed)
    pag_fmt = PAGINABLE_FORMATS[(set_idx + rng.randint(0, len(PAGINABLE_FORMATS) - 1)) % len(PAGINABLE_FORMATS)]
    # Remaining 7 formats; omit 1 non-special format (rotated by set_idx so all 8 appear across sets)
    non_special_remaining = [f for f in ALL_CONTENT_FORMATS if f != pag_fmt and f not in REQUIRED_SPECIAL_FORMATS]
    omit_fmt = non_special_remaining[set_idx % len(non_special_remaining)]
    singleton_fmts = [f for f in ALL_CONTENT_FORMATS if f != pag_fmt and f != omit_fmt]
    rng.shuffle(singleton_fmts)
    assert len(singleton_fmts) == 6
    used = {pag_fmt} | set(singleton_fmts)
    assert len(used) == 7
    assert sum(1 for f in REQUIRED_SPECIAL_FORMATS if f in used) >= 2
    return pag_fmt, singleton_fmts


def build_and_write_set(
    set_idx: int,
    seed: int,
    out_dir: Path,
) -> dict[str, Any]:
    set_id = f"s{set_idx + 1:02d}"
    # Derive isolated deterministic RNG for this set
    rng = random.Random(f"{seed}:{GENERATOR_NAME}:{set_id}")

    domain = DOMAINS[set_idx % len(DOMAINS)]
    qualifier = "" if set_idx < len(DOMAINS) else f" (Sector {set_idx // len(DOMAINS) + 1})"
    domain_title = f"{domain.title}{qualifier}"
    domain_id = domain.domain_id if not qualifier else f"{domain.domain_id}_s{set_idx // len(DOMAINS) + 1}"

    # 2 or 3 sections (always 2 or 3)
    n_sections = 3 if (set_idx % 2 == 0 or rng.random() < 0.7) else 2
    if n_sections == 3:
        sec_defs = list(domain.sections)
        topic_sec_map = [t.section_idx for t in domain.topics]
    else:
        sec_defs = [domain.sections[0], domain.sections[1]]
        topic_sec_map = [t.section_idx if t.section_idx < 2 else 1 for t in domain.topics]

    # Top index & section index filenames (mix .html and .md)
    top_ext = "html" if set_idx % 2 == 0 else "md"
    top_index = f"index.{top_ext}"
    sec_files: list[tuple[str, str]] = []
    for i, (sec_slug, sec_title) in enumerate(sec_defs):
        ext = "html" if (set_idx + i) % 2 == 0 else "md"
        sec_files.append((f"sec-{sec_slug}.{ext}", sec_title))

    # Formats for 8 content pages (2 paginated + 6 singletons)
    pag_fmt, singleton_fmts = select_formats_for_set(set_idx, rng)

    # Decide which content pages get row_placeholder=True
    # CSV & TSV always have row_placeholder=True; add enough others so ~55-70% of claims have it.
    page_specs: list[tuple[TopicSpec, str, bool, int]] = []
    # (topic, fmt, is_paginated, page_num)
    pag_topic = domain.topics[0]
    page_specs.append((pag_topic, pag_fmt, True, 1))
    page_specs.append((pag_topic, pag_fmt, True, 2))
    for topic, fmt in zip(domain.topics[1:], singleton_fmts):
        page_specs.append((topic, fmt, False, 0))

    # Build entity pools without reuse across the set
    word_pool = list(domain.word_entities)
    num_pool = list(domain.numbered_entities)
    rng.shuffle(word_pool)
    rng.shuffle(num_pool)
    used_entities: set[str] = set()

    def take_entity(want_number: bool) -> str:
        pool = num_pool if want_number else word_pool
        while pool:
            e = pool.pop()
            if e not in used_entities:
                used_entities.add(e)
                return e
        raise RuntimeError("Entity pool exhausted")

    # Claim allocation across the 8 content pages:
    # pag1: 3 claims, pag2: 3 claims, singletons[0..5]: 3, 3, 2, 2, 2, 2 => total 20 claims
    claims_per_page = [3, 3, 3, 3, 2, 2, 2, 2]
    assert sum(claims_per_page) == 20

    # Assign row_placeholder flags: CSV/TSV mandatory True; pick 3 more non-CSV/TSV pages
    row_ph_flags: list[bool] = []
    non_delim_indices = [i for i, (_, fmt, _, _) in enumerate(page_specs) if fmt not in ("csv", "tsv")]
    chosen_extra_ph = set(rng.sample(non_delim_indices, k=min(3, len(non_delim_indices))))
    for i, (_, fmt, _, _) in enumerate(page_specs):
        row_ph_flags.append(fmt in ("csv", "tsv") or i in chosen_extra_ph)

    # Identify history-enabled pages (all non-CSV/TSV formats)
    has_hist_flags = [fmt not in ("csv", "tsv") for _, fmt, _, _ in page_specs]

    # Pick which 2 singleton history-enabled pages will host:
    # - a shared-unclaimed claim (on several pages)
    # - a shared-claimed pair (2 claims on SAME entity & SAME initial value!)
    hist_singleton_indices = [i for i in range(2, 8) if has_hist_flags[i]]
    assert len(hist_singleton_indices) >= 4
    # Page for the claimed shared-value pair (needs >= 2 claims on that page)
    pair_page_idx = hist_singleton_indices[0]
    # Pages for shared-unclaimed claims: all remaining pages get 1 shared-unclaimed claim
    # so at least 7-8 claims total have a shared value in the same record!

    # Numbered vs word-only assignment across the 20 claims:
    # Aim for ~45% numbered (9 of 20 claims) so >= 30% numbered and rest words-only.
    num_flags = [True] * 9 + [False] * 11
    rng.shuffle(num_flags)

    pages: list[ContentPageState] = []
    claims: list[ClaimDef] = []
    # Track which page index(es) carry each claim id at cycle 0
    claim_page_map: dict[str, list[int]] = {}
    claim_counter = 0

    for p_idx, (topic, fmt, is_pag, page_num) in enumerate(page_specs):
        if is_pag:
            fname = f"{topic.slug}-page-{page_num}.{fmt}"
            ptitle = f"{topic.title} (Page {page_num} of 2)"
        else:
            fname = f"{topic.slug}.{fmt}"
            ptitle = topic.title

        sec_idx = topic_sec_map[0] if is_pag else topic_sec_map[p_idx - 1]
        has_hist = has_hist_flags[p_idx]
        row_ph = row_ph_flags[p_idx]
        notice = domain.notices[(set_idx + p_idx) % len(domain.notices)]

        n_claims_here = claims_per_page[p_idx]
        records: list[RecordRow] = []
        history: list[HistoryEntry] = []

        # Create claimed entities for this page
        if p_idx == pair_page_idx:
            # First entity hosts TWO claims sharing the exact same initial value (attrs[0] & attrs[1])
            want_num = num_flags[claim_counter]
            e_pair = take_entity(want_num)
            # Align num_flags for the second claim on the same entity
            num_flags[claim_counter + 1] = want_num

            shared_val = format_value(topic.attrs[0], rng)
            fields = {
                topic.attrs[0].key: shared_val,
                topic.attrs[1].key: shared_val,
                topic.attrs[2].key: format_value(topic.attrs[2], rng, avoid={shared_val}),
                topic.attrs[3].key: format_value(topic.attrs[3], rng, avoid={shared_val}),
            }
            records.append(RecordRow(entity=e_pair, fields=fields))

            for attr_i in (0, 1):
                claim_counter += 1
                cid = f"c{claim_counter:02d}"
                attr = topic.attrs[attr_i]
                claims.append(
                    ClaimDef(
                        cid=cid,
                        entity=e_pair,
                        attr=attr,
                        template_line=f"- {e_pair} — {attr.label}: ",
                        section_idx=sec_idx,
                        is_shared_claimed_pair=True,
                    )
                )
                claim_page_map[cid] = [p_idx]

            # Near-identical distractor twin for e_pair
            twin = make_near_twin(e_pair, used_entities, rng)
            used_entities.add(twin)
            records.append(
                RecordRow(
                    entity=twin,
                    fields={
                        a.key: format_value(a, rng, avoid={fields[a.key]})
                        for a in topic.attrs
                    },
                )
            )
            remaining_claims = n_claims_here - 2
        else:
            remaining_claims = n_claims_here

        for local_c in range(remaining_claims):
            want_num = num_flags[claim_counter]
            ent = take_entity(want_num)
            claim_counter += 1
            cid = f"c{claim_counter:02d}"

            # Make the first claim on each page (except pair_page_idx) share value with sibling attr[1]
            make_shared = (local_c == 0 and p_idx != pair_page_idx)
            if make_shared:
                claimed_attr = topic.attrs[0]
                shared_val = format_value(topic.attrs[0], rng)
                fields = {
                    topic.attrs[0].key: shared_val,
                    topic.attrs[1].key: shared_val,
                    topic.attrs[2].key: format_value(topic.attrs[2], rng, avoid={shared_val}),
                    topic.attrs[3].key: format_value(topic.attrs[3], rng, avoid={shared_val}),
                }
            else:
                # Pick among attrs[0], attrs[2], attrs[3] so labels stay varied
                attr_choice = [topic.attrs[0], topic.attrs[2], topic.attrs[3]][(p_idx + local_c) % 3]
                claimed_attr = attr_choice
                fields = {a.key: format_value(a, rng) for a in topic.attrs}
                # Ensure distinct values on non-shared rows
                if fields[topic.attrs[1].key] == fields[topic.attrs[0].key]:
                    fields[topic.attrs[1].key] = format_value(topic.attrs[1], rng, avoid={fields[topic.attrs[0].key]})

            records.append(RecordRow(entity=ent, fields=fields))
            claims.append(
                ClaimDef(
                    cid=cid,
                    entity=ent,
                    attr=claimed_attr,
                    template_line=f"- {ent} — {claimed_attr.label}: ",
                    section_idx=sec_idx,
                    is_shared_unclaimed=make_shared,
                )
            )
            claim_page_map[cid] = [p_idx]

            # Add near-identical distractor twin for every claimed entity!
            twin = make_near_twin(ent, used_entities, rng)
            used_entities.add(twin)
            records.append(
                RecordRow(
                    entity=twin,
                    fields={
                        a.key: format_value(a, rng, avoid={fields[a.key]})
                        for a in topic.attrs
                    },
                )
            )

        # Add extra distractor rows so paginated tables are long (7 rows per page = 14 total)
        # and singleton tables have 6 rows each
        target_rows = 7 if is_pag else 6
        while len(records) < target_rows:
            dist_ent = take_entity(rng.random() < 0.45)
            records.append(
                RecordRow(
                    entity=dist_ent,
                    fields={a.key: format_value(a, rng) for a in topic.attrs},
                )
            )

        # Shuffle initial row order
        rng.shuffle(records)

        # Seed initial pre-cycle-0 revision history on history-enabled pages
        if has_hist:
            for idx_h in range(2):
                ref_row = records[idx_h % len(records)]
                ref_attr = topic.attrs[idx_h % 2]
                curr_v = ref_row.fields[ref_attr.key]
                old_v = format_value(ref_attr, rng, avoid={curr_v})
                history.append(
                    HistoryEntry(
                        date=f"2026-09-{10 + p_idx * 2 + idx_h:02d}",
                        entity=ref_row.entity,
                        field_key=ref_attr.key,
                        field_label=ref_attr.label,
                        previous=old_v,
                        updated=curr_v,
                        note="Baseline quarterly review",
                    )
                )

        pages.append(
            ContentPageState(
                filename=fname,
                slug=topic.slug,
                title=ptitle,
                fmt=fmt,
                section_idx=sec_idx,
                attrs=topic.attrs,
                has_history=has_hist,
                row_placeholder=row_ph,
                notice=notice,
                records=records,
                history=history,
                is_paginated=is_pag,
                page_num=page_num,
            )
        )

    assert len(claims) == 20

    # Mirror 1 claim onto a second singleton page that shares the same attr key
    # (exercises multi-page source_pages & consistent multi-page F updates!)
    mirrored_cid: str | None = None
    for c in claims:
        if c.is_shared_claimed_pair or c.is_shared_unclaimed:
            continue
        orig_p_idx = claim_page_map[c.cid][0]
        if orig_p_idx < 2:
            continue
        # Find another singleton page (2..7) that has c.attr.key in its attrs
        for other_p_idx in range(2, 8):
            if other_p_idx == orig_p_idx:
                continue
            other_page = pages[other_p_idx]
            if any(a.key == c.attr.key for a in other_page.attrs):
                if all(r.entity != c.entity for r in other_page.records):
                    orig_rec = next(r for r in pages[orig_p_idx].records if r.entity == c.entity)
                    val = orig_rec.fields[c.attr.key]
                    new_fields = {
                        a.key: (val if a.key == c.attr.key else format_value(a, rng, avoid={val}))
                        for a in other_page.attrs
                    }
                    other_page.records.insert(rng.randint(0, len(other_page.records)), RecordRow(entity=c.entity, fields=new_fields))
                    claim_page_map[c.cid].append(other_p_idx)
                    mirrored_cid = c.cid
                    break
        if mirrored_cid is not None:
            break

    # Shuffle cycle types {F, F, N, Z} for this set
    cycle_types = list(CYCLE_TYPES_MULTISET)
    rng.shuffle(cycle_types)

    # Plan which 4 claims change across the 2 F cycles (2 in first F, 2 in second F)
    # Requirements to hit comfortably:
    # - Req 3: >= 35% of changed claims have old value in history section -> pick 3 of 4 on history-enabled pages (75%)!
    # - Req 5: >= 15% of changed claims have old value still in same record -> pick 2 of 4 from shared-value claims (50%)!
    #   (1 unclaimed shared-value claim + 1 from the claimed shared-value pair!)
    # - Req 6: >= 30% of pages reordered -> N reorders pag1 & pag2; F1 reorders F1_noise; F2 reorders F2_noise (4 distinct pages!)
    # - Req 7: N moves 1 claimed entity between pag1 and pag2!

    # Helper to find claims by properties
    pair_claims = [c for c in claims if c.is_shared_claimed_pair]
    assert len(pair_claims) == 2
    unclaimed_shared_hist_claims = [
        c for c in claims
        if c.is_shared_unclaimed and any(pages[pi].has_history for pi in claim_page_map[c.cid])
        and all(pi >= 2 for pi in claim_page_map[c.cid])
    ]
    assert len(unclaimed_shared_hist_claims) >= 1

    # Pick Claim A (F1 #1): history-enabled singleton with shared unclaimed sibling
    claim_a = unclaimed_shared_hist_claims[0]
    pages_a = set(claim_page_map[claim_a.cid])

    # Pick Claim C (F2 #1): one of the claimed shared-value pair (on pair_page_idx, history-enabled!)
    claim_c = pair_claims[0]
    pages_c = set(claim_page_map[claim_c.cid])
    assert pair_page_idx in pages_c

    # Pick Claim B (F1 #2): prefer the mirrored multi-page claim (if it has a history-enabled page and doesn't overlap pages_a)
    mirrored_c = next((c for c in claims if c.cid == mirrored_cid), None)
    if (
        mirrored_c is not None
        and mirrored_c.cid not in {claim_a.cid, claim_c.cid, pair_claims[1].cid}
        and any(pages[pi].has_history for pi in claim_page_map[mirrored_c.cid])
    ):
        claim_b = mirrored_c
    else:
        other_hist_claims = [
            c for c in claims
            if c.cid not in {claim_a.cid, claim_c.cid, pair_claims[1].cid}
            and any(pages[pi].has_history for pi in claim_page_map[c.cid])
            and not (set(claim_page_map[c.cid]) & ({0, 1} | pages_a))
        ]
        claim_b = rng.choice(other_hist_claims)
    pages_b = set(claim_page_map[claim_b.cid])

    # Pick Claim D (F2 #2): a claim on a page distinct from pages_c (preferring a non-history or paginated page for variety!)
    cand_d = [
        c for c in claims
        if c.cid not in {claim_a.cid, claim_b.cid, claim_c.cid, pair_claims[1].cid}
        and not (set(claim_page_map[c.cid]) & pages_c)
    ]
    non_hist_d = [c for c in cand_d if all(not pages[pi].has_history for pi in claim_page_map[c.cid])]
    claim_d = rng.choice(non_hist_d if non_hist_d else cand_d)
    pages_d = set(claim_page_map[claim_d.cid])

    # Pick F1_noise and F2_noise: distinct singleton pages (>= 2), not touched by their F cycle's changed claims
    f1_claim_pages = pages_a | pages_b
    f2_claim_pages = pages_c | pages_d
    f1_noise_cands = [i for i in range(2, 8) if i not in f1_claim_pages]
    f1_noise_idx = rng.choice(f1_noise_cands)
    f2_noise_cands = [i for i in range(2, 8) if i not in f2_claim_pages and i != f1_noise_idx]
    f2_noise_idx = rng.choice(f2_noise_cands)

    # Pick which claimed entity moves in the N cycle (from pag1 -> pag2 or pag2 -> pag1)
    # Avoid moving claim_d if claim_d is on pag1/pag2? Actually our live state handles it fine either way!
    move_dir = "1->2" if set_idx % 2 == 0 else "2->1"
    src_pag_idx = 0 if move_dir == "1->2" else 1
    dst_pag_idx = 1 if move_dir == "1->2" else 0
    pag_claims_on_src = [c for c in claims if claim_page_map[c.cid][0] == src_pag_idx]
    moved_claim = pag_claims_on_src[0]
    moved_entity = moved_claim.entity

    # Helper to extract current truth & source_pages_by_cycle from live page states
    def snapshot_truth_and_sources() -> tuple[dict[str, str], dict[str, list[str]]]:
        truth_k: dict[str, str] = {}
        src_k: dict[str, list[str]] = {}
        for c in claims:
            found_pages: list[str] = []
            found_val: str | None = None
            for p in pages:
                for rec in p.records:
                    if rec.entity == c.entity and c.attr.key in rec.fields:
                        val = rec.fields[c.attr.key]
                        if found_val is None:
                            found_val = val
                        else:
                            assert found_val == val, f"Inconsistent value for {c.cid}"
                        found_pages.append(p.filename)
            assert found_val is not None and found_pages, f"Claim {c.cid} missing!"
            truth_k[c.cid] = found_val
            src_k[c.cid] = sorted(found_pages)
        return truth_k, src_k

    # Render and write a cycle's full site, returning page_sha256 dict
    set_dir = out_dir / "sets" / set_id
    set_dir.mkdir(parents=True, exist_ok=True)

    # Write template.md (grouped by section with optional ## headings)
    tpl_lines: list[str] = [
        f"# {domain_title} — Operational Report",
        "Fill each blank below with the exact current value (including unit or prefix) as shown on the source site.",
    ]
    for s_idx, (_, s_title) in enumerate(sec_defs):
        sec_claims = [c for c in claims if c.section_idx == s_idx]
        if sec_claims:
            tpl_lines.append("")
            tpl_lines.append(f"## {s_title}")
            for c in sec_claims:
                tpl_lines.append(f"{c.template_line}____")
    (set_dir / "template.md").write_text("\n".join(tpl_lines) + "\n", encoding="utf-8")

    # Pre-render static index pages (they never change across cycles)
    top_index_content = render_top_index(top_index, domain_title, sec_files)
    sec_index_contents: dict[str, str] = {}
    for s_idx, (sec_fname, sec_title) in enumerate(sec_files):
        sec_content_entries = [
            (p.filename, p.title, p.fmt) for p in pages if p.section_idx == s_idx
        ]
        sec_index_contents[sec_fname] = render_section_index(
            sec_fname, domain_title, sec_title, sec_content_entries
        )

    def write_cycle_site(cycle_k: int) -> dict[str, str]:
        site_dir = set_dir / f"cycle_{cycle_k}" / "site"
        site_dir.mkdir(parents=True, exist_ok=True)
        sha_map: dict[str, str] = {}

        def _write(fname: str, text: str) -> None:
            data = text.encode("utf-8")
            (site_dir / fname).write_bytes(data)
            sha_map[fname] = hashlib.sha256(data).hexdigest()

        _write(top_index, top_index_content)
        for sec_fname, sec_text in sec_index_contents.items():
            _write(sec_fname, sec_text)
        for p in pages:
            sec_title = sec_files[p.section_idx][1]
            _write(p.filename, render_content_page(p, domain_title, sec_title))

        return dict(sorted(sha_map.items()))

    truth_by_cycle: list[dict[str, str]] = []
    sources_by_cycle: list[dict[str, list[str]]] = []
    sha_by_cycle: list[dict[str, str]] = []
    cycles_meta: list[dict[str, Any]] = []

    # Cycle 0 (baseline)
    t0, s0 = snapshot_truth_and_sources()
    truth_by_cycle.append(t0)
    sources_by_cycle.append(s0)
    sha_by_cycle.append(write_cycle_site(0))

    # Apply cycles 1..4
    f_seen = 0
    cycle_dates = ["2026-11-02", "2026-11-09", "2026-11-16", "2026-11-23"]

    def apply_claim_change(c: ClaimDef, date_str: str) -> None:
        # Update every page carrying this claim consistently
        old_val: str | None = None
        new_val: str | None = None
        for p in pages:
            for rec in p.records:
                if rec.entity == c.entity and c.attr.key in rec.fields:
                    if old_val is None:
                        old_val = rec.fields[c.attr.key]
                        # Avoid all existing values in the same record so new_val is genuinely fresh
                        avoid = set(rec.fields.values())
                        new_val = format_value(c.attr, rng, avoid=avoid)
                    rec.fields[c.attr.key] = new_val
                    if p.has_history:
                        p.history.append(
                            HistoryEntry(
                                date=date_str,
                                entity=c.entity,
                                field_key=c.attr.key,
                                field_label=c.attr.label,
                                previous=old_val,
                                updated=new_val,
                                note="Scheduled operational revision",
                            )
                        )
        assert old_val is not None and new_val is not None and old_val != new_val

    def apply_unrelated_reorder_and_note(p: ContentPageState, cycle_k: int) -> None:
        # Reorder records (guaranteed non-identity permutation)
        perm = derange_indices(len(p.records), rng)
        p.records = [p.records[i] for i in perm]
        # Also tweak unrelated notice or distractor status
        p.notice = f"{domain.notices[(set_idx + cycle_k + 2) % len(domain.notices)]} (Rev {cycle_k})"
        # For CSV/TSV (no notice field), toggle status on a distractor row too
        claimed_entities = {c.entity for c in claims}
        for rec in p.records:
            if rec.entity not in claimed_entities:
                rec.status = f"audited-c{cycle_k}"
                break

    for idx_c, ctype in enumerate(cycle_types):
        cycle_k = idx_c + 1
        date_str = cycle_dates[idx_c]

        if ctype == "Z":
            # Byte-identical site
            cycles_meta.append({
                "cycle": cycle_k,
                "type": "Z",
                "changed_claims": [],
                "noise_pages": [],
            })

        elif ctype == "N":
            # Pagination move between pag1 and pag2 + reorder BOTH paginated pages
            src_page = pages[src_pag_idx]
            dst_page = pages[dst_pag_idx]

            # Find moved_entity row in src_page
            moved_row_idx = next(i for i, r in enumerate(src_page.records) if r.entity == moved_entity)
            moved_row = src_page.records.pop(moved_row_idx)

            # Also move one unclaimed distractor row in the opposite direction to keep page lengths balanced
            claimed_entities = {c.entity for c in claims}
            swap_row_idx = next(i for i, r in enumerate(dst_page.records) if r.entity not in claimed_entities)
            swap_row = dst_page.records.pop(swap_row_idx)

            # Reorder surviving rows on BOTH pages (guaranteed non-identity on surviving rows!)
            src_perm = derange_indices(len(src_page.records), rng)
            src_page.records = [src_page.records[i] for i in src_perm]
            src_page.records.insert(rng.randint(0, len(src_page.records)), swap_row)

            dst_perm = derange_indices(len(dst_page.records), rng)
            dst_page.records = [dst_page.records[i] for i in dst_perm]
            dst_page.records.insert(rng.randint(0, len(dst_page.records)), moved_row)

            # Update notice on non-delimited paginated pages
            src_page.notice = f"{src_page.notice} [Page rebalanced cycle {cycle_k}]"
            dst_page.notice = f"{dst_page.notice} [Page rebalanced cycle {cycle_k}]"

            noise_list = sorted([src_page.filename, dst_page.filename])
            cycles_meta.append({
                "cycle": cycle_k,
                "type": "N",
                "changed_claims": [],
                "noise_pages": noise_list,
            })

        elif ctype == "F":
            f_seen += 1
            if f_seen == 1:
                chosen_claims = [claim_a, claim_b]
                noise_page = pages[f1_noise_idx]
            else:
                chosen_claims = [claim_c, claim_d]
                noise_page = pages[f2_noise_idx]

            for ch_c in chosen_claims:
                apply_claim_change(ch_c, date_str)

            apply_unrelated_reorder_and_note(noise_page, cycle_k)

            cycles_meta.append({
                "cycle": cycle_k,
                "type": "F",
                "changed_claims": sorted(c.cid for c in chosen_claims),
                "noise_pages": [noise_page.filename],
            })
        else:
            raise ValueError(f"Unknown cycle type: {ctype}")

        tk, sk = snapshot_truth_and_sources()
        truth_by_cycle.append(tk)
        sources_by_cycle.append(sk)
        sha_by_cycle.append(write_cycle_site(cycle_k))

    # Build manifest entry for this set
    all_other_pages = sorted([sf for sf, _ in sec_files] + [p.filename for p in pages])
    claims_manifest = [
        {
            "id": c.cid,
            "entity": c.entity,
            "label": c.attr.label,
            "template_line": c.template_line,
            "source_pages": sources_by_cycle[0][c.cid],
        }
        for c in claims
    ]

    return {
        "set": set_id,
        "domain": domain_id,
        "index": top_index,
        "pages": all_other_pages,
        "claims": claims_manifest,
        "source_pages_by_cycle": sources_by_cycle,
        "truth": truth_by_cycle,
        "cycles": cycles_meta,
        "page_sha256": sha_by_cycle,
    }


def generate(seed: int, n_sets: int, out_dir: Path) -> None:
    if n_sets < 1:
        raise ValueError("--sets must be >= 1")

    if out_dir.exists():
        if not out_dir.is_dir():
            raise SystemExit(f"Error: output path exists and is not a directory: {out_dir}")
        if any(out_dir.iterdir()):
            raise SystemExit(f"Error: output directory is not empty: {out_dir}")
    else:
        out_dir.mkdir(parents=True, exist_ok=True)

    sets_manifest: list[dict[str, Any]] = []
    for i in range(n_sets):
        sets_manifest.append(build_and_write_set(i, seed, out_dir))

    manifest = {
        "schema": SCHEMA_VERSION,
        "generator": GENERATOR_NAME,
        "seed": seed,
        "n_sets": n_sets,
        "cycle_types": list(CYCLE_TYPES_MULTISET),
        "sets": sets_manifest,
    }

    manifest_bytes = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    (out_dir / "manifest.json").write_bytes(manifest_bytes)
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    (out_dir / "manifest.sha256").write_text(f"{manifest_sha}\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate heldout-v4 benchmark dataset.")
    parser.add_argument("--seed", type=int, required=True, help="Deterministic integer seed.")
    parser.add_argument("--sets", type=int, required=True, help="Number of sets to generate.")
    parser.add_argument("--out", type=Path, required=True, help="Output directory (must be empty or non-existent).")
    args = parser.parse_args(argv)

    generate(args.seed, args.sets, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
