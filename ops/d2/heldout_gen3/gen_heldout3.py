#!/usr/bin/env python3
"""Synthetic multi-format website & evolving report benchmark generator (heldout-v3)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "vacant.d2.manifest/1"
GENERATOR_NAME = "heldout-v3"
CYCLE_TYPES_MULTISET = ["F", "F", "N", "Z"]
STRUCTURED_EXTS = (".json", ".csv", ".txt")


@dataclass(frozen=True)
class AttrSpec:
    key: str
    col_title: str
    label: str
    group_idx: int
    val_kind: tuple[Any, ...]


@dataclass(frozen=True)
class PageSpec:
    slug: str
    fmt: str  # "csv", "json_pretty", "json_compact", "txt", "md", "html"
    title: str
    description: str
    row_placeholder: bool
    placeholder_col: str
    placeholder_tok: str
    attrs: tuple[AttrSpec, ...]
    code_prefix: str


@dataclass(frozen=True)
class DomainSpec:
    domain: str
    site_title: str
    report_title: str
    facility_variants: tuple[str, ...]
    groups: tuple[str, str, str]
    entity_bases: tuple[str, ...]
    twin_suffixes: tuple[str, ...]
    pages: tuple[PageSpec, ...]  # 7 pages: p0..p6
    notices: tuple[str, ...]


DOMAINS: tuple[DomainSpec, ...] = (
    DomainSpec(
        domain="inventory",
        site_title="Meridian Industrial Supply Portal",
        report_title="Industrial Supply Inventory",
        facility_variants=("Central Hub", "West Annex", "North Depot", "East Wing"),
        groups=("Pricing & Stock Levels", "Telemetry & Dispatch", "Catalog Specifications"),
        entity_bases=(
            "Kestrel 200", "Vortex 450", "Aegis Valve 80", "Cobalt Pump 12",
            "Boreal Filter 6", "Trident Coupling 9", "Helios Motor 30",
            "Orion Actuator 5", "Falcon Seal 18", "Summit Gear 44", "Pinnacle Fan 70",
            "Delta Relay 15", "Titan Bearing 22", "Nova Gasket 11", "Sable Hose 36",
            "Crest Manifold 8",
        ),
        twin_suffixes=("X", " Pro", "B", "-M", " Plus", " Mk2", " HD"),
        pages=(
            PageSpec(
                slug="price-schedule.csv",
                fmt="csv",
                title="Wholesale Price Schedule",
                description="Current catalog pricing, warehouse stock counts, and batch minimums.",
                row_placeholder=True,
                placeholder_col="last_checked",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="PRC",
                attrs=(
                    AttrSpec("unit_price", "Unit Price", "unit price", 0, ("money", "USD", 24, 490)),
                    AttrSpec("stock_qty", "In Stock", "stock on hand", 0, ("int_unit", "units", 22, 340)),
                    AttrSpec("min_order", "Min Order", "minimum order quantity", 0, ("int_unit", "units", 10, 85)),
                ),
            ),
            PageSpec(
                slug="warehouse-stock.json",
                fmt="json_pretty",
                title="Warehouse Stock Ledger",
                description="Verified bin counts, reorder thresholds, and tare weights.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="STK",
                attrs=(
                    AttrSpec("stock_qty", "In Stock", "stock on hand", 0, ("int_unit", "units", 22, 340)),
                    AttrSpec("reorder_point", "Reorder Point", "reorder threshold", 0, ("int_unit", "units", 12, 95)),
                    AttrSpec("unit_weight", "Unit Weight", "unit weight", 2, ("dec_unit", "kg", 1.4, 38.5)),
                ),
            ),
            PageSpec(
                slug="bin-telemetry.json",
                fmt="json_compact",
                title="Smart Bin Telemetry Feed",
                description="Compact sensor firmware versions, fill ratios, and scan intervals.",
                row_placeholder=True,
                placeholder_col="trace_id",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="TEL",
                attrs=(
                    AttrSpec("sensor_fw", "Firmware", "bin sensor firmware", 1, ("version", 2, 7)),
                    AttrSpec("bin_fill", "Bin Fill", "bin fill ratio", 1, ("percent", 18, 96)),
                    AttrSpec("scan_cycle", "Scan Cycle", "telemetry scan cycle", 1, ("int_unit", "min", 5, 60)),
                ),
            ),
            PageSpec(
                slug="dispatch-ledger.txt",
                fmt="txt",
                title="Outbound Dispatch Ledger",
                description="Fixed-width fulfillment lead times, crate limits, and dock ratings.",
                row_placeholder=True,
                placeholder_col="Sync Ref",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="DSP",
                attrs=(
                    AttrSpec("lead_time", "Lead Time", "dispatch lead time", 1, ("int_unit", "days", 3, 42)),
                    AttrSpec("crate_cap", "Crate Cap", "crate capacity", 1, ("int_unit", "units", 16, 120)),
                    AttrSpec("dock_fee", "Dock Fee", "handling surcharge", 1, ("money", "USD", 11, 95)),
                ),
            ),
            PageSpec(
                slug="supplier-notes.md",
                fmt="md",
                title="Supplier Specification Notes",
                description="Warranty windows, tolerance grades, and batch order notes.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="SUP",
                attrs=(
                    AttrSpec("warranty_term", "Warranty", "warranty period", 2, ("int_unit", "months", 12, 60)),
                    AttrSpec("defect_cap", "Defect Cap", "max defect allowance", 2, ("percent", 1, 9)),
                    AttrSpec("min_order", "Min Order", "minimum order quantity", 0, ("int_unit", "units", 10, 85)),
                ),
            ),
            PageSpec(
                slug="catalog-overview.html",
                fmt="html",
                title="Hardware Catalog Overview",
                description="HTML summary of pressure limits, service lifespans, and crate sizing.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="CAT",
                attrs=(
                    AttrSpec("pressure_max", "Max Pressure", "maximum working pressure", 2, ("dec_unit", "bar", 4.5, 42.0)),
                    AttrSpec("service_life", "Service Life", "rated service life", 2, ("int_unit", "hours", 1200, 9600)),
                    AttrSpec("crate_cap", "Crate Cap", "crate capacity", 1, ("int_unit", "units", 16, 120)),
                ),
            ),
            PageSpec(
                slug="backorder-queue.csv",
                fmt="csv",
                title="Backorder Allocation Queue",
                description="Pending replenishment lots, reserve fees, and tare weights.",
                row_placeholder=True,
                placeholder_col="audit_ref",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="BOQ",
                attrs=(
                    AttrSpec("reserve_qty", "Reserve Lot", "reserved replenishment lot", 0, ("int_unit", "units", 30, 260)),
                    AttrSpec("expedite_fee", "Expedite Fee", "expedite fee", 0, ("money", "USD", 25, 190)),
                    AttrSpec("unit_weight", "Unit Weight", "unit weight", 2, ("dec_unit", "kg", 1.4, 38.5)),
                ),
            ),
        ),
        notices=(
            "Standard quarterly catalog pricing active.",
            "Zone B aisle labels verified during routine walk.",
            "Receiving dock schedule updated for weekday shifts.",
            "Cycle-count reconciliation completed for mezzanine racks.",
            "Packaging tape supplier switched to recycled stock.",
        ),
    ),
    DomainSpec(
        domain="logistics",
        site_title="Northstar Freight & Cold-Chain Portal",
        report_title="Freight & Cold-Chain Logistics",
        facility_variants=("Midwest Corridor", "Pacific Lane", "Atlantic Hub", "Gulf Terminal"),
        groups=("Tariffs & Capacity", "Transit Telemetry", "Corridor & Depot Rules"),
        entity_bases=(
            "Corridor R14", "Hauler H220", "Reefer Box 40", "Express Van 9",
            "Shuttle T80", "Cargo Pod 16", "Pallet Lift 7",
            "Freight Link 55", "Cold Trunk 12", "Intermodal C3", "Parcel Relay 4",
            "Linehaul L90", "Depot Crane 19", "Dock Loader 6", "Airbridge A11",
            "Crossdock X2",
        ),
        twin_suffixes=("X", " Express", "B", "-L", " Heavy", " Mk2", " Cold"),
        pages=(
            PageSpec(
                slug="tariff-rates.csv",
                fmt="csv",
                title="Freight Tariff Schedule",
                description="Per-lane freight rates, pallet capacities, and detention charges.",
                row_placeholder=True,
                placeholder_col="last_checked",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="TRF",
                attrs=(
                    AttrSpec("lane_rate", "Lane Rate", "base lane tariff", 0, ("money", "USD", 180, 1450)),
                    AttrSpec("pallet_cap", "Pallet Cap", "pallet capacity", 0, ("int_unit", "pallets", 14, 68)),
                    AttrSpec("detention_fee", "Detention", "hourly detention fee", 0, ("money", "USD", 35, 165)),
                ),
            ),
            PageSpec(
                slug="fleet-capacity.json",
                fmt="json_pretty",
                title="Fleet Capacity Registry",
                description="Payload ceilings, pallet slots, and fuel tank capacities.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="FLT",
                attrs=(
                    AttrSpec("pallet_cap", "Pallet Cap", "pallet capacity", 0, ("int_unit", "pallets", 14, 68)),
                    AttrSpec("max_payload", "Max Payload", "maximum payload", 0, ("dec_unit", "tons", 4.5, 28.5)),
                    AttrSpec("fuel_tank", "Fuel Tank", "fuel tank volume", 2, ("int_unit", "L", 180, 820)),
                ),
            ),
            PageSpec(
                slug="dock-status.json",
                fmt="json_compact",
                title="Live Dock Telemetry Stream",
                description="Compact tracker firmware, on-time percentages, and beacon intervals.",
                row_placeholder=True,
                placeholder_col="req_id",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="DCK",
                attrs=(
                    AttrSpec("tracker_fw", "Tracker FW", "GPS tracker firmware", 1, ("version", 1, 6)),
                    AttrSpec("ontime_pct", "On-Time", "on-time arrival rate", 1, ("percent", 78, 99)),
                    AttrSpec("beacon_sec", "Beacon", "telemetry beacon interval", 1, ("int_unit", "s", 15, 180)),
                ),
            ),
            PageSpec(
                slug="manifest-schedule.txt",
                fmt="txt",
                title="Daily Manifest Transit Table",
                description="Fixed-width transit times, route distances, and customs buffers.",
                row_placeholder=True,
                placeholder_col="Audit Ref",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="MNF",
                attrs=(
                    AttrSpec("transit_hrs", "Transit Time", "scheduled transit time", 1, ("int_unit", "hours", 6, 72)),
                    AttrSpec("route_km", "Distance", "corridor distance", 1, ("int_unit", "km", 140, 1850)),
                    AttrSpec("customs_buf", "Customs Buf", "customs clearance buffer", 1, ("int_unit", "min", 25, 240)),
                ),
            ),
            PageSpec(
                slug="corridor-brief.md",
                fmt="md",
                title="Corridor Operations Brief",
                description="Thermal hold ratings, insurance ceilings, and detention policy.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="COR",
                attrs=(
                    AttrSpec("hold_hours", "Thermal Hold", "cold-chain hold duration", 2, ("int_unit", "hours", 12, 96)),
                    AttrSpec("loss_cap", "Shrink Cap", "spoilage threshold", 2, ("percent", 1, 8)),
                    AttrSpec("detention_fee", "Detention", "hourly detention fee", 0, ("money", "USD", 35, 165)),
                ),
            ),
            PageSpec(
                slug="depot-directory.html",
                fmt="html",
                title="Regional Depot Directory",
                description="HTML overview of bay clearances, axle limits, and route lengths.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="DEP",
                attrs=(
                    AttrSpec("bay_height", "Bay Height", "dock door clearance", 2, ("dec_unit", "m", 3.2, 5.8)),
                    AttrSpec("axle_limit", "Axle Limit", "axle load rating", 2, ("dec_unit", "tons", 6.5, 16.5)),
                    AttrSpec("route_km", "Distance", "corridor distance", 1, ("int_unit", "km", 140, 1850)),
                ),
            ),
            PageSpec(
                slug="customs-leadtimes.txt",
                fmt="txt",
                title="Cross-Border Customs Leadtimes",
                description="Fixed-width inspection windows, brokerage fees, and fuel specs.",
                row_placeholder=True,
                placeholder_col="Check TS",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="CST",
                attrs=(
                    AttrSpec("broker_fee", "Broker Fee", "customs brokerage fee", 0, ("money", "EUR", 45, 290)),
                    AttrSpec("inspect_win", "Inspect Win", "inspection window", 1, ("int_unit", "min", 30, 210)),
                    AttrSpec("fuel_tank", "Fuel Tank", "fuel tank volume", 2, ("int_unit", "L", 180, 820)),
                ),
            ),
        ),
        notices=(
            "Standard weekday dispatch lanes operating normally.",
            "Gate 4 badge reader firmware audit completed.",
            "Weigh-station calibration certificates filed for Q3.",
            "Driver lounge signage refreshed at southern crossdock.",
            "Winter tire inspection reminder posted for northern hubs.",
        ),
    ),
    DomainSpec(
        domain="lab_equipment",
        site_title="Helix Analytical Lab Operations",
        report_title="Analytical Lab Equipment",
        facility_variants=("BioLab North", "ChemSuite East", "Metrology Wing", "Cleanroom South"),
        groups=("Calibration & Capacity", "Instrument Telemetry", "Maintenance & Bench Specs"),
        entity_bases=(
            "Centrifuge CR-80", "Spectra UV-400", "Autoclave AC-12", "Chroma HPLC-7",
            "Cryo Freezer F9", "Osmometer OM-3", "Microplate M60",
            "Titrator TR-22", "Balance AB-500", "Incubator IN-4", "Shaker SH-18",
            "Fluorometer FL-9", "Viscometer VS-6", "Sonics Bath S14", "Vacuum Pump VP-5",
            "Thermal Cycler TC-8",
        ),
        twin_suffixes=("R", " Plus", "B", "-Pro", " Dual", " Mk2", " XT"),
        pages=(
            PageSpec(
                slug="calibration-specs.csv",
                fmt="csv",
                title="Calibration Specification Table",
                description="Annual calibration fees, sample capacities, and warm-up windows.",
                row_placeholder=True,
                placeholder_col="last_checked",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="CAL",
                attrs=(
                    AttrSpec("cal_fee", "Cal Fee", "annual calibration fee", 0, ("money", "USD", 140, 890)),
                    AttrSpec("sample_vol", "Sample Vol", "max sample volume", 0, ("int_unit", "mL", 25, 950)),
                    AttrSpec("warmup_min", "Warmup", "warm-up duration", 0, ("int_unit", "min", 8, 55)),
                ),
            ),
            PageSpec(
                slug="instrument-registry.json",
                fmt="json_pretty",
                title="Laboratory Instrument Registry",
                description="Sample capacities, power draws, and benchtop weights.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="INS",
                attrs=(
                    AttrSpec("sample_vol", "Sample Vol", "max sample volume", 0, ("int_unit", "mL", 25, 950)),
                    AttrSpec("power_draw", "Power Draw", "rated power draw", 0, ("int_unit", "W", 120, 2400)),
                    AttrSpec("bench_mass", "Bench Mass", "instrument weight", 2, ("dec_unit", "kg", 4.2, 68.5)),
                ),
            ),
            PageSpec(
                slug="sensor-readouts.json",
                fmt="json_compact",
                title="Instrument Controller Telemetry",
                description="Compact controller firmware, repeatability scores, and cycle intervals.",
                row_placeholder=True,
                placeholder_col="trace_id",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="SNS",
                attrs=(
                    AttrSpec("ctrl_fw", "Controller FW", "controller firmware", 1, ("version", 3, 9)),
                    AttrSpec("repeat_pct", "Repeatability", "repeatability score", 1, ("percent", 91, 99)),
                    AttrSpec("log_period", "Log Period", "data logging interval", 1, ("int_unit", "s", 10, 120)),
                ),
            ),
            PageSpec(
                slug="maintenance-log.txt",
                fmt="txt",
                title="Preventive Maintenance Schedule",
                description="Fixed-width service intervals, rotor speeds, and filter costs.",
                row_placeholder=True,
                placeholder_col="Audit Ref",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="MNT",
                attrs=(
                    AttrSpec("service_days", "Service Cycle", "preventive service interval", 1, ("int_unit", "days", 30, 360)),
                    AttrSpec("max_rpm", "Max Speed", "rated drive speed", 1, ("int_unit", "RPM", 450, 9800)),
                    AttrSpec("filter_cost", "Filter Kit", "replacement filter cost", 1, ("money", "USD", 28, 240)),
                ),
            ),
            PageSpec(
                slug="safety-bulletins.md",
                fmt="md",
                title="Bench Safety & Noise Bulletins",
                description="Acoustic limits, humidity tolerances, and warm-up policies.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="SAF",
                attrs=(
                    AttrSpec("noise_db", "Acoustic Max", "maximum acoustic output", 2, ("int_unit", "dB", 42, 78)),
                    AttrSpec("humidity_max", "Max Humidity", "operating humidity ceiling", 2, ("percent", 55, 85)),
                    AttrSpec("warmup_min", "Warmup", "warm-up duration", 0, ("int_unit", "min", 8, 55)),
                ),
            ),
            PageSpec(
                slug="bench-overview.html",
                fmt="html",
                title="Cleanroom Bench Overview",
                description="HTML catalog of footprint widths, voltage ratings, and drive speeds.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="BNC",
                attrs=(
                    AttrSpec("bench_width", "Width", "footprint width", 2, ("int_unit", "mm", 280, 920)),
                    AttrSpec("line_volt", "Supply Volt", "nominal supply voltage", 2, ("int_unit", "V", 110, 240)),
                    AttrSpec("max_rpm", "Max Speed", "rated drive speed", 1, ("int_unit", "RPM", 450, 9800)),
                ),
            ),
            PageSpec(
                slug="consumable-limits.csv",
                fmt="csv",
                title="Consumable Pack Limits",
                description="Reagent kit prices, tray capacities, and instrument weights.",
                row_placeholder=True,
                placeholder_col="verified_at",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="CON",
                attrs=(
                    AttrSpec("kit_price", "Kit Price", "reagent kit price", 0, ("money", "USD", 38, 310)),
                    AttrSpec("tray_slots", "Tray Slots", "tray slot capacity", 0, ("int_unit", "slots", 12, 96)),
                    AttrSpec("bench_mass", "Bench Mass", "instrument weight", 2, ("dec_unit", "kg", 4.2, 68.5)),
                ),
            ),
        ),
        notices=(
            "Annual ISO bench audit documentation archived.",
            "Fume hood sash alarm checks passed in Wing C.",
            "Deionized water cartridge batch verified for purity.",
            "Sample barcode printer ribbons restocked on Bench 2.",
            "Lab coat laundering pickup moved to Thursday mornings.",
        ),
    ),
    DomainSpec(
        domain="software_releases",
        site_title="Cobalt Platform Release Registry",
        report_title="Platform Software Releases",
        facility_variants=("Production US", "Production EU", "Staging Global", "GovCloud Core"),
        groups=("Releases & Quotas", "Runtime Telemetry", "SLA & Support Policies"),
        entity_bases=(
            "CoreAuth 3", "EdgeProxy 8", "VaultSync 5", "QueueMesh 2",
            "TracePipe 4", "SchemaHub 7", "BillingAPI 6",
            "SearchIdx 9", "NotifyBus 3", "LedgerSvc 4", "MetricIngest 2",
            "PolicyEng 5", "TokenMint 8", "AuditLog 6", "StreamAgg 7",
            "ConfigCtl 3",
        ),
        twin_suffixes=(" LTS", " Edge", "B", "-RC", " Pro", " Plus", " Mini"),
        pages=(
            PageSpec(
                slug="release-matrix.csv",
                fmt="csv",
                title="Active Release Matrix",
                description="Current production versions, memory budgets, and support fees.",
                row_placeholder=True,
                placeholder_col="last_checked",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="REL",
                attrs=(
                    AttrSpec("prod_ver", "Release", "production release version", 0, ("version", 1, 12)),
                    AttrSpec("mem_quota", "Mem Quota", "memory quota", 0, ("int_unit", "GB", 12, 256)),
                    AttrSpec("license_fee", "License Fee", "monthly license fee", 0, ("money", "USD", 95, 980)),
                ),
            ),
            PageSpec(
                slug="service-quotas.json",
                fmt="json_pretty",
                title="Service Quota Configuration",
                description="Memory allocations, disk limits, and connection ceilings.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="QTA",
                attrs=(
                    AttrSpec("mem_quota", "Mem Quota", "memory quota", 0, ("int_unit", "GB", 12, 256)),
                    AttrSpec("disk_quota", "Disk Quota", "storage allocation", 0, ("int_unit", "GB", 50, 950)),
                    AttrSpec("build_size", "Artifact Size", "container image size", 2, ("int_unit", "MB", 45, 860)),
                ),
            ),
            PageSpec(
                slug="runtime-metrics.json",
                fmt="json_compact",
                title="Runtime Telemetry Snapshot",
                description="Compact SDK versions, error budgets, and p95 response latencies.",
                row_placeholder=True,
                placeholder_col="trace_id",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="RTM",
                attrs=(
                    AttrSpec("sdk_ver", "SDK Version", "client SDK version", 1, ("version", 2, 11)),
                    AttrSpec("avail_pct", "Availability", "monthly availability", 1, ("percent", 94, 99)),
                    AttrSpec("p95_ms", "P95 Latency", "p95 response latency", 1, ("dec_unit", "ms", 11.5, 245.5)),
                ),
            ),
            PageSpec(
                slug="package-registry.txt",
                fmt="txt",
                title="Package & Throughput Ledger",
                description="Fixed-width throughput caps, retention windows, and egress costs.",
                row_placeholder=True,
                placeholder_col="Req ID",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="PKG",
                attrs=(
                    AttrSpec("throughput", "Throughput", "sustained throughput", 1, ("int_unit", "MB/s", 40, 880)),
                    AttrSpec("retention_d", "Retention", "log retention window", 1, ("int_unit", "days", 14, 365)),
                    AttrSpec("egress_fee", "Egress Rate", "egress surcharge", 1, ("money", "USD", 12, 145)),
                ),
            ),
            PageSpec(
                slug="changelog-digest.md",
                fmt="md",
                title="Release Support & Changelog Digest",
                description="Support lifetimes, test coverage targets, and licensing notes.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="CHG",
                attrs=(
                    AttrSpec("eol_months", "Support Term", "long-term support window", 2, ("int_unit", "months", 12, 48)),
                    AttrSpec("cov_pct", "Coverage", "unit test coverage", 2, ("percent", 72, 97)),
                    AttrSpec("license_fee", "License Fee", "monthly license fee", 0, ("money", "USD", 95, 980)),
                ),
            ),
            PageSpec(
                slug="platform-status.html",
                fmt="html",
                title="Platform Service Directory",
                description="HTML index of failover targets, worker counts, and retention windows.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="PLT",
                attrs=(
                    AttrSpec("rto_sec", "Failover RTO", "failover recovery target", 2, ("int_unit", "s", 15, 240)),
                    AttrSpec("workers", "Worker Pool", "default worker count", 2, ("int_unit", "nodes", 4, 48)),
                    AttrSpec("retention_d", "Retention", "log retention window", 1, ("int_unit", "days", 14, 365)),
                ),
            ),
            PageSpec(
                slug="sla-targets.txt",
                fmt="txt",
                title="Enterprise SLA Target Sheet",
                description="Fixed-width escalation times, credit caps, and artifact sizes.",
                row_placeholder=True,
                placeholder_col="Sync TS",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="SLA",
                attrs=(
                    AttrSpec("resp_min", "Response SLA", "incident response SLA", 2, ("int_unit", "min", 10, 120)),
                    AttrSpec("credit_pct", "Credit Cap", "service credit cap", 2, ("percent", 10, 45)),
                    AttrSpec("build_size", "Artifact Size", "container image size", 2, ("int_unit", "MB", 45, 860)),
                ),
            ),
        ),
        notices=(
            "Artifact signing keys rotated on standard quarterly cadence.",
            "Dependency SBOM exports archived in build storage.",
            "Documentation search index rebuilt overnight.",
            "Release calendar updated with upcoming freeze windows.",
            "Canary alert routing templates verified by SRE team.",
        ),
    ),
    DomainSpec(
        domain="transit",
        site_title="MetroLink Transit Operations Portal",
        report_title="Metropolitan Transit Operations",
        facility_variants=("North Sector", "Central Ring", "Harbor Division", "Valley Network"),
        groups=("Timetables & Fleet", "Signaling Telemetry", "Network & Station Specs"),
        entity_bases=(
            "Line 14 Express", "Railcar M300", "Bus Route 42", "Tram Loop 7",
            "Ferry Craft 5", "Shuttle B18", "Metro Line 9",
            "Commuter C22", "Rapid Bus 61", "Crosstown 11", "Airport Link 3",
            "Harbor Line 8", "Hillside Tram 4", "Depot Yard 6", "Night Owl 50",
            "Circle Line 2",
        ),
        twin_suffixes=(" Local", "B", " Plus", "-X", " Short", " Mk2", " Peak"),
        pages=(
            PageSpec(
                slug="timetable-headways.csv",
                fmt="csv",
                title="Peak Timetable Headways",
                description="Peak headways, active fleet counts, and base fares.",
                row_placeholder=True,
                placeholder_col="last_checked",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="TTB",
                attrs=(
                    AttrSpec("headway_min", "Peak Headway", "peak headway", 0, ("int_unit", "min", 4, 28)),
                    AttrSpec("fleet_cars", "Active Cars", "active vehicle count", 0, ("int_unit", "cars", 12, 96)),
                    AttrSpec("base_fare", "Base Fare", "standard single fare", 0, ("money", "USD", 2, 18)),
                ),
            ),
            PageSpec(
                slug="rolling-stock.json",
                fmt="json_pretty",
                title="Rolling Stock Allocation",
                description="Active vehicle counts, seated capacities, and corridor lengths.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="RST",
                attrs=(
                    AttrSpec("fleet_cars", "Active Cars", "active vehicle count", 0, ("int_unit", "cars", 12, 96)),
                    AttrSpec("seat_cap", "Seat Cap", "seated passenger capacity", 0, ("int_unit", "seats", 44, 380)),
                    AttrSpec("corridor_km", "Route Length", "corridor length", 2, ("dec_unit", "km", 6.4, 58.5)),
                ),
            ),
            PageSpec(
                slug="signal-feed.json",
                fmt="json_compact",
                title="Signaling & On-Time Feed",
                description="Compact signal firmware, schedule adherence, and dwell targets.",
                row_placeholder=True,
                placeholder_col="trace_id",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="SIG",
                attrs=(
                    AttrSpec("sig_fw", "Signal FW", "signaling unit firmware", 1, ("version", 2, 8)),
                    AttrSpec("adherence", "Adherence", "schedule adherence rate", 1, ("percent", 82, 98)),
                    AttrSpec("dwell_sec", "Dwell Time", "station dwell time", 1, ("int_unit", "s", 20, 95)),
                ),
            ),
            PageSpec(
                slug="station-capacity.txt",
                fmt="txt",
                title="Platform & Speed Ledger",
                description="Fixed-width platform lengths, cruising speeds, and pass fees.",
                row_placeholder=True,
                placeholder_col="Audit Ref",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="STN",
                attrs=(
                    AttrSpec("plat_len", "Platform Len", "platform length", 1, ("int_unit", "m", 65, 280)),
                    AttrSpec("cruise_kmh", "Cruise Speed", "average cruising speed", 1, ("int_unit", "km/h", 28, 115)),
                    AttrSpec("day_pass", "Day Pass", "unlimited day pass fee", 1, ("money", "USD", 8, 34)),
                ),
            ),
            PageSpec(
                slug="service-advisories.md",
                fmt="md",
                title="Service Advisory Summary",
                description="Maintenance windows, load factors, and standard fare notes.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="ADV",
                attrs=(
                    AttrSpec("maint_hrs", "Maint Window", "overnight maintenance window", 2, ("int_unit", "hours", 2, 8)),
                    AttrSpec("load_pct", "Peak Load", "peak load factor", 2, ("percent", 54, 95)),
                    AttrSpec("base_fare", "Base Fare", "standard single fare", 0, ("money", "USD", 2, 18)),
                ),
            ),
            PageSpec(
                slug="network-guide.html",
                fmt="html",
                title="Network Route Guide",
                description="HTML overview of station counts, turnaround buffers, and speeds.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="NET",
                attrs=(
                    AttrSpec("stop_count", "Stops", "scheduled stop count", 2, ("int_unit", "stops", 8, 42)),
                    AttrSpec("turn_min", "Turnaround", "terminal turnaround buffer", 2, ("int_unit", "min", 5, 24)),
                    AttrSpec("cruise_kmh", "Cruise Speed", "average cruising speed", 1, ("int_unit", "km/h", 28, 115)),
                ),
            ),
            PageSpec(
                slug="fare-zones.csv",
                fmt="csv",
                title="Zone Pass Pricing Sheet",
                description="Monthly pass prices, transfer windows, and route lengths.",
                row_placeholder=True,
                placeholder_col="sync_ts",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="FZN",
                attrs=(
                    AttrSpec("month_pass", "Monthly Pass", "monthly zone pass", 0, ("money", "USD", 65, 240)),
                    AttrSpec("xfer_min", "Transfer Win", "free transfer window", 0, ("int_unit", "min", 45, 150)),
                    AttrSpec("corridor_km", "Route Length", "corridor length", 2, ("dec_unit", "km", 6.4, 58.5)),
                ),
            ),
        ),
        notices=(
            "Digital arrival boards synced across downtown concourses.",
            "Escalator inspection completed at Union transfer hall.",
            "Printed pocket timetables restocked at kiosk desks.",
            "Bicycle rack capacity expanded at western park-and-ride.",
            "Wayfinding decals refreshed along mezzanine corridors.",
        ),
    ),
    DomainSpec(
        domain="energy",
        site_title="GridPulse Generation & Storage Portal",
        report_title="Grid & Renewable Energy Assets",
        facility_variants=("Northern Grid", "Highland Basin", "Coastal Intertie", "Desert Array"),
        groups=("Tariffs & Generation", "Grid Telemetry", "Plant & Reserve Specs"),
        entity_bases=(
            "Substation North-4", "Turbine WT-12", "Solar Array S8", "Battery Bank B5",
            "Hydro Unit H3", "Peaker Gas P7", "Inverter IV-20",
            "Wind Block W9", "Storage Cell C14", "Feeder Line F6", "Transformer T40",
            "Geo Plant G2", "Microgrid MG-11", "Capacitor Cap-8", "Breaker Bay K5",
            "Biomass Unit BM-4",
        ),
        twin_suffixes=("B", " East", "X", "-Pro", " Aux", " Mk2", " Plus"),
        pages=(
            PageSpec(
                slug="dispatch-tariffs.csv",
                fmt="csv",
                title="Wholesale Dispatch Tariffs",
                description="Clearing tariffs, nameplate capacities, and ramp fees.",
                row_placeholder=True,
                placeholder_col="last_checked",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="TRG",
                attrs=(
                    AttrSpec("mwh_rate", "Dispatch Rate", "wholesale dispatch tariff", 0, ("money", "USD", 34, 185)),
                    AttrSpec("nameplate", "Nameplate", "nameplate capacity", 0, ("dec_unit", "MW", 12.5, 240.5)),
                    AttrSpec("ramp_fee", "Ramp Fee", "fast-ramp incentive", 0, ("money", "USD", 14, 88)),
                ),
            ),
            PageSpec(
                slug="generation-assets.json",
                fmt="json_pretty",
                title="Generation Asset Register",
                description="Nameplate outputs, storage reserves, and transformer voltages.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="GEN",
                attrs=(
                    AttrSpec("nameplate", "Nameplate", "nameplate capacity", 0, ("dec_unit", "MW", 12.5, 240.5)),
                    AttrSpec("reserve_mwh", "Reserve", "stored energy reserve", 0, ("int_unit", "MWh", 25, 640)),
                    AttrSpec("bus_kv", "Bus Voltage", "intertie bus voltage", 2, ("int_unit", "kV", 33, 345)),
                ),
            ),
            PageSpec(
                slug="grid-telemetry.json",
                fmt="json_compact",
                title="SCADA Telemetry Stream",
                description="Compact relay firmware, capacity factors, and grid frequencies.",
                row_placeholder=True,
                placeholder_col="req_id",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="SCD",
                attrs=(
                    AttrSpec("relay_fw", "Relay FW", "protection relay firmware", 1, ("version", 3, 9)),
                    AttrSpec("cap_factor", "Cap Factor", "net capacity factor", 1, ("percent", 26, 92)),
                    AttrSpec("grid_hz", "Frequency", "measured bus frequency", 1, ("dec_unit", "Hz", 49.5, 60.5)),
                ),
            ),
            PageSpec(
                slug="load-schedule.txt",
                fmt="txt",
                title="Peak Load & Ramp Table",
                description="Fixed-width ramp times, curtailment limits, and standby charges.",
                row_placeholder=True,
                placeholder_col="Sync Ref",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="LOD",
                attrs=(
                    AttrSpec("ramp_min", "Ramp Time", "cold-start ramp time", 1, ("int_unit", "min", 4, 48)),
                    AttrSpec("export_cap", "Export Cap", "scheduled export ceiling", 1, ("dec_unit", "MW", 10.5, 195.5)),
                    AttrSpec("standby_fee", "Standby", "hourly standby fee", 1, ("money", "USD", 22, 140)),
                ),
            ),
            PageSpec(
                slug="outage-notices.md",
                fmt="md",
                title="Planned Outage & Efficiency Notes",
                description="Round-trip efficiencies, inspection cycles, and ramp fees.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="OUT",
                attrs=(
                    AttrSpec("eff_pct", "Efficiency", "round-trip efficiency", 2, ("percent", 68, 96)),
                    AttrSpec("insp_days", "Inspect Cycle", "blade and bus inspection cycle", 2, ("int_unit", "days", 30, 180)),
                    AttrSpec("ramp_fee", "Ramp Fee", "fast-ramp incentive", 0, ("money", "USD", 14, 88)),
                ),
            ),
            PageSpec(
                slug="plant-directory.html",
                fmt="html",
                title="Intertie Plant Directory",
                description="HTML summary of current limits, outage windows, and export ceilings.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="PLN",
                attrs=(
                    AttrSpec("amp_limit", "Current Cap", "feeder current limit", 2, ("int_unit", "A", 180, 1450)),
                    AttrSpec("outage_hrs", "Outage Win", "annual maintenance allowance", 2, ("int_unit", "hours", 16, 120)),
                    AttrSpec("export_cap", "Export Cap", "scheduled export ceiling", 1, ("dec_unit", "MW", 10.5, 195.5)),
                ),
            ),
            PageSpec(
                slug="storage-reserves.txt",
                fmt="txt",
                title="Spinning Reserve Allocation",
                description="Fixed-width reserve margins, blackstart times, and bus voltages.",
                row_placeholder=True,
                placeholder_col="Audit TS",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="RES",
                attrs=(
                    AttrSpec("spin_mw", "Spinning Res", "spinning reserve obligation", 0, ("dec_unit", "MW", 5.5, 65.5)),
                    AttrSpec("black_min", "Blackstart", "blackstart restore time", 1, ("int_unit", "min", 12, 90)),
                    AttrSpec("bus_kv", "Bus Voltage", "intertie bus voltage", 2, ("int_unit", "kV", 33, 345)),
                ),
            ),
        ),
        notices=(
            "Quarterly protective relay test reports uploaded to archive.",
            "Perimeter thermal camera sweep completed at dusk.",
            "Weather station anemometer cups cleaned on Tower 2.",
            "Control room shift handover logbooks audited.",
            "Vegetation clearance finalized along southern easement.",
        ),
    ),
    DomainSpec(
        domain="datacenter",
        site_title="Stratos Colocation Infrastructure Portal",
        report_title="Colocation Data Center Operations",
        facility_variants=("Ashburn DC1", "Frankfurt DC4", "Dallas DC2", "Tokyo DC3"),
        groups=("Rack Pricing & Power", "PDU Telemetry", "Thermal & Cage Specs"),
        entity_bases=(
            "Cage A12", "Cluster C40", "PDU Bank P8", "Chiller CH-5",
            "Rack Row R19", "UPS Module U4", "Switch Fabric S6",
            "Pod Hall H3", "Fiber Vault V2", "Generator G10", "CRAC Unit K7",
            "Storage Bay B9", "Edge Cage E15", "Core Cage N11", "Busway BW-3",
            "Cooling Loop L6",
        ),
        twin_suffixes=("X", " Dual", "B", "-HA", " Plus", " Mk2", " Redundant"),
        pages=(
            PageSpec(
                slug="rack-pricing.csv",
                fmt="csv",
                title="Colocation Rack Pricing",
                description="Monthly rack leases, power commitments, and cross-connect fees.",
                row_placeholder=True,
                placeholder_col="last_checked",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="RCK",
                attrs=(
                    AttrSpec("rack_fee", "Rack Lease", "monthly rack lease", 0, ("money", "USD", 650, 2950)),
                    AttrSpec("power_kw", "Power Cap", "committed power draw", 0, ("dec_unit", "kW", 6.5, 48.5)),
                    AttrSpec("xconn_fee", "Cross-Conn", "cross-connect fee", 0, ("money", "USD", 120, 480)),
                ),
            ),
            PageSpec(
                slug="cluster-inventory.json",
                fmt="json_pretty",
                title="Hall Cluster Inventory",
                description="Power commitments, cabinet counts, and floor load ratings.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="CLS",
                attrs=(
                    AttrSpec("power_kw", "Power Cap", "committed power draw", 0, ("dec_unit", "kW", 6.5, 48.5)),
                    AttrSpec("rack_units", "Cabinets", "allocated cabinet count", 0, ("int_unit", "racks", 6, 64)),
                    AttrSpec("floor_kg", "Floor Load", "raised floor load rating", 2, ("int_unit", "kg", 650, 1850)),
                ),
            ),
            PageSpec(
                slug="pdu-stream.json",
                fmt="json_compact",
                title="Smart PDU Telemetry Stream",
                description="Compact PDU firmware, load utilization, and poll intervals.",
                row_placeholder=True,
                placeholder_col="trace_id",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="PDU",
                attrs=(
                    AttrSpec("pdu_fw", "PDU Firmware", "PDU controller firmware", 1, ("version", 2, 9)),
                    AttrSpec("load_util", "Load Util", "PDU load utilization", 1, ("percent", 32, 88)),
                    AttrSpec("poll_sec", "Poll Rate", "telemetry poll interval", 1, ("int_unit", "s", 10, 120)),
                ),
            ),
            PageSpec(
                slug="thermal-table.txt",
                fmt="txt",
                title="Thermal & Airflow Ledger",
                description="Fixed-width aisle temperatures, chilled water flows, and PUE targets.",
                row_placeholder=True,
                placeholder_col="Sync Ref",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="THM",
                attrs=(
                    AttrSpec("aisle_c", "Cold Aisle", "cold aisle setpoint", 1, ("dec_unit", "C", 18.5, 26.5)),
                    AttrSpec("flow_lpm", "Coolant Flow", "chilled water flow rate", 1, ("int_unit", "L/min", 45, 420)),
                    AttrSpec("uplink_gb", "Uplink Cap", "redundant uplink capacity", 1, ("int_unit", "Gbps", 20, 400)),
                ),
            ),
            PageSpec(
                slug="ops-runbook.md",
                fmt="md",
                title="Cage Operations Runbook",
                description="UPS runtime minimums, humidity targets, and cross-connect rates.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="RUN",
                attrs=(
                    AttrSpec("ups_min", "UPS Runtime", "battery ride-through time", 2, ("int_unit", "min", 12, 65)),
                    AttrSpec("rh_pct", "Humidity", "relative humidity target", 2, ("percent", 38, 58)),
                    AttrSpec("xconn_fee", "Cross-Conn", "cross-connect fee", 0, ("money", "USD", 120, 480)),
                ),
            ),
            PageSpec(
                slug="cage-overview.html",
                fmt="html",
                title="Colocation Cage Directory",
                description="HTML summary of breaker ratings, aisle widths, and uplink speeds.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="CAG",
                attrs=(
                    AttrSpec("breaker_a", "Breaker", "primary breaker rating", 2, ("int_unit", "A", 30, 250)),
                    AttrSpec("aisle_mm", "Aisle Width", "cold aisle width", 2, ("int_unit", "mm", 1200, 2400)),
                    AttrSpec("uplink_gb", "Uplink Cap", "redundant uplink capacity", 1, ("int_unit", "Gbps", 20, 400)),
                ),
            ),
            PageSpec(
                slug="bandwidth-tiers.csv",
                fmt="csv",
                title="Dedicated Bandwidth Tiers",
                description="Transit commit prices, burst ceilings, and floor load specs.",
                row_placeholder=True,
                placeholder_col="audit_ts",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="BWT",
                attrs=(
                    AttrSpec("commit_fee", "Transit Fee", "monthly transit commit", 0, ("money", "USD", 280, 1650)),
                    AttrSpec("burst_gb", "Burst Cap", "burstable bandwidth cap", 0, ("int_unit", "Gbps", 10, 200)),
                    AttrSpec("floor_kg", "Floor Load", "raised floor load rating", 2, ("int_unit", "kg", 650, 1850)),
                ),
            ),
        ),
        notices=(
            "Biometric mantrap sensors recalibrated in Lobby A.",
            "Monthly generator load-bank test completed with zero faults.",
            "Blanking panel inventory audited across Hall 2.",
            "Fiber tray labeling updated on overhead ladder racks.",
            "Visitor escort badge lanyards restocked at security desk.",
        ),
    ),
    DomainSpec(
        domain="maritime",
        site_title="Bayport Maritime Terminal Portal",
        report_title="Port & Maritime Operations",
        facility_variants=("Pier Alpha", "Container West", "Deepwater South", "Bulk Terminal East"),
        groups=("Berth Tariffs & Capacity", "Crane Telemetry", "Harbor & Vessel Specs"),
        entity_bases=(
            "Berth B14", "Gantry G8", "Tugboat V22", "Feeder Ship F9",
            "Bulk Pier P3", "Quay Crane Q11", "Barge Unit R6",
            "RoRo Ramp M4", "Pilot Boat K5", "Drydock D7", "Tanker Slip T12",
            "Reefer Yard Y8", "Shore Power S3", "Gate Lane L16", "Anchor Zone A2",
            "Wharf Apron W5",
        ),
        twin_suffixes=("X", " Deep", "B", "-East", " Heavy", " Mk2", " Plus"),
        pages=(
            PageSpec(
                slug="berth-tariffs.csv",
                fmt="csv",
                title="Port Berth Tariff Table",
                description="Daily wharfage fees, draft limits, and pilotage surcharges.",
                row_placeholder=True,
                placeholder_col="last_checked",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="BRT",
                attrs=(
                    AttrSpec("wharf_fee", "Wharfage", "daily wharfage fee", 0, ("money", "USD", 420, 2850)),
                    AttrSpec("draft_m", "Max Draft", "maximum vessel draft", 0, ("dec_unit", "m", 6.5, 18.5)),
                    AttrSpec("pilot_fee", "Pilot Fee", "harbor pilotage fee", 0, ("money", "USD", 180, 960)),
                ),
            ),
            PageSpec(
                slug="vessel-manifest.json",
                fmt="json_pretty",
                title="Berth & Vessel Capacity Register",
                description="Draft clearances, crane lifts, and quay lengths.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="VSL",
                attrs=(
                    AttrSpec("draft_m", "Max Draft", "maximum vessel draft", 0, ("dec_unit", "m", 6.5, 18.5)),
                    AttrSpec("lift_tons", "Lift Rating", "safe working lift load", 0, ("int_unit", "tons", 35, 165)),
                    AttrSpec("quay_m", "Quay Length", "berth quay length", 2, ("int_unit", "m", 140, 480)),
                ),
            ),
            PageSpec(
                slug="crane-telemetry.json",
                fmt="json_compact",
                title="Quay Crane Telemetry Feed",
                description="Compact PLC firmware, berth occupancy, and cycle times.",
                row_placeholder=True,
                placeholder_col="req_id",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="CRN",
                attrs=(
                    AttrSpec("plc_fw", "PLC Firmware", "crane PLC firmware", 1, ("version", 1, 8)),
                    AttrSpec("berth_occ", "Occupancy", "berth occupancy rate", 1, ("percent", 45, 95)),
                    AttrSpec("cycle_sec", "Lift Cycle", "average container lift cycle", 1, ("int_unit", "s", 45, 165)),
                ),
            ),
            PageSpec(
                slug="cargo-schedule.txt",
                fmt="txt",
                title="Cargo Handling & Gate Schedule",
                description="Fixed-width turn times, container stacks, and shore power fees.",
                row_placeholder=True,
                placeholder_col="Sync Ref",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="CRG",
                attrs=(
                    AttrSpec("turn_hrs", "Turn Time", "vessel turnaround time", 1, ("int_unit", "hours", 8, 54)),
                    AttrSpec("teu_stack", "Stack Cap", "yard stack capacity", 1, ("int_unit", "TEU", 120, 960)),
                    AttrSpec("shore_fee", "Shore Power", "shore power hookup fee", 1, ("money", "USD", 95, 520)),
                ),
            ),
            PageSpec(
                slug="harbor-notices.md",
                fmt="md",
                title="Harbor Operations Notices",
                description="Wind cutoff thresholds, tidal margins, and pilotage rates.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="HBR",
                attrs=(
                    AttrSpec("wind_kt", "Wind Cutoff", "crane wind cutoff speed", 2, ("int_unit", "knots", 24, 48)),
                    AttrSpec("tide_pct", "Tide Margin", "under-keel tide margin", 2, ("percent", 8, 24)),
                    AttrSpec("pilot_fee", "Pilot Fee", "harbor pilotage fee", 0, ("money", "USD", 180, 960)),
                ),
            ),
            PageSpec(
                slug="terminal-portal.html",
                fmt="html",
                title="Terminal Facility Directory",
                description="HTML catalog of outreach spans, bollard pulls, and stack capacities.",
                row_placeholder=False,
                placeholder_col="",
                placeholder_tok="{{FETCH_ID}}",
                code_prefix="TRM",
                attrs=(
                    AttrSpec("outreach_m", "Outreach", "boom outreach span", 2, ("int_unit", "m", 28, 72)),
                    AttrSpec("bollard_t", "Bollard Pull", "bollard pull rating", 2, ("int_unit", "tons", 45, 140)),
                    AttrSpec("teu_stack", "Stack Cap", "yard stack capacity", 1, ("int_unit", "TEU", 120, 960)),
                ),
            ),
            PageSpec(
                slug="bunker-rates.txt",
                fmt="txt",
                title="Marine Bunker & Quay Table",
                description="Fixed-width bunker prices, pump rates, and quay lengths.",
                row_placeholder=True,
                placeholder_col="Audit TS",
                placeholder_tok="{{FETCH_TS}}",
                code_prefix="BNK",
                attrs=(
                    AttrSpec("bunker_fee", "Bunker Rate", "marine fuel rate", 0, ("money", "USD", 510, 890)),
                    AttrSpec("pump_rate", "Pump Rate", "bunker pumping rate", 1, ("int_unit", "tons/h", 60, 320)),
                    AttrSpec("quay_m", "Quay Length", "berth quay length", 2, ("int_unit", "m", 140, 480)),
                ),
            ),
        ),
        notices=(
            "Channel marker buoy lanterns inspected by harbor patrol.",
            "Customs gate optical scanner lenses cleaned overnight.",
            "Fender rubber bolts torqued along southern apron.",
            "VHF channel watch roster posted for weekend shift.",
            "Stormwater catch basins cleared behind Reefer Yard.",
        ),
    ),
)

DISTRACTOR_NOTES = (
    "Standard",
    "Verified",
    "Active",
    "Routine",
    "Nominal",
    "Scheduled",
    "Approved",
    "Current",
)

NOISE_CSV_NOTES = (
    "Audit pass alpha",
    "Shelf label checked",
    "Batch review logged",
    "Routine QA signoff",
    "Format sync verified",
    "Desk audit complete",
)


def gen_value(rng: random.Random, val_kind: tuple[Any, ...]) -> str:
    kind = val_kind[0]
    if kind == "money":
        _, currency, lo, hi = val_kind
        whole = rng.randint(lo, hi)
        cents = rng.choice((0, 10, 20, 25, 40, 50, 60, 75, 80, 90, 95))
        return f"{whole}.{cents:02d} {currency}"
    if kind == "int_unit":
        _, unit, lo, hi = val_kind
        val = rng.randint(lo, hi)
        return f"{val} {unit}"
    if kind == "dec_unit":
        _, unit, lo, hi = val_kind
        steps = int(round((hi - lo) * 10))
        val = lo + rng.randint(0, steps) / 10.0
        return f"{val:.1f} {unit}"
    if kind == "percent":
        _, lo, hi = val_kind
        if rng.random() < 0.45:
            return f"{rng.randint(lo, hi)}%"
        steps = int(round((hi - lo) * 10))
        val = lo + rng.randint(0, steps) / 10.0
        # Avoid trailing .0 so mix looks natural
        if abs(val - round(val)) < 1e-9:
            return f"{int(round(val))}%"
        return f"{val:.1f}%"
    if kind == "version":
        _, maj_lo, maj_hi = val_kind
        maj = rng.randint(maj_lo, maj_hi)
        minor = rng.randint(0, 14)
        patch = rng.randint(0, 19)
        return f"v{maj}.{minor}.{patch}"
    raise ValueError(f"Unknown val_kind: {val_kind}")


def gen_distinct_value(
    rng: random.Random,
    val_kind: tuple[Any, ...],
    forbidden_exact: set[str],
    forbidden_substrings: set[str] | None = None,
) -> str:
    forbidden_substrings = forbidden_substrings or set()
    for _ in range(400):
        cand = gen_value(rng, val_kind)
        if cand in forbidden_exact:
            continue
        if any(f in cand or cand in f for f in forbidden_substrings):
            continue
        return cand
    raise RuntimeError(f"Could not generate distinct value for {val_kind}")


def render_csv_page(
    page: PageSpec,
    rows: list[dict[str, str]],
) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    headers = ["item_code", "entity"] + [a.key for a in page.attrs] + ["notes"]
    if page.row_placeholder:
        headers.append(page.placeholder_col)
    writer.writerow(headers)
    for row in rows:
        vals = [row["code"], row["entity"]] + [row[a.key] for a in page.attrs] + [row["notes"]]
        if page.row_placeholder:
            vals.append(page.placeholder_tok)
        writer.writerow(vals)
    return buf.getvalue()


def render_json_pretty_page(
    page: PageSpec,
    domain_name: str,
    facility: str,
    notice: str,
    rows: list[dict[str, str]],
) -> str:
    records = []
    for row in rows:
        rec: dict[str, str] = {"code": row["code"], "entity": row["entity"]}
        for a in page.attrs:
            rec[a.key] = row[a.key]
        rec["status"] = row["notes"]
        if page.row_placeholder:
            rec[page.placeholder_col] = page.placeholder_tok
        records.append(rec)
    payload = {
        "dataset": page.slug.removesuffix(".json"),
        "title": page.title,
        "domain": domain_name,
        "facility": facility,
        "generated_at": "{{FETCH_TS}}",
        "request_id": "{{FETCH_ID}}",
        "page_views": "{{FETCH_COUNT}}",
        "editorial_note": notice,
        "records": records,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def render_json_compact_page(
    page: PageSpec,
    domain_name: str,
    facility: str,
    notice: str,
    rows: list[dict[str, str]],
) -> str:
    items = []
    for row in rows:
        rec: dict[str, str] = {"code": row["code"], "entity": row["entity"]}
        for a in page.attrs:
            rec[a.key] = row[a.key]
        rec["status"] = row["notes"]
        if page.row_placeholder:
            rec[page.placeholder_col] = page.placeholder_tok
        items.append(rec)
    payload = {
        "feed": page.slug.removesuffix(".json"),
        "domain": domain_name,
        "facility": facility,
        "generated_at": "{{FETCH_TS}}",
        "serve_count": "{{FETCH_COUNT}}",
        "bulletin": notice,
        "items": items,
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n"


def render_txt_page(
    page: PageSpec,
    facility: str,
    notice: str,
    rows: list[dict[str, str]],
) -> str:
    cols = [("code", "Code"), ("entity", "Entity")]
    for a in page.attrs:
        cols.append((a.key, a.col_title))
    cols.append(("notes", "Status"))
    if page.row_placeholder:
        cols.append(("__ph__", page.placeholder_col))

    matrix: list[list[str]] = []
    for row in rows:
        r_vals = []
        for k, _ in cols:
            if k == "__ph__":
                r_vals.append(page.placeholder_tok)
            else:
                r_vals.append(row[k])
        matrix.append(r_vals)

    widths = [len(title) for _, title in cols]
    for r_vals in matrix:
        for i, cell in enumerate(r_vals):
            if len(cell) > widths[i]:
                widths[i] = len(cell)

    def fmt_line(cells: list[str]) -> str:
        return "  ".join(cells[i].ljust(widths[i]) for i in range(len(cells))).rstrip()

    rule = "=" * max(72, sum(widths) + 2 * (len(widths) - 1))
    dash = "-" * len(rule)
    header_line = fmt_line([title for _, title in cols])
    sep_line = "  ".join("-" * w for w in widths)

    lines = [
        rule,
        f"{page.title.upper()} — {facility}",
        f"Generated: {{{{FETCH_TS}}}}    Request ID: {{{{FETCH_ID}}}}",
        f"Notice: {notice}",
        rule,
        "",
        header_line,
        sep_line,
    ]
    for r_vals in matrix:
        lines.append(fmt_line(r_vals))
    lines.extend([
        "",
        dash,
        f"Page views: {{{{FETCH_COUNT}}}}",
    ])
    return "\n".join(lines) + "\n"


def render_md_page(
    page: PageSpec,
    facility: str,
    notice: str,
    rows: list[dict[str, str]],
) -> str:
    headers = ["Code", "Entity"] + [a.col_title for a in page.attrs] + ["Status"]
    if page.row_placeholder:
        headers.append(page.placeholder_col)
    lines = [
        f"# {page.title}",
        "",
        f"> Facility: {facility} | Snapshot: `{{{{FETCH_TS}}}}` | Request: `{{{{FETCH_ID}}}}`",
        "",
        f"Operational notice: {notice}",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        cells = [row["code"], row["entity"]] + [row[a.key] for a in page.attrs] + [row["notes"]]
        if page.row_placeholder:
            cells.append(page.placeholder_tok)
        lines.append("| " + " | ".join(cells) + " |")
    lines.extend([
        "",
        f"_Page views: {{{{FETCH_COUNT}}}}_",
    ])
    return "\n".join(lines) + "\n"


def render_html_page(
    page: PageSpec,
    facility: str,
    notice: str,
    rows: list[dict[str, str]],
) -> str:
    headers = ["Code", "Entity"] + [a.col_title for a in page.attrs] + ["Status"]
    if page.row_placeholder:
        headers.append(page.placeholder_col)
    th_html = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    tr_lines = []
    for row in rows:
        cells = [row["code"], row["entity"]] + [row[a.key] for a in page.attrs] + [row["notes"]]
        if page.row_placeholder:
            cells.append(page.placeholder_tok)
        tds = "".join(f"<td>{html.escape(c)}</td>" for c in cells)
        tr_lines.append(f"      <tr>{tds}</tr>")

    body_rows = "\n".join(tr_lines)
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        f"  <title>{html.escape(page.title)} — {html.escape(facility)}</title>\n"
        "</head>\n"
        "<body>\n"
        f"  <h1>{html.escape(page.title)}</h1>\n"
        f"  <p class=\"meta\">Facility: {html.escape(facility)} | Rendered: {{{{FETCH_TS}}}} | Req: {{{{FETCH_ID}}}}</p>\n"
        f"  <p class=\"notice\">Notice: {html.escape(notice)}</p>\n"
        "  <table>\n"
        "    <thead>\n"
        f"      <tr>{th_html}</tr>\n"
        "    </thead>\n"
        "    <tbody>\n"
        f"{body_rows}\n"
        "    </tbody>\n"
        "  </table>\n"
        "  <footer>Page views: {{FETCH_COUNT}}</footer>\n"
        "</body>\n"
        "</html>\n"
    )


def render_index_page(
    index_name: str,
    site_title: str,
    facility: str,
    active_pages: list[PageSpec],
) -> str:
    if index_name.endswith(".html"):
        items = []
        for p in active_pages:
            ext = Path(p.slug).suffix.lstrip(".").upper()
            items.append(
                f"    <li><a href=\"{html.escape(p.slug)}\">{html.escape(p.title)}</a> "
                f"({ext}) — {html.escape(p.description)}</li>"
            )
        items_html = "\n".join(items)
        return (
            "<!DOCTYPE html>\n"
            "<html lang=\"en\">\n"
            "<head>\n"
            "  <meta charset=\"utf-8\">\n"
            f"  <title>{html.escape(site_title)} — {html.escape(facility)}</title>\n"
            "</head>\n"
            "<body>\n"
            f"  <h1>{html.escape(site_title)}</h1>\n"
            f"  <p class=\"meta\">Division: {html.escape(facility)} | Snapshot: {{{{FETCH_TS}}}} | Request: {{{{FETCH_ID}}}}</p>\n"
            "  <p>Select a data feed or reference table below:</p>\n"
            "  <ul>\n"
            f"{items_html}\n"
            "  </ul>\n"
            "  <footer>Page views: {{FETCH_COUNT}}</footer>\n"
            "</body>\n"
            "</html>\n"
        )
    else:
        lines = [
            f"# {site_title}",
            "",
            f"> Division: {facility} | Snapshot: `{{{{FETCH_TS}}}}` | Request: `{{{{FETCH_ID}}}}`",
            "",
            "Available datasets and reference pages:",
            "",
        ]
        for p in active_pages:
            ext = Path(p.slug).suffix.lstrip(".").upper()
            lines.append(f"- [{p.title}]({p.slug}) ({ext}) — {p.description}")
        lines.extend([
            "",
            "_Page views: {{FETCH_COUNT}}_",
        ])
        return "\n".join(lines) + "\n"


def render_content_page(
    page: PageSpec,
    domain_name: str,
    facility: str,
    notice: str,
    rows: list[dict[str, str]],
) -> str:
    if page.fmt == "csv":
        return render_csv_page(page, rows)
    if page.fmt == "json_pretty":
        return render_json_pretty_page(page, domain_name, facility, notice, rows)
    if page.fmt == "json_compact":
        return render_json_compact_page(page, domain_name, facility, notice, rows)
    if page.fmt == "txt":
        return render_txt_page(page, facility, notice, rows)
    if page.fmt == "md":
        return render_md_page(page, facility, notice, rows)
    if page.fmt == "html":
        return render_html_page(page, facility, notice, rows)
    raise ValueError(f"Unknown format: {page.fmt}")


def build_set(set_idx: int, seed: int, out_dir: Path) -> dict[str, Any]:
    rng = random.Random(seed * 1_000_003 + set_idx * 9176 + 17)
    set_id = f"s{set_idx:02d}"

    dom = DOMAINS[(set_idx - 1) % len(DOMAINS)]
    variant_idx = ((set_idx - 1) // len(DOMAINS)) % len(dom.facility_variants)
    facility = dom.facility_variants[variant_idx]
    if (set_idx - 1) >= len(DOMAINS) * len(dom.facility_variants):
        facility = f"{facility} Sector {(set_idx - 1) // len(DOMAINS) + 1}"

    # Decide 6 or 7 content pages (all 6 core pages cover csv, json_pretty, json_compact, txt, md, html)
    use_seventh = (set_idx % 2 == 1)
    active_pages: list[PageSpec] = list(dom.pages[:6])
    if use_seventh:
        active_pages.append(dom.pages[6])

    # Vary index between index.html and index.md
    index_name = "index.html" if (set_idx + seed) % 2 == 0 else "index.md"

    # Build entity pool: 11 claimed entities + 12 distractors (first 7 are near-identical twins!)
    clean_bases = list(dom.entity_bases)
    rng.shuffle(clean_bases)
    claimed_entities = clean_bases[:11]
    extra_distractors = clean_bases[11:16]

    twins: list[str] = []
    used_names = set(claimed_entities) | set(extra_distractors)
    for i in range(7):
        base = claimed_entities[i]
        suf = dom.twin_suffixes[i % len(dom.twin_suffixes)]
        twin_name = f"{base}{suf}"
        if twin_name in used_names:
            twin_name = f"{base} V2"
        twins.append(twin_name)
        used_names.add(twin_name)

    distractor_entities = twins + extra_distractors  # 12 distractors
    all_entities = claimed_entities + distractor_entities

    # Map attr key -> AttrSpec
    attr_by_key: dict[str, AttrSpec] = {}
    for p in active_pages:
        for a in p.attrs:
            attr_by_key[a.key] = a

    # Page attribute shortcuts:
    # p0: [a0, a1, a2] (csv, row_ph=True)
    # p1: [a1, a3, a4] (json_pretty, row_ph=False)  shares a1 with p0
    # p2: [a5, a6, a7] (json_compact, row_ph=True)
    # p3: [a8, a9, a10] (txt, row_ph=True)
    # p4: [a11, a12, a2] (md, row_ph=False)         shares a2 with p0
    # p5: [a13, a14, a9] (html, row_ph=False)       shares a9 with p3
    # p6 (optional): [a15, a16, a4] (csv/txt, row_ph=True) shares a4 with p1
    p0, p1, p2, p3, p4, p5 = active_pages[:6]
    a0, a1, a2 = p0.attrs[0].key, p0.attrs[1].key, p0.attrs[2].key
    a3, a4 = p1.attrs[1].key, p1.attrs[2].key
    a5, a6, a7 = p2.attrs[0].key, p2.attrs[1].key, p2.attrs[2].key
    a8, a9, a10 = p3.attrs[0].key, p3.attrs[1].key, p3.attrs[2].key
    a11, a12 = p4.attrs[0].key, p4.attrs[1].key
    a13, a14 = p5.attrs[0].key, p5.attrs[1].key

    # Assign page memberships for each claimed entity E0..E10 carefully so
    # each claim's source_pages is exact and split-fact structure is clean.
    # Multi-claim entities: E0(3), E1(3), E2(2), E3(2), E4(2), E5(2), E6(2) -> 5/7 = 71.4% split!
    # Single-claim entities: E7(1), E8(1), E9(1), E10(1)
    entity_pages: dict[str, set[str]] = {
        claimed_entities[0]: {p0.slug, p1.slug, p2.slug, p3.slug},      # E0: split + replicated
        claimed_entities[1]: {p0.slug, p1.slug, p2.slug, p3.slug, p5.slug},  # E1: split + 2 replicated
        claimed_entities[2]: {p0.slug, p1.slug},                        # E2: split (p0 vs p1)
        claimed_entities[3]: {p2.slug, p3.slug},                        # E3: split (p2 vs p3)
        claimed_entities[4]: {p4.slug, p5.slug},                        # E4: split (p4 vs p5)
        claimed_entities[5]: {p2.slug},                                 # E5: same page (p2)
        claimed_entities[6]: {p4.slug},                                 # E6: same page (p4)
        claimed_entities[7]: {active_pages[6].slug if use_seventh else p0.slug},  # E7: single
        claimed_entities[8]: {p3.slug},                                 # E8: single
        claimed_entities[9]: {p5.slug},                                 # E9: single
        claimed_entities[10]: {p0.slug, p4.slug},                       # E10: replicated (p0, p4)
    }

    e7_attr = active_pages[6].attrs[0].key if use_seventh else a0

    # Define the 20 raw claims: (entity, attr_key)
    raw_claims: list[tuple[str, str]] = [
        # Replicated structured (2)
        (claimed_entities[0], a1),   # [p0, p1]
        (claimed_entities[1], a1),   # [p0, p1]
        # Single-page structured (11)
        (claimed_entities[0], a5),   # [p2]
        (claimed_entities[0], a8),   # [p3]
        (claimed_entities[1], a6),   # [p2]
        (claimed_entities[2], a0),   # [p0]
        (claimed_entities[2], a3),   # [p1]
        (claimed_entities[3], a5),   # [p2]
        (claimed_entities[3], a8),   # [p3]
        (claimed_entities[5], a6),   # [p2]
        (claimed_entities[5], a7),   # [p2]
        (claimed_entities[7], e7_attr),  # [p6 or p0]
        (claimed_entities[8], a10),  # [p3]
        # Mixed / md / html (7)
        (claimed_entities[1], a9),   # [p3, p5] replicated mixed
        (claimed_entities[4], a11),  # [p4]
        (claimed_entities[4], a13),  # [p5]
        (claimed_entities[6], a11),  # [p4]
        (claimed_entities[6], a12),  # [p4]
        (claimed_entities[9], a14),  # [p5]
        (claimed_entities[10], a2),  # [p0, p4] replicated mixed
    ]

    # Sort claims by template group_idx so template.md groups are neat, preserving determinism
    raw_claims.sort(key=lambda pair: (attr_by_key[pair[1]].group_idx, pair[0], pair[1]))

    # Compute exact source_pages for each claim from entity_pages + page.attrs
    page_by_slug = {p.slug: p for p in active_pages}
    page_attr_keys = {p.slug: {a.key for a in p.attrs} for p in active_pages}

    claim_defs: list[dict[str, Any]] = []
    for idx, (ent, akey) in enumerate(raw_claims, start=1):
        cid = f"c{idx:02d}"
        aspec = attr_by_key[akey]
        src_pages = [
            p.slug for p in active_pages
            if p.slug in entity_pages[ent] and akey in page_attr_keys[p.slug]
        ]
        assert src_pages, f"No source pages for {(ent, akey)}"
        claim_defs.append({
            "id": cid,
            "entity": ent,
            "attr_key": akey,
            "label": aspec.label,
            "group_idx": aspec.group_idx,
            "template_line": f"- {ent} \u2014 {aspec.label}: ",
            "source_pages": src_pages,
        })

    # Place distractor entities on pages:
    # - Put each twin D0..D6 on the EXACT same pages as its claimed twin E0..E6
    # - Distribute extra distractors D7..D11 so every page has 8..11 total rows and >= 4 distractors
    page_entities: dict[str, list[str]] = {p.slug: [] for p in active_pages}
    for ent in claimed_entities:
        for slug in sorted(entity_pages[ent]):
            page_entities[slug].append(ent)
    for i in range(7):
        twin = twins[i]
        for slug in sorted(entity_pages[claimed_entities[i]]):
            page_entities[slug].append(twin)
    # Add extra distractors to every page so every page has plenty of distractors
    for p_idx, p in enumerate(active_pages):
        # Rotate extra distractors + borrow a couple of unused twins so every page has >= 4 distractors
        candidates = extra_distractors + [t for t in twins if t not in page_entities[p.slug]]
        for d in candidates:
            if len(page_entities[p.slug]) >= 10:
                break
            if d not in page_entities[p.slug]:
                page_entities[p.slug].append(d)
        rng.shuffle(page_entities[p.slug])

    # Assign stable item codes per (page, entity)
    item_codes: dict[tuple[str, str], str] = {}
    for p in active_pages:
        for row_i, ent in enumerate(page_entities[p.slug], start=101):
            item_codes[(p.slug, ent)] = f"{p.code_prefix}-{row_i}"

    # Assign cycle schedule (permutation of F, F, N, Z)
    cycle_types = list(CYCLE_TYPES_MULTISET)
    rng.shuffle(cycle_types)

    # Pick 4 changing claims (2 per F cycle):
    # Ensure at least 1 replicated claim is among the 4 changing claims, and that
    # for each F cycle there is at least 1 content page NOT in the 2 claims' source_pages.
    replicated_cids = [c["id"] for c in claim_defs if len(c["source_pages"]) >= 2]
    single_cids = [c["id"] for c in claim_defs if len(c["source_pages"]) == 1]
    rng.shuffle(replicated_cids)
    rng.shuffle(single_cids)

    changing_pool = [replicated_cids[0]] + single_cids[:3]
    rng.shuffle(changing_pool)
    f_pairs = [changing_pool[:2], changing_pool[2:4]]
    changing_set = set(changing_pool)

    # Verify each F pair leaves at least 1 page free for noise_page
    claim_by_id = {c["id"]: c for c in claim_defs}
    all_page_slugs = [p.slug for p in active_pages]

    cycles_meta: list[dict[str, Any]] = []
    f_idx = 0
    for cyc_num, ctype in enumerate(cycle_types, start=1):
        if ctype == "Z":
            cycles_meta.append({
                "cycle": cyc_num,
                "type": "Z",
                "changed_claims": [],
                "noise_pages": [],
            })
        elif ctype == "N":
            n_noise = rng.choice((1, 2))
            noise_pages = sorted(rng.sample(all_page_slugs, n_noise))
            cycles_meta.append({
                "cycle": cyc_num,
                "type": "N",
                "changed_claims": [],
                "noise_pages": noise_pages,
            })
        else:  # "F"
            cids = sorted(f_pairs[f_idx])
            f_idx += 1
            touched = set()
            for cid in cids:
                touched.update(claim_by_id[cid]["source_pages"])
            free_pages = [s for s in all_page_slugs if s not in touched]
            assert free_pages, "No free page for F-cycle noise edit"
            noise_page = rng.choice(free_pages)
            cycles_meta.append({
                "cycle": cyc_num,
                "type": "F",
                "changed_claims": cids,
                "noise_pages": [noise_page],
            })

    # Choose 12 of the 16 non-changing claims for Requirement #2 (same value, same page, different item)
    non_changing_cids = [c["id"] for c in claim_defs if c["id"] not in changing_set]
    rng.shuffle(non_changing_cids)
    dup_cids = set(non_changing_cids[:12])  # 12/20 = 60%

    # Generate initial cycle-0 values for every (entity, attr_key) that appears on any page
    ent_attr_vals: dict[tuple[str, str], str] = {}
    for p in active_pages:
        for ent in page_entities[p.slug]:
            for a in p.attrs:
                if (ent, a.key) not in ent_attr_vals:
                    ent_attr_vals[(ent, a.key)] = gen_value(rng, a.val_kind)

    # First pick old_val and new_val for the 4 changing claims so they never collide with each other
    changed_new_vals: dict[str, str] = {}
    all_changing_old_vals: set[str] = set()
    all_changing_new_vals: set[str] = set()
    for cid in changing_pool:
        c = claim_by_id[cid]
        aspec = attr_by_key[c["attr_key"]]
        # Pick clean old_val and new_val with no mutual substring collision
        old_v = gen_distinct_value(
            rng, aspec.val_kind,
            forbidden_exact=all_changing_old_vals | all_changing_new_vals,
            forbidden_substrings=all_changing_old_vals | all_changing_new_vals,
        )
        all_changing_old_vals.add(old_v)
        ent_attr_vals[(c["entity"], c["attr_key"])] = old_v

    for cid in changing_pool:
        c = claim_by_id[cid]
        aspec = attr_by_key[c["attr_key"]]
        new_v = gen_distinct_value(
            rng, aspec.val_kind,
            forbidden_exact=all_changing_old_vals | all_changing_new_vals,
            forbidden_substrings=all_changing_old_vals,
        )
        all_changing_new_vals.add(new_v)
        changed_new_vals[cid] = new_v

    # Ensure NO other (entity, attr_key) value on ANY page collides with ANY changing claim's old_val
    # (even as a substring, e.g. "5 kg" inside "15 kg")!
    changing_pairs = {(claim_by_id[cid]["entity"], claim_by_id[cid]["attr_key"]) for cid in changing_pool}
    for (ent, akey), val in list(ent_attr_vals.items()):
        if (ent, akey) in changing_pairs:
            continue
        if any(old_v in val or val in old_v for old_v in all_changing_old_vals):
            aspec = attr_by_key[akey]
            ent_attr_vals[(ent, akey)] = gen_distinct_value(
                rng, aspec.val_kind,
                forbidden_exact=all_changing_old_vals,
                forbidden_substrings=all_changing_old_vals,
            )

    # Now apply Requirement #2: for each claim in dup_cids, copy its exact value onto a
    # distractor entity on its primary source page (different item, same page, same attribute)!
    claimed_entity_set = set(claimed_entities)
    used_donor_slots: set[tuple[str, str]] = set()
    for cid in sorted(dup_cids):
        c = claim_by_id[cid]
        val = ent_attr_vals[(c["entity"], c["attr_key"])]
        target_slug = c["source_pages"][0]
        # Prefer a distractor entity on target_slug whose (ent, attr_key) isn't already a donor
        distractors_on_page = [e for e in page_entities[target_slug] if e not in claimed_entity_set]
        donor = None
        for d in distractors_on_page:
            if (d, c["attr_key"]) not in used_donor_slots:
                donor = d
                break
        if donor is None and distractors_on_page:
            donor = distractors_on_page[0]
        assert donor is not None, f"No distractor on {target_slug} for dup {cid}"
        # Since c is non-changing, val does not collide with all_changing_old_vals
        ent_attr_vals[(donor, c["attr_key"])] = val
        used_donor_slots.add((donor, c["attr_key"]))

    # Prepare base notes per (page, entity) and per-page notice text
    row_notes: dict[tuple[str, str], str] = {}
    for p in active_pages:
        for ent in page_entities[p.slug]:
            row_notes[(p.slug, ent)] = rng.choice(DISTRACTOR_NOTES)

    # Pick one designated distractor entity per CSV page to carry unrelated CSV note edits
    csv_noise_target: dict[str, str] = {}
    for p in active_pages:
        if p.fmt == "csv":
            d_list = [e for e in page_entities[p.slug] if e not in claimed_entity_set]
            csv_noise_target[p.slug] = d_list[0]

    page_notice: dict[str, str] = {}
    for p_idx, p in enumerate(active_pages):
        page_notice[p.slug] = dom.notices[p_idx % len(dom.notices)]

    # Render cycle 0..4 sites, compute truth[0..4] and page_sha256[0..4]
    set_dir = out_dir / "sets" / set_id
    set_dir.mkdir(parents=True, exist_ok=True)

    index_content = render_index_page(index_name, dom.site_title, facility, active_pages)
    index_bytes = index_content.encode("utf-8")
    index_sha = hashlib.sha256(index_bytes).hexdigest()

    truth_cycles: list[dict[str, str]] = []
    sha_cycles: list[dict[str, str]] = []
    # Keep track of cycle 0..4 state
    current_vals = dict(ent_attr_vals)
    current_notices = dict(page_notice)
    current_row_notes = dict(row_notes)
    changed_so_far: dict[str, str] = {}  # cid -> old_val

    for k in range(5):
        if k >= 1:
            cmeta = cycles_meta[k - 1]
            # Apply claim changes
            for cid in cmeta["changed_claims"]:
                c = claim_by_id[cid]
                old_v = current_vals[(c["entity"], c["attr_key"])]
                new_v = changed_new_vals[cid]
                assert new_v != old_v
                changed_so_far[cid] = old_v
                current_vals[(c["entity"], c["attr_key"])] = new_v
            # Apply unrelated noise edits
            for nslug in cmeta["noise_pages"]:
                pspec = page_by_slug[nslug]
                if pspec.fmt == "csv":
                    target_ent = csv_noise_target[nslug]
                    base_note = NOISE_CSV_NOTES[(k + set_idx) % len(NOISE_CSV_NOTES)]
                    current_row_notes[(nslug, target_ent)] = f"{base_note} (rev {k})"
                else:
                    base_msg = dom.notices[(k + set_idx) % len(dom.notices)]
                    current_notices[nslug] = f"{base_msg} [Audit log rev {k}]"

        # Record truth at cycle k
        t_k = {
            c["id"]: current_vals[(c["entity"], c["attr_key"])]
            for c in claim_defs
        }
        truth_cycles.append(t_k)

        site_dir = set_dir / f"cycle_{k}" / "site"
        site_dir.mkdir(parents=True, exist_ok=True)

        # Write index
        (site_dir / index_name).write_bytes(index_bytes)
        sha_k: dict[str, str] = {index_name: index_sha}

        # Render & write each content page
        rendered_pages: dict[str, str] = {}
        for p in active_pages:
            rows = []
            for ent in page_entities[p.slug]:
                r: dict[str, str] = {
                    "code": item_codes[(p.slug, ent)],
                    "entity": ent,
                    "notes": current_row_notes[(p.slug, ent)],
                }
                for a in p.attrs:
                    r[a.key] = current_vals[(ent, a.key)]
                rows.append(r)
            text = render_content_page(p, dom.domain, facility, current_notices[p.slug], rows)
            rendered_pages[p.slug] = text
            raw_bytes = text.encode("utf-8")
            (site_dir / p.slug).write_bytes(raw_bytes)
            sha_k[p.slug] = hashlib.sha256(raw_bytes).hexdigest()

        # Internal invariant assertions at cycle k
        for c in claim_defs:
            val = t_k[c["id"]]
            for slug in c["source_pages"]:
                assert val in rendered_pages[slug], f"{set_id} c{k}: {val!r} missing from {slug}"
            if c["id"] in changed_so_far:
                old_v = changed_so_far[c["id"]]
                for slug in c["source_pages"]:
                    assert old_v not in rendered_pages[slug], (
                        f"{set_id} cycle {k}: old value {old_v!r} still present in {slug}"
                    )

        sha_cycles.append(dict(sorted(sha_k.items())))

    # Write template.md
    tmpl_lines = [
        f"# {dom.report_title} ({facility}) — Verification Report",
        "",
        "Fill each blank with the exact value string as written on the source site.",
    ]
    current_group = -1
    for c in claim_defs:
        if c["group_idx"] != current_group:
            current_group = c["group_idx"]
            tmpl_lines.append("")
            tmpl_lines.append(f"## {dom.groups[current_group]}")
        tmpl_lines.append(f"{c['template_line']}____")
    template_text = "\n".join(tmpl_lines) + "\n"
    (set_dir / "template.md").write_text(template_text, encoding="utf-8")

    # Build set manifest entry
    manifest_claims = [
        {
            "id": c["id"],
            "entity": c["entity"],
            "label": c["label"],
            "template_line": c["template_line"],
            "source_pages": c["source_pages"],
        }
        for c in claim_defs
    ]

    return {
        "set": set_id,
        "domain": dom.domain,
        "index": index_name,
        "pages": [p.slug for p in active_pages],
        "claims": manifest_claims,
        "truth": truth_cycles,
        "cycles": cycles_meta,
        "page_sha256": sha_cycles,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate synthetic multi-format heldout-v3 benchmark sets."
    )
    parser.add_argument("--seed", type=int, required=True, help="Deterministic integer RNG seed.")
    parser.add_argument("--sets", type=int, required=True, help="Number of sets to generate (>= 1).")
    parser.add_argument("--out", type=Path, required=True, help="Output directory (must be empty or non-existent).")
    args = parser.parse_args(argv)

    if args.sets < 1:
        print("Error: --sets must be >= 1", file=sys.stderr)
        return 1

    out_dir: Path = args.out
    if out_dir.exists():
        if not out_dir.is_dir():
            print(f"Error: output path exists and is not a directory: {out_dir}", file=sys.stderr)
            return 1
        if any(out_dir.iterdir()):
            print(f"Error: refusing to write into non-empty directory: {out_dir}", file=sys.stderr)
            return 1
    else:
        out_dir.mkdir(parents=True, exist_ok=True)

    sets_entries = [build_set(i, args.seed, out_dir) for i in range(1, args.sets + 1)]

    manifest = {
        "schema": SCHEMA_VERSION,
        "generator": GENERATOR_NAME,
        "seed": args.seed,
        "n_sets": args.sets,
        "cycle_types": CYCLE_TYPES_MULTISET,
        "sets": sets_entries,
    }

    manifest_bytes = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    (out_dir / "manifest.json").write_bytes(manifest_bytes)
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    (out_dir / "manifest.sha256").write_text(f"{manifest_digest}\n", encoding="utf-8")

    print(f"Generated {args.sets} set(s) (seed={args.seed}) in {out_dir}")
    print(f"manifest.sha256: {manifest_digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
