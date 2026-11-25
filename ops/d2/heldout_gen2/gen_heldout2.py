#!/usr/bin/env python3
"""Generate heldout-v2 benchmark sets with harder document-extraction properties.

CLI:
    python3 gen_heldout2.py --seed <int> --sets <N> --out <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "vacant.d2.manifest/1"
GENERATOR_NAME = "heldout-v2"
CYCLE_TYPES_BASE = ["F", "F", "N", "Z"]


@dataclass(frozen=True)
class EntitySpec:
    name: str
    nickname: str
    descriptor: str
    ordinal: str
    subj: str
    poss: str
    kind: str


@dataclass(frozen=True)
class AttrSpec:
    label: str
    unit_kind: str
    context_noun: str
    direct_templates: tuple[str, ...]
    indirect_heading_templates: tuple[str, ...]
    anaphora_leads: tuple[str, ...]
    anaphora_follows: tuple[str, ...]
    nickname_templates: tuple[str, ...]
    ordinal_templates: tuple[str, ...]


@dataclass(frozen=True)
class PageSpec:
    filename: str
    title: str
    role: str  # manual, dossier, dispatch, tariffs, telemetry, advisory, audit
    is_long: bool


@dataclass(frozen=True)
class DomainSpec:
    domain_id: str
    title: str
    authority: str
    region: str
    entities: tuple[EntitySpec, ...]
    pages: tuple[PageSpec, ...]
    attrs: tuple[AttrSpec, ...]
    background_topics: tuple[str, ...]
    distractor_subjects: dict[str, tuple[str, ...]]
    noise_notes: tuple[str, ...]


# ---------------------------------------------------------------------------
# Value generation & formatting (strictly 1 number or 1 version string)
# ---------------------------------------------------------------------------

def _gen_raw_value(unit_kind: str, rng: random.Random) -> tuple[str, Any]:
    """Return (formatted_value, core_key) where core_key identifies numeric/version value."""
    if unit_kind == "km":
        if rng.random() < 0.45:
            n = rng.randint(4, 85)
            return f"{n} km", ("num", float(n))
        v = round(rng.randint(35, 640) / 10.0, 1)
        if v.is_integer():
            v += 0.5
        return f"{v:.1f} km", ("num", v)
    if unit_kind == "m":
        if rng.random() < 0.65:
            n = rng.randint(14, 980)
            return f"{n} m", ("num", float(n))
        v = round(rng.randint(45, 295) / 10.0, 1)
        if v.is_integer():
            v += 0.5
        return f"{v:.1f} m", ("num", v)
    if unit_kind == "kW":
        n = rng.randint(12, 95) * 10
        return f"{n} kW", ("num", float(n))
    if unit_kind == "MW":
        v = round(rng.randint(15, 245) / 10.0, 1)
        if v.is_integer():
            v += 0.5
        return f"{v:.1f} MW", ("num", v)
    if unit_kind == "usd":
        if rng.random() < 0.7:
            dollars = rng.randint(6, 95)
            cents = rng.choice([0, 25, 50, 75])
            v = dollars + cents / 100.0
            return f"${v:.2f}", ("num", v)
        n = rng.randint(110, 890)
        return f"${n}", ("num", float(n))
    if unit_kind == "eur":
        euros = rng.randint(8, 85)
        cents = rng.choice([0, 20, 50, 80])
        v = euros + cents / 100.0
        return f"€{v:.2f}", ("num", v)
    if unit_kind == "pct":
        if rng.random() < 0.6:
            n = rng.randint(12, 96)
            return f"{n}%", ("num", float(n))
        v = round(rng.randint(185, 985) / 10.0, 1)
        if v.is_integer():
            v += 0.5
        return f"{v:.1f}%", ("num", v)
    if unit_kind == "min":
        n = rng.randint(8, 95)
        return f"{n} min", ("num", float(n))
    if unit_kind == "hr":
        v = round(rng.randint(15, 185) / 10.0, 1)
        if v.is_integer():
            v += 0.5
        return f"{v:.1f} hr", ("num", v)
    if unit_kind == "L":
        n = rng.randint(12, 98) * 10
        return f"{n} L", ("num", float(n))
    if unit_kind == "L_min":
        n = rng.randint(45, 680)
        return f"{n} L/min", ("num", float(n))
    if unit_kind == "knots":
        v = round(rng.randint(85, 285) / 10.0, 1)
        if v.is_integer():
            v += 0.5
        return f"{v:.1f} knots", ("num", v)
    if unit_kind == "kmh":
        n = rng.randint(25, 145)
        return f"{n} km/h", ("num", float(n))
    if unit_kind == "bar":
        v = round(rng.randint(18, 125) / 10.0, 1)
        if v.is_integer():
            v += 0.5
        return f"{v:.1f} bar", ("num", v)
    if unit_kind == "temp_c":
        v = round(rng.randint(45, 295) / 10.0, 1)
        if v.is_integer():
            v += 0.5
        return f"{v:.1f} C", ("num", v)
    if unit_kind == "tons":
        n = rng.randint(18, 480)
        return f"{n} tons", ("num", float(n))
    if unit_kind == "bays":
        n = rng.randint(4, 38)
        return f"{n} bays", ("num", float(n))
    if unit_kind == "units":
        n = rng.randint(6, 72)
        return f"{n} units", ("num", float(n))
    if unit_kind == "version":
        maj = rng.randint(1, 5)
        min_ = rng.randint(0, 14)
        pat = rng.randint(0, 9)
        return f"v{maj}.{min_}.{pat}", ("ver", (maj, min_, pat))
    raise ValueError(f"Unknown unit_kind: {unit_kind}")


def gen_unique_value(
    unit_kind: str,
    rng: random.Random,
    forbidden_strings: set[str],
    forbidden_cores: set[Any] | None = None,
) -> tuple[str, Any]:
    """Generate a value of unit_kind not in forbidden_strings or forbidden_cores."""
    for _ in range(500):
        val, core = _gen_raw_value(unit_kind, rng)
        if val in forbidden_strings:
            continue
        if forbidden_cores is not None and (unit_kind, core) in forbidden_cores:
            continue
        return val, core
    raise RuntimeError(f"Could not find unique value for {unit_kind}")


# ---------------------------------------------------------------------------
# Generic attribute template builder (ensures varied natural sentences)
# ---------------------------------------------------------------------------

def _indef(phrase: str) -> str:
    return "an" if phrase[:1].lower() in "aeiou" else "a"


def make_attr(label: str, unit_kind: str, context_noun: str) -> AttrSpec:
    art = _indef(label)
    return AttrSpec(
        label=label,
        unit_kind=unit_kind,
        context_noun=context_noun,
        direct_templates=(
            f"Current operating sheets list {{entity}} with {label} set to {{val}} during standard duty.",
            f"According to the latest field ledger, {{entity}} carries a verified {label} of {{val}}.",
            f"Updated district filings list the {label} for {{entity}} at {{val}} under normal conditions.",
            f"Operational sign-off confirms that {{entity}} maintains {art} {label} of {{val}} this quarter.",
        ),
        indirect_heading_templates=(
            f"Under normal operating conditions, {{poss}} {label} stands at {{val}} across scheduled shifts.",
            f"Field audits recorded {{poss}} active {label} at {{val}} during the latest review window.",
            f"In regular service, {{subj}} operates with {label} held at {{val}} before seasonal adjustments.",
            f"Engineering sign-off places {{poss}} baseline {label} at {{val}} for routine planning.",
        ),
        anaphora_leads=(
            f"Supervisors reviewed the quarterly {context_noun} dossier for {{entity}} earlier this month.",
            f"Technical staff completed a full verification of {{entity}} ahead of the upcoming operating cycle.",
            f"Recent dispatch records highlighted updated {context_noun} parameters for {{entity}}.",
        ),
        anaphora_follows=(
            f"Under the current schedule, {{descriptor}} maintains {art} {label} of {{val}}.",
            f"Based on those measurements, {{poss}} {label} is held at {{val}} throughout normal shifts.",
            f"Following the review, {{subj}} remains calibrated with {label} at {{val}}.",
        ),
        nickname_templates=(
            f"{{nick}}: current {label} is logged at {{val}} on active operating charts.",
            f"{{nick}}: verified {label} stands at {{val}} in the latest dispatch register.",
            f"{{nick}}: baseline {label} remains set to {{val}} under standard rules.",
        ),
        ordinal_templates=(
            f"For {{ordinal}}, planners budget {art} {label} of {{val}} under standard operating rules.",
            f"Across {{ordinal}}, the latest field sheet reports {label} at {{val}}.",
            f"At {{ordinal}}, routine inspections confirm {art} {label} of {{val}} for this season.",
        ),
    )


# ---------------------------------------------------------------------------
# Rich domain library (8 distinct operational domains)
# ---------------------------------------------------------------------------

def _build_domains() -> tuple[DomainSpec, ...]:
    common_distractors: dict[str, tuple[str, ...]] = {
        "km": (
            "the outer perimeter patrol loop",
            "the decommissioned coastal survey transect",
            "the backup fiber conduit along the ridge",
            "the regional courier haul between depots",
            "the emergency bypass diversion corridor",
            "the legacy telemetry relay span",
        ),
        "m": (
            "the outer retaining seawall section",
            "the secondary drainage culvert",
            "the historical test trench",
            "the perimeter fence setback",
            "the temporary crane boom clearance",
            "the standby antenna mast height",
        ),
        "kW": (
            "the standby workshop compressor bank",
            "the administrative lighting feeder",
            "the retired test-bench load bank",
            "the auxiliary heating circuit in the warehouse",
            "the portable maintenance generator",
            "the courtyard charging bus",
        ),
        "MW": (
            "the regional tie-line reserve allocation",
            "the decommissioned peaking block",
            "the neighboring municipal intertie",
            "the winter contingency import cap",
            "the historical peak load benchmark",
            "the test substation transformer rating",
        ),
        "usd": (
            "the external contractor filing fee",
            "the duplicate badge replacement charge",
            "the archive print copy surcharge",
            "the weekend visitor parking pass",
            "the temporary equipment locker rental",
            "the off-hours courier handling fee",
        ),
        "eur": (
            "the regional inspection stamp fee",
            "the external document certification tariff",
            "the visiting vehicle day permit",
            "the manual customs dossier charge",
            "the short-term storage locker fee",
            "the standard courier surcharge",
        ),
        "pct": (
            "the five-year regional rainfall anomaly",
            "the archive digitization completion share",
            "the contractor safety briefing attendance",
            "the spare-parts shelf turnover ratio",
            "the nighttime acoustic dampening factor",
            "the baseline humidity reading in storage",
        ),
        "min": (
            "the lobby security badge verification window",
            "the shift handover briefing duration",
            "the automated backup tape rotation cycle",
            "the courtyard gate lockout interval",
            "the weekly siren test duration",
            "the radio channel roll-call window",
        ),
        "hr": (
            "the archival tape retention warm-up period",
            "the training simulator block duration",
            "the routine concrete curing hold",
            "the weekend depot quiet-hours span",
            "the battery bench conditioning test",
            "the scheduled calibration soak period",
        ),
        "L": (
            "the washbay rainwater recovery barrel",
            "the workshop parts-washer sump",
            "the calibration fluid reference drum",
            "the auxiliary lubricant transfer tote",
            "the emergency spill-kit foam tank",
            "the greenhouse irrigation buffer vat",
        ),
        "L_min": (
            "the courtyard fire-hydrant flush test",
            "the washdown hose manifold discharge",
            "the laboratory chiller return loop",
            "the stormwater sump pump benchmark",
            "the test-stand bypass flow rate",
            "the emergency eyewash header output",
        ),
        "knots": (
            "the outer buoy spring-tide drift",
            "the autumn gale gust threshold",
            "the pilot launch harbor transit cap",
            "the historical channel current peak",
            "the acoustic survey tow speed",
            "the coastal patrol skiff cruise limit",
        ),
        "kmh": (
            "the service access road speed limit",
            "the valley crosswind warning threshold",
            "the maintenance hi-rail vehicle cap",
            "the historical storm gust reading",
            "the yard shunting caution limit",
            "the perimeter patrol van pace",
        ),
        "bar": (
            "the workshop air-tool manifold setting",
            "the pneumatic door-closer test pressure",
            "the hydrostatic bench proof-test figure",
            "the spare nitrogen cylinder regulator",
            "the brake-testing rig supply line",
            "the cleaning lance operating head",
        ),
        "temp_c": (
            "the archive vault dehumidifier setpoint",
            "the workshop floor ambient average",
            "the groundwater observation well reading",
            "the server closet return-air target",
            "the concrete curing shed baseline",
            "the seasonal coastal surface mean",
        ),
        "tons": (
            "the yard gantry crane proof weight",
            "the gravel stockpile reserve mass",
            "the retired ballast test block",
            "the seasonal road-salt bunker capacity",
            "the flatbed trailer axle-load cap",
            "the scrap steel bin haul limit",
        ),
        "bays": (
            "the visitor contractor staging apron",
            "the overflow winter storage yard",
            "the decommissioned south annex",
            "the municipal fleet wash compound",
            "the training depot mock-up yard",
            "the spare trailer parking strip",
        ),
        "units": (
            "the spare parts warehouse shelf lot",
            "the retired training kit inventory",
            "the regional loaner pool allocation",
            "the central calibration bench stock",
            "the field-office emergency crate count",
            "the archive backup transceiver cache",
        ),
        "version": (
            "the retired billing export parser",
            "the standalone training kiosk image",
            "the legacy archive viewer utility",
            "the internal label-printer driver",
            "the testbed telemetry replay tool",
            "the offline map-tiling script",
        ),
    }

    return (
        DomainSpec(
            domain_id="maritime-ferry-network",
            title="Northsound Coastal Ferry and Harbor Operations",
            authority="Northsound Maritime Authority",
            region="Northsound Archipelago",
            entities=(
                EntitySpec("Kestrel Ferry", "KF-4", "the northern crossing vessel", "the first asset", "the vessel", "its", "vessel"),
                EntitySpec("Marrow Shoal Terminal", "MST-2", "the eastern landing pier", "the second site", "the terminal", "its", "terminal"),
                EntitySpec("Pelican Shuttle", "PS-7", "the inner-bay commuter craft", "the third asset", "the shuttle", "its", "vessel"),
                EntitySpec("Northbreak Drydock", "NBD-9", "the main hull repair slip", "the fourth site", "the drydock", "its", "facility"),
                EntitySpec("Tidewater Beacon", "TWB-5", "the outer channel relay tower", "the fifth site", "the beacon", "its", "station"),
            ),
            pages=(
                PageSpec("fleet-operations.md", "Fleet and Harbor Operations Manual", "manual", True),
                PageSpec("terminal-directory.html", "Harbor Facilities and Asset Dossier", "dossier", True),
                PageSpec("dispatch-bulletin.txt", "Daily Channel Dispatch Bulletin", "dispatch", True),
                PageSpec("tariff-and-compliance.md", "Tariffs, Clearances, and Compliance Notes", "tariffs", False),
                PageSpec("engineering-telemetry.html", "Marine Engineering and Telemetry Specs", "telemetry", False),
                PageSpec("seasonal-advisory.txt", "Seasonal Crossing Advisory", "advisory", False),
                PageSpec("annual-audit-notes.md", "Annual Marine Audit Summary", "audit", False),
            ),
            attrs=(
                # 4 attributes per entity (20 total) — curated for domain fit and cross-claim unit pairs
                make_attr("channel crossing distance", "km", "route"),
                make_attr("rated cruising speed", "knots", "propulsion"),
                make_attr("adult crossing fare", "usd", "tariff"),
                make_attr("navigation software build", "version", "avionics"),

                make_attr("approach channel distance", "km", "hydrography"),
                make_attr("berth deck length", "m", "docking"),
                make_attr("peak berth surcharge", "usd", "tariff"),
                make_attr("scheduled turnaround window", "min", "dispatch"),

                make_attr("auxiliary generator output", "kW", "electrical"),
                make_attr("reserve fuel capacity", "L", "bunkering"),
                make_attr("annual on-time rate", "pct", "punctuality"),
                make_attr("boarding gate interval", "min", "dispatch"),

                make_attr("keel pit length", "m", "structural"),
                make_attr("dewatering pump rate", "L_min", "hydraulics"),
                make_attr("crane lifting capacity", "tons", "rigging"),
                make_attr("active repair stalls", "bays", "yard"),

                make_attr("shore power draw", "kW", "electrical"),
                make_attr("telemetry uptime rate", "pct", "monitoring"),
                make_attr("transponder firmware release", "version", "signaling"),
                make_attr("weather sensor array count", "units", "instrumentation"),
            ),
            background_topics=(
                "Tidal range shifts across the sound require dockmasters to verify mooring tension at every slack-water change.",
                "Pilots coordinate radio handoffs between inner harbor buoys and exposed channel markers whenever fog banks roll ashore.",
                "Routine hull-plating ultrasonic checks are logged alongside zinc anode replacement cycles in the winter maintenance binder.",
                "Passenger gangway alignment depends on hydraulic ramp sensors that are zeroed before the first morning sailing.",
                "Bunkering crews log sample viscosity and water-separation checks prior to opening shore manifold valves.",
                "Harbor security patrols inspect perimeter fenders, life-ring cabinets, and emergency shore-power breakers every evening.",
            ),
            distractor_subjects=common_distractors,
            noise_notes=(
                "Shoreline crews repainted the yellow hazard curbing near the public waiting shelter and cleared driftwood from the slipway apron.",
                "Harbor office staff rotated the physical binder index at the front counter and posted updated tide-table wall calendars.",
                "Weekend maintenance technicians replaced two corroded deck floodlight brackets along the pedestrian walkway.",
                "The marine radio desk tested the backup handset charger and reorganized the laminated harbor chart drawer.",
            ),
        ),
        DomainSpec(
            domain_id="alpine-rail-corridor",
            title="Highpass Alpine Rail and Tunnel Operations",
            authority="Highpass Rail Directorate",
            region="Central Alpine Spine",
            entities=(
                EntitySpec("Silvercrest Express", "SCX-1", "the summit passenger trainset", "the first line", "the trainset", "its", "trainset"),
                EntitySpec("Glacier Gate Depot", "GGD-3", "the high-elevation transfer yard", "the second site", "the depot", "its", "depot"),
                EntitySpec("Timberline Freight", "TLF-6", "the valley cargo consist", "the third line", "the consist", "its", "consist"),
                EntitySpec("Kestrel Bore Tunnel", "KBT-8", "the main summit passage", "the fourth site", "the tunnel", "its", "tunnel"),
                EntitySpec("Valecrest Control", "VCC-4", "the western signaling center", "the fifth site", "the center", "its", "center"),
            ),
            pages=(
                PageSpec("corridor-handbook.md", "Alpine Corridor Operating Handbook", "manual", True),
                PageSpec("station-profiles.html", "Corridor Asset and Station Dossier", "dossier", True),
                PageSpec("track-dispatch-log.txt", "Daily Track Dispatch Register", "dispatch", True),
                PageSpec("fare-and-safety.md", "Fares, Clearances, and Safety Rules", "tariffs", False),
                PageSpec("rolling-stock-specs.html", "Rolling Stock and Signaling Telemetry", "telemetry", False),
                PageSpec("winter-operations.txt", "Winter Avalanche and Ice Advisory", "advisory", False),
                PageSpec("inspection-summary.md", "Annual Corridor Inspection Summary", "audit", False),
            ),
            attrs=(
                make_attr("summit route length", "km", "alignment"),
                make_attr("line cruising speed", "kmh", "traction"),
                make_attr("standard summit ticket", "eur", "fare"),
                make_attr("cab signaling firmware", "version", "signaling"),

                make_attr("branch spur length", "km", "alignment"),
                make_attr("platform canopy length", "m", "station"),
                make_attr("luggage transfer fee", "eur", "fare"),
                make_attr("coupling turnaround time", "min", "dispatch"),

                make_attr("traction substation draw", "kW", "electrical"),
                make_attr("brake reservoir pressure", "bar", "pneumatics"),
                make_attr("maximum payload mass", "tons", "freight"),
                make_attr("schedule reliability rate", "pct", "punctuality"),

                make_attr("portal clearance span", "m", "civil"),
                make_attr("drainage pump capacity", "L_min", "hydraulics"),
                make_attr("ventilation fan draw", "kW", "ventilation"),
                make_attr("emergency refuge bays", "bays", "safety"),

                make_attr("dispatch cycle interval", "min", "signaling"),
                make_attr("interlocking software build", "version", "signaling"),
                make_attr("trackside beacon count", "units", "telemetry"),
                make_attr("winter availability rate", "pct", "reliability"),
            ),
            background_topics=(
                "Steep ruling gradients along the upper switchbacks demand continuous sand-box level checks before snowstorms arrive.",
                "Track walkers inspect insulated rail joints and snow-shed drainage gratings after every freeze-thaw cycle.",
                "Catenary tension weights are checked weekly to keep pantograph contact force steady across high-wind viaducts.",
                "Tunnel refuge doors undergo differential-pressure sealing checks alongside quarterly emergency lighting drills.",
                "Yard supervisors balance brake-shoe wear logs against axle-counter diagnostics before releasing night consists.",
                "Avalanche acoustic monitors feed directly into the valley watch desk so slow orders can be issued ahead of slide paths.",
            ),
            distractor_subjects=common_distractors,
            noise_notes=(
                "Station attendants refreshed the bilingual wayfinding placards along the concourse stairs and cleared salt residue near the ticket lobby.",
                "The dispatch library updated its paper binder tabs for snowplow roster sheets without altering any timetable figures.",
                "Yard crews repainted the pedestrian crosswalk stripes beside the crew breakroom and checked locker latches.",
                "Signaling clerks archived last winter's weather faxes into labeled boxes in the basement storage room.",
            ),
        ),
        DomainSpec(
            domain_id="geothermal-power-grid",
            title="Basalt Basin Geothermal Generation and Grid Operations",
            authority="Basalt Basin Energy Cooperative",
            region="Basalt Rift Valley",
            entities=(
                EntitySpec("Caldera Unit One", "CU-1", "the northern steam plant", "the first site", "the plant", "its", "plant"),
                EntitySpec("Obsidian Substation", "OBS-3", "the high-voltage switching yard", "the second site", "the substation", "its", "substation"),
                EntitySpec("Fumarole Loop", "FML-5", "the eastern reinjection line", "the third asset", "the loop", "its", "pipeline"),
                EntitySpec("Redrock Wellhead", "RRW-2", "the deep production borefield", "the fourth site", "the borefield", "its", "wellhead"),
                EntitySpec("Sinter Control Hub", "SCH-8", "the central load-dispatch center", "the fifth site", "the hub", "its", "hub"),
            ),
            pages=(
                PageSpec("plant-operations.md", "Geothermal Plant Operations Manual", "manual", True),
                PageSpec("substation-dossier.html", "Generation and Grid Asset Dossier", "dossier", True),
                PageSpec("grid-control-log.txt", "Grid Control Dispatch Log", "dispatch", True),
                PageSpec("capacity-and-tariffs.md", "Capacity Allocations and Wholesale Tariffs", "tariffs", False),
                PageSpec("turbine-telemetry.html", "Turbine and Wellhead Telemetry Specs", "telemetry", False),
                PageSpec("borehole-advisory.txt", "Borehole Pressure and Silica Advisory", "advisory", False),
                PageSpec("reliability-review.md", "Annual Grid Reliability Review", "audit", False),
            ),
            attrs=(
                make_attr("rated net output", "MW", "generation"),
                make_attr("condenser steam pressure", "bar", "thermodynamics"),
                make_attr("wholesale block tariff", "usd", "tariff"),
                make_attr("governor firmware release", "version", "controls"),

                make_attr("transmission corridor length", "km", "grid"),
                make_attr("transformer bank rating", "MW", "grid"),
                make_attr("wheeling access charge", "usd", "tariff"),
                make_attr("active breaker stalls", "bays", "switchgear"),

                make_attr("insulated pipeline length", "km", "piping"),
                make_attr("brine return flow", "L_min", "hydraulics"),
                make_attr("re-injection wellhead pressure", "bar", "reservoir"),
                make_attr("thermal recovery efficiency", "pct", "thermodynamics"),

                make_attr("production casing depth", "m", "drilling"),
                make_attr("separator outlet temperature", "temp_c", "thermodynamics"),
                make_attr("inhibitor dosing tank", "L", "chemistry"),
                make_attr("active monitoring probes", "units", "instrumentation"),

                make_attr("fault isolation window", "min", "protection"),
                make_attr("grid uptime factor", "pct", "reliability"),
                make_attr("scada kernel build", "version", "controls"),
                make_attr("auxiliary backup draw", "kW", "electrical"),
            ),
            background_topics=(
                "Silica scaling along flashing separators requires scheduled chemical inhibitor audits before winter load peaks.",
                "Switchyard engineers verify SF6 gas density gauges and grounding-grid continuity after each dry-season dust storm.",
                "Cooling-tower drift eliminators are washed down in alternating cells to keep condenser vacuum stable.",
                "Micro-seismic geophones around the reinjection perimeter stream continuous waveforms to the basin geology desk.",
                "Turbine lube-oil centrifuges undergo weekly particulate counts alongside vibration spectrum reviews.",
                "Dispatchers coordinate planned feeder switching with regional agricultural co-ops to minimize irrigation pump trips.",
            ),
            distractor_subjects=common_distractors,
            noise_notes=(
                "Grounds crews trimmed dry brush along the perimeter gravel road and checked the security gate intercom speaker.",
                "Control-room staff replaced two worn ergonomic chair casters and tidied the binder rack beside the wall mimic board.",
                "Field technicians repainted weathered valve-tag stencils near the visitor orientation gazebo.",
                "Administrative clerks filed signed safety-briefing attendance rosters in the quarterly compliance cabinet.",
            ),
        ),
        DomainSpec(
            domain_id="botanical-research-stations",
            title="Emerald Canopy Botanical Conservatories and Field Stations",
            authority="Emerald Canopy Research Trust",
            region="Cascadia Uplands",
            entities=(
                EntitySpec("Fernhollow Glasshouse", "FHG-1", "the main tropical conservatory", "the first site", "the glasshouse", "its", "glasshouse"),
                EntitySpec("Cedar Ridge Plot", "CRP-4", "the alpine conifer reserve", "the second site", "the reserve", "its", "reserve"),
                EntitySpec("Mossbank Herbarium", "MBH-2", "the central specimen archive", "the third site", "the herbarium", "its", "herbarium"),
                EntitySpec("Rainshadow Nursery", "RSN-6", "the dryland propagation compound", "the fourth site", "the nursery", "its", "nursery"),
                EntitySpec("Lichen Creek Lab", "LCL-9", "the watershed genomics annex", "the fifth site", "the laboratory", "its", "laboratory"),
            ),
            pages=(
                PageSpec("conservatory-manual.md", "Conservatory and Field Operations Manual", "manual", True),
                PageSpec("field-sites-guide.html", "Research Stations and Collections Dossier", "dossier", True),
                PageSpec("curatorial-bulletin.txt", "Curatorial and Field Dispatch Bulletin", "dispatch", True),
                PageSpec("grants-and-quotas.md", "Access Fees, Quotas, and Conservation Targets", "tariffs", False),
                PageSpec("climate-control-specs.html", "Climate Control and Sensor Telemetry", "telemetry", False),
                PageSpec("seasonal-field-notes.txt", "Seasonal Phenology and Frost Advisory", "advisory", False),
                PageSpec("collection-audit.md", "Annual Botanical Collection Audit", "audit", False),
            ),
            attrs=(
                make_attr("mist zone temperature", "temp_c", "climate"),
                make_attr("irrigation reservoir volume", "L", "hydration"),
                make_attr("research bench fee", "usd", "access"),
                make_attr("climate controller build", "version", "automation"),

                make_attr("transect trail length", "km", "survey"),
                make_attr("canopy tower height", "m", "observation"),
                make_attr("field permit fee", "usd", "access"),
                make_attr("native germination rate", "pct", "ecology"),

                make_attr("vault ambient temperature", "temp_c", "preservation"),
                make_attr("cataloging cycle time", "min", "curation"),
                make_attr("specimen cabinet count", "units", "storage"),
                make_attr("digitized collection share", "pct", "archiving"),

                make_attr("perimeter fence length", "m", "enclosure"),
                make_attr("drip manifold flow", "L_min", "irrigation"),
                make_attr("propagation holding bays", "bays", "greenhouse"),
                make_attr("rainwater cistern volume", "L", "hydration"),

                make_attr("watershed survey span", "km", "hydrology"),
                make_attr("growth chamber draw", "kW", "electrical"),
                make_attr("sequencing pipeline build", "version", "genomics"),
                make_attr("sample drying soak", "hr", "laboratory"),
            ),
            background_topics=(
                "Integrated pest-management teams release predatory mites across humid benches instead of applying broad-spectrum sprays.",
                "Seed-bank technicians verify silica-gel indicator beads inside sealed foil pouches before moving lots into cold storage.",
                "Glazing crews inspect roof vent gaskets and shade-cloth rollers ahead of late-summer heat waves.",
                "Field botanists press voucher specimens with archival linen tape and log GPS coordinates from fixed brass benchmarks.",
                "Rainwater catchment screens are flushed after autumn leaf drop to keep dissolved tannins out of orchid mist lines.",
                "Visiting fellows attend a biosecurity boot-wash orientation prior to entering rare-bryophyte quarantine enclosures.",
            ),
            distractor_subjects=common_distractors,
            noise_notes=(
                "Curators relabeled the wooden drawer pulls in the public reading foyer and replaced two faded trailhead signs.",
                "Grounds staff raked gravel along the visitor courtyard path and cleaned moss from the stone benches.",
                "The library desk shelved incoming botanical journals and updated the volunteer docent rotation board.",
                "Maintenance workers oiled the wooden Dutch doors at the potting shed and tightened hose-reel brackets.",
            ),
        ),
        DomainSpec(
            domain_id="regional-water-works",
            title="Clearbrook Municipal Water Treatment and Aqueduct Network",
            authority="Clearbrook Water Commission",
            region="Clearbrook Basin",
            entities=(
                EntitySpec("Stonebridge Aqueduct", "SBA-2", "the northern gravity conduit", "the first asset", "the aqueduct", "its", "conduit"),
                EntitySpec("Sandbar Filtration", "SBF-5", "the main rapid-sand plant", "the second site", "the plant", "its", "plant"),
                EntitySpec("Hilltop Booster", "HTB-7", "the upper-zone pumping station", "the third site", "the station", "its", "station"),
                EntitySpec("Millpond Reservoir", "MPR-1", "the western storage basin", "the fourth site", "the basin", "its", "reservoir"),
                EntitySpec("Weirgate Telemetry", "WGT-4", "the central SCADA watch house", "the fifth site", "the watch house", "its", "center"),
            ),
            pages=(
                PageSpec("aqueduct-operations.md", "Aqueduct and Treatment Operations Manual", "manual", True),
                PageSpec("treatment-plants.html", "Basin Waterworks Asset Dossier", "dossier", True),
                PageSpec("pumping-dispatch.txt", "Daily Pumping and Valve Dispatch Log", "dispatch", True),
                PageSpec("rates-and-standards.md", "Metering Tariffs and Purity Standards", "tariffs", False),
                PageSpec("valve-telemetry.html", "Hydraulics and Valve Telemetry Specs", "telemetry", False),
                PageSpec("reservoir-bulletin.txt", "Seasonal Reservoir and Turbidity Advisory", "advisory", False),
                PageSpec("quality-audit.md", "Annual Water Quality Compliance Audit", "audit", False),
            ),
            attrs=(
                make_attr("trunk conduit length", "km", "conveyance"),
                make_attr("siphon culvert span", "m", "civil"),
                make_attr("bulk supply rate", "usd", "tariff"),
                make_attr("scada valve firmware", "version", "controls"),

                make_attr("rapid filter flow", "L_min", "treatment"),
                make_attr("backwash cycle window", "min", "treatment"),
                make_attr("commercial meter charge", "usd", "tariff"),
                make_attr("active filter basins", "bays", "treatment"),

                make_attr("discharge header pressure", "bar", "hydraulics"),
                make_attr("pump motor load", "kW", "electrical"),
                make_attr("peak efficiency rating", "pct", "pumping"),
                make_attr("surge tank volume", "L", "hydraulics"),

                make_attr("intake tunnel length", "m", "civil"),
                make_attr("perimeter patrol road", "km", "security"),
                make_attr("alum storage reserve", "L", "treatment"),
                make_attr("raw intake temperature", "temp_c", "limnology"),

                make_attr("chlorine contact soak", "hr", "disinfection"),
                make_attr("remote sensor count", "units", "telemetry"),
                make_attr("compliance pass rate", "pct", "quality"),
                make_attr("historian software build", "version", "telemetry"),
            ),
            background_topics=(
                "Turbidity spikes following mountain snowmelt trigger automated coagulant jar tests at the main intake laboratory.",
                "Valve crews exercise buried butterfly valves on a rolling schedule so stems never seize during main-break isolation.",
                "Acoustic leak correlators listen along cast-iron distribution trunks during low-flow overnight hours.",
                "Reservoir caretakers check spillway trash racks and piezometer wells along the earthen embankment each week.",
                "Standby diesel switchgear runs under load bank testing monthly to verify smooth transfer during grid sags.",
                "Water-quality chemists cross-check online residual analyzers against hand-titrated grab samples every shift.",
            ),
            distractor_subjects=common_distractors,
            noise_notes=(
                "Facility crews swept the concrete spillway walkway and repainted the safety railing beside the parking lot.",
                "Clerks organized archived sample-bottle manifests into labeled binders on the north office shelves.",
                "Maintenance staff replaced a cracked plexiglass cover on the outdoor notice board near the main gate.",
                "Operators cleaned the mudroom boot-scrubbing grate and restocked disposable glove dispensers.",
            ),
        ),
        DomainSpec(
            domain_id="arctic-weather-observatories",
            title="Boreal Ring Arctic Meteorological Observatory Network",
            authority="Boreal Atmospheric Service",
            region="High Boreal Sector",
            entities=(
                EntitySpec("Frostpoint Dome", "FPD-1", "the northern upper-air station", "the first site", "the station", "its", "station"),
                EntitySpec("Driftwood Sound", "DWS-3", "the coastal ice-radar post", "the second site", "the outpost", "its", "outpost"),
                EntitySpec("Tundra Ridge Array", "TRA-6", "the inland wind-profiler site", "the third site", "the array", "its", "array"),
                EntitySpec("Sprucebay Depot", "SBD-2", "the winter resupply base", "the fourth site", "the depot", "its", "depot"),
                EntitySpec("Aurora Link Relay", "ALR-8", "the satellite downlink hut", "the fifth site", "the relay", "its", "relay"),
            ),
            pages=(
                PageSpec("station-handbook.md", "Arctic Observatory Operations Handbook", "manual", True),
                PageSpec("outpost-profiles.html", "Observatory Sites and Instrument Dossier", "dossier", True),
                PageSpec("synoptic-bulletin.txt", "Synoptic Watch and Balloon Dispatch Log", "dispatch", True),
                PageSpec("logistics-and-budgets.md", "Resupply Tariffs and Fuel Budgets", "tariffs", False),
                PageSpec("instrument-specs.html", "Meteorological Instrument Telemetry", "telemetry", False),
                PageSpec("polar-season-log.txt", "Polar Night and Sea-Ice Advisory", "advisory", False),
                PageSpec("calibration-review.md", "Annual Sensor Calibration Audit", "audit", False),
            ),
            attrs=(
                make_attr("balloon launch interval", "hr", "upper-air"),
                make_attr("radome mast height", "m", "structures"),
                make_attr("charter cargo rate", "usd", "logistics"),
                make_attr("sonde decoder build", "version", "telemetry"),

                make_attr("coastal scan corridor", "km", "radar"),
                make_attr("peak wind threshold", "kmh", "weather"),
                make_attr("ice-core assay fee", "usd", "laboratory"),
                make_attr("radar uptime ratio", "pct", "reliability"),

                make_attr("snow-track supply route", "km", "logistics"),
                make_attr("heater bank load", "kW", "electrical"),
                make_attr("sensor calibration window", "min", "maintenance"),
                make_attr("acoustic anemometer count", "units", "instrumentation"),

                make_attr("fuel bladder volume", "L", "storage"),
                make_attr("bulk supply tonnage", "tons", "freight"),
                make_attr("heated sled bays", "bays", "garage"),
                make_attr("warehouse floor temperature", "temp_c", "heating"),

                make_attr("antenna tower height", "m", "communications"),
                make_attr("downlink capture rate", "pct", "communications"),
                make_attr("modem firmware release", "version", "communications"),
                make_attr("backup generator draw", "kW", "electrical"),
            ),
            background_topics=(
                "Rime ice accumulation on pyranometer domes requires gentle alcohol wipes before each synoptic observation hour.",
                "Hydrogen inflation sheds undergo strict static-grounding checks prior to filling twice-daily upper-air balloons.",
                "Tracked snow-cat teams flag crevasse detours with bamboo wands before polar twilight reduces surface contrast.",
                "Battery banks are kept inside insulated cabinets with trickle equalizers to withstand extended subzero calm spells.",
                "Satellite dish de-icing heaters cycle automatically whenever cross-polarization noise climbs during wet snow.",
                "Visiting glaciologists coordinate snow-pit stratigraphy digs well clear of undisturbed precipitation-gauge aprons.",
            ),
            distractor_subjects=common_distractors,
            noise_notes=(
                "Station cooks reorganized the dry-goods pantry shelves and inventoried spare wool liners in the vestibule.",
                "Technicians cleared drifted snow from the porch steps and inspected the wooden storm-door latches.",
                "The radio desk replaced frayed headphone earpads and neatly coiled spare patch cables on the pegboard.",
                "Logistics staff updated the color-coded crate labels in the heated entry hall.",
            ),
        ),
        DomainSpec(
            domain_id="freight-airfield-logistics",
            title="Crosswind Regional Cargo Airfield and Cold-Chain Hub",
            authority="Crosswind Aviation Logistics Board",
            region="Midlands Freight Basin",
            entities=(
                EntitySpec("Falcon Apron North", "FAN-1", "the main widebody cargo ramp", "the first site", "the apron", "its", "apron"),
                EntitySpec("Glacier Vault Cold", "GVC-4", "the pharmaceutical cold warehouse", "the second site", "the vault", "its", "warehouse"),
                EntitySpec("Meridian Hangar", "MRH-7", "the heavy airframe maintenance bay", "the third site", "the hangar", "its", "hangar"),
                EntitySpec("Runway Bravo Strip", "RBS-2", "the secondary instrument runway", "the fourth site", "the runway", "its", "runway"),
                EntitySpec("Beacon Tower East", "BTE-5", "the ground-movement control tower", "the fifth site", "the tower", "its", "tower"),
            ),
            pages=(
                PageSpec("ramp-operations.md", "Airfield Ramp and Cargo Operations Manual", "manual", True),
                PageSpec("hangar-directory.html", "Airfield Facilities and Cold-Chain Dossier", "dossier", True),
                PageSpec("cargo-dispatch-log.txt", "Night Cargo Ramp Dispatch Log", "dispatch", True),
                PageSpec("handling-tariffs.md", "Ramp Handling Tariffs and Compliance Rules", "tariffs", False),
                PageSpec("cold-chain-specs.html", "Cold-Chain and Ground Power Telemetry", "telemetry", False),
                PageSpec("runway-advisory.txt", "Runway Surface and De-Icing Advisory", "advisory", False),
                PageSpec("compliance-audit.md", "Annual Airfield Compliance Audit", "audit", False),
            ),
            attrs=(
                make_attr("tug turnaround window", "min", "ground-handling"),
                make_attr("ground power draw", "kW", "electrical"),
                make_attr("pallet handling tariff", "usd", "tariff"),
                make_attr("active loading bays", "bays", "apron"),

                make_attr("chiller vault setpoint", "temp_c", "cold-chain"),
                make_attr("glycol coolant reserve", "L", "refrigeration"),
                make_attr("cold-storage access fee", "usd", "tariff"),
                make_attr("temperature compliance rate", "pct", "quality"),

                make_attr("door clearance span", "m", "structural"),
                make_attr("hoist payload rating", "tons", "rigging"),
                make_attr("compressed air pressure", "bar", "pneumatics"),
                make_attr("diagnostic cart count", "units", "equipment"),

                make_attr("perimeter taxiway loop", "km", "airfield"),
                make_attr("threshold lighting span", "m", "lighting"),
                make_attr("de-icing truck flow", "L_min", "winter-ops"),
                make_attr("crosswind caution limit", "kmh", "weather"),

                make_attr("surface radar range", "km", "surveillance"),
                make_attr("dispatch software build", "version", "controls"),
                make_attr("slot adherence rate", "pct", "punctuality"),
                make_attr("transponder parser build", "version", "avionics"),
            ),
            background_topics=(
                "Foreign-object debris sweepers patrol every taxiway intersection before the nightly express freight wave lands.",
                "Cold-chain marshals verify insulated blanket seals and logger activation LEDs prior to closing reefer-truck docks.",
                "Airfield electricians inspect runway edge-light lenses and constant-current regulators during midday lulls.",
                "De-icing pads drain spent glycol runoff into segregated holding ponds for off-site recycling tankers.",
                "Loadmasters cross-check pallet scale calibration weights against manifest totals before signing weight-and-balance sheets.",
                "Wildlife control patrols log bird-dispersal sweeps along perimeter retention basins at dawn and dusk.",
            ),
            distractor_subjects=common_distractors,
            noise_notes=(
                "Ramp supervisors replaced scuffed reflective cones near the crew van pickup curb and swept the vest locker room.",
                "The freight desk printed fresh clip-in lanyard sleeves and reorganized the customs stamp rack.",
                "Custodial teams buffed the breakroom linoleum floor and refilled paper towel cabinets in the east vestibule.",
                "Maintenance painters touched up the yellow boundary line outside the tool crib entrance.",
            ),
        ),
        DomainSpec(
            domain_id="urban-district-heating",
            title="Ironbridge District Thermal Loop and Cogeneration Network",
            authority="Ironbridge Thermal Utility",
            region="Ironbridge Metro Sector",
            entities=(
                EntitySpec("Foundry Cogen Plant", "FCP-1", "the main riverside boiler house", "the first site", "the plant", "its", "plant"),
                EntitySpec("Canal Heat Exchange", "CHE-3", "the central transfer substation", "the second site", "the station", "its", "station"),
                EntitySpec("Westgate Loop Main", "WLM-5", "the insulated western ring pipe", "the third asset", "the loop", "its", "pipeline"),
                EntitySpec("Millrace Thermal Tank", "MTT-2", "the stratified accumulator tower", "the fourth site", "the tower", "its", "tower"),
                EntitySpec("Civic Meter Desk", "CMD-8", "the district billing telemetry hub", "the fifth site", "the hub", "its", "hub"),
            ),
            pages=(
                PageSpec("network-operations.md", "District Thermal Network Operations Manual", "manual", True),
                PageSpec("plant-directory.html", "Cogeneration and Substation Asset Dossier", "dossier", True),
                PageSpec("thermal-dispatch.txt", "Daily Thermal Load Dispatch Bulletin", "dispatch", True),
                PageSpec("metering-and-rates.md", "District Heating Rates and Efficiency Targets", "tariffs", False),
                PageSpec("boiler-telemetry.html", "Boiler and Loop Hydraulics Telemetry", "telemetry", False),
                PageSpec("heating-season-notes.txt", "Heating Season Peak Load Advisory", "advisory", False),
                PageSpec("efficiency-audit.md", "Annual Thermal Efficiency Audit", "audit", False),
            ),
            attrs=(
                make_attr("thermal output rating", "MW", "generation"),
                make_attr("boiler header pressure", "bar", "hydraulics"),
                make_attr("commercial connection fee", "eur", "tariff"),
                make_attr("burner controller build", "version", "controls"),

                make_attr("primary supply flow", "L_min", "hydraulics"),
                make_attr("heat exchanger efficiency", "pct", "thermodynamics"),
                make_attr("meter inspection fee", "eur", "tariff"),
                make_attr("valve actuation window", "min", "controls"),

                make_attr("trunk pipe length", "km", "distribution"),
                make_attr("expansion chamber span", "m", "civil"),
                make_attr("loop supply pressure", "bar", "hydraulics"),
                make_attr("circulation pump draw", "kW", "electrical"),

                make_attr("accumulator vessel height", "m", "structures"),
                make_attr("makeup water reserve", "L", "chemistry"),
                make_attr("charge cycle duration", "hr", "storage"),
                make_attr("return line temperature", "temp_c", "thermodynamics"),

                make_attr("feeder branch length", "km", "distribution"),
                make_attr("telemetry delivery rate", "pct", "metering"),
                make_attr("active heat meters", "units", "metering"),
                make_attr("billing gateway build", "version", "software"),
            ),
            background_topics=(
                "Pre-insulated steel mains include embedded copper alarm wires that alert crews to groundwater ingress inside casing joints.",
                "Water-treatment chemists monitor dissolved oxygen and pH continuously to suppress corrosion inside plate heat exchangers.",
                "Stratified thermal accumulators absorb overnight cogeneration surplus so morning radiator warm-up ramps stay smooth.",
                "Substation crews inspect differential-pressure controllers and strainer baskets before the October cold snap.",
                "Acoustic vault inspections check underground valve chambers for steam wisps and sump-pump float operation.",
                "Dispatchers coordinate flue-gas condenser blowdown schedules with municipal wastewater flow windows.",
            ),
            distractor_subjects=common_distractors,
            noise_notes=(
                "Plant stewards washed the observation-gallery windows and updated the visitor hard-hat rack inventory.",
                "Office coordinators archived quarterly paper inspection slips and restocked dry-erase markers in the briefing room.",
                "Grounds crews swept autumn leaves away from the courtyard drain grates beside the loading dock.",
                "Technicians relabeled wrench drawers in the maintenance workshop without changing any operational settings.",
            ),
        ),
    )


DOMAINS = _build_domains()


# ---------------------------------------------------------------------------
# Internal plan structures for deterministic AST-based rendering
# ---------------------------------------------------------------------------

@dataclass
class ClaimPlan:
    cid: str
    entity_idx: int
    entity: EntitySpec
    attr: AttrSpec
    template_line: str
    source_pages: list[str]
    is_indirect: bool
    val_c0: str
    core_c0: Any
    # Map cycle (1..4) -> new value if changed in that cycle
    cycle_values: list[str]  # length 5 (cycle 0..4)


@dataclass
class DistractorItem:
    page: str
    text: str
    is_collision: bool


def _variant_domain(base: DomainSpec, batch_idx: int) -> DomainSpec:
    """Create a deterministic regional variant when n_sets exceeds len(DOMAINS)."""
    if batch_idx == 0:
        return base
    suffixes = ("West", "South", "East", "North", "Highland", "Coastal", "Valley", "Central")
    tag = suffixes[(batch_idx - 1) % len(suffixes)]
    slug_tag = tag.lower() if batch_idx <= len(suffixes) else f"{tag.lower()}-{batch_idx}"
    new_entities = tuple(
        EntitySpec(
            name=f"{e.name} {tag}",
            nickname=f"{e.nickname}{tag[0]}",
            descriptor=f"{e.descriptor} ({slug_tag} sector)",
            ordinal=e.ordinal,
            subj=e.subj,
            poss=e.poss,
            kind=e.kind,
        )
        for e in base.entities
    )
    return DomainSpec(
        domain_id=f"{base.domain_id}-{slug_tag}",
        title=f"{base.title} — {tag} Division",
        authority=f"{base.authority} ({tag})",
        region=f"{base.region} {tag}",
        entities=new_entities,
        pages=base.pages,
        attrs=base.attrs,
        background_topics=base.background_topics,
        distractor_subjects=base.distractor_subjects,
        noise_notes=base.noise_notes,
    )


def _make_distractor_sentence(
    domain: DomainSpec,
    unit_kind: str,
    val: str,
    rng: random.Random,
    used_subjects: set[str] | None = None,
) -> str:
    subjects = domain.distractor_subjects[unit_kind]
    if used_subjects is not None:
        fresh = [s for s in subjects if s not in used_subjects]
        subj = rng.choice(fresh) if fresh else rng.choice(subjects)
        used_subjects.add(subj)
    else:
        subj = rng.choice(subjects)
    templates = (
        f"Reference telemetry notes that {subj} measured {val} during the prior regional benchmark.",
        f"For background comparison, {subj} stands at {val} in the district engineering archive.",
        f"Historical records place {subj} at {val} outside active facility allocations.",
        f"Independent survey sheets report {val} for {subj} across the adjacent sector.",
        f"Archival compliance logs list {subj} at {val} under legacy test rules.",
    )
    return rng.choice(templates)


def _format_claim_occurrence(
    claim: ClaimPlan,
    val: str,
    style: str,
    variant_idx: int,
) -> tuple[str | None, str]:
    """Return (optional_lead_sentence, main_sentence) for a claim occurrence."""
    e = claim.entity
    a = claim.attr
    if style == "direct":
        tmpl = a.direct_templates[variant_idx % len(a.direct_templates)]
        return None, tmpl.format(entity=e.name, val=val)
    if style == "heading_indirect":
        tmpl = a.indirect_heading_templates[variant_idx % len(a.indirect_heading_templates)]
        return None, tmpl.format(poss=e.poss, subj=e.subj, val=val)
    if style == "anaphora":
        lead = a.anaphora_leads[variant_idx % len(a.anaphora_leads)].format(entity=e.name)
        follow = a.anaphora_follows[variant_idx % len(a.anaphora_follows)].format(
            descriptor=e.descriptor, poss=e.poss, subj=e.subj, val=val
        )
        return lead, follow
    if style == "nickname":
        tmpl = a.nickname_templates[variant_idx % len(a.nickname_templates)]
        return None, tmpl.format(nick=e.nickname, val=val)
    if style == "ordinal":
        tmpl = a.ordinal_templates[variant_idx % len(a.ordinal_templates)]
        return None, tmpl.format(ordinal=e.ordinal, val=val)
    raise ValueError(f"Unknown style: {style}")


def _build_set_plan(
    set_idx: int,
    seed: int,
) -> dict[str, Any]:
    """Deterministically plan all claims, pages, collisions, distractors, and cycles for one set."""
    set_id = f"s{set_idx + 1:02d}"
    rng = random.Random(seed * 1000003 + (set_idx + 1) * 9176 + 17)

    base_domain = DOMAINS[set_idx % len(DOMAINS)]
    domain = _variant_domain(base_domain, set_idx // len(DOMAINS))

    # Vary number of content pages across 5, 6, 7 while guaranteeing all 3 formats (.md, .html, .txt)
    n_pages = (5, 6, 7)[(set_idx + seed) % 3]
    selected_pages = list(domain.pages[:n_pages])
    page_names = [p.filename for p in selected_pages]
    page_by_name = {p.filename: p for p in selected_pages}
    index_name = "index.html" if (set_idx + seed) % 2 == 0 else "index.md"

    entities = domain.entities  # 5 entities
    attrs = domain.attrs  # 20 attributes (4 per entity)

    # 1) Decide which 9 claims (45%) are multi-page: 3 on 3 pages, 6 on 2 pages, 11 on 1 page
    claim_indices = list(range(20))
    rng.shuffle(claim_indices)
    three_page_set = set(claim_indices[:3])
    two_page_set = set(claim_indices[3:9])
    # Ensure indirect claims cover 12/20 = 60% (including at least half of single-page & multi-page)
    indirect_candidates = list(range(20))
    rng.shuffle(indirect_candidates)
    indirect_set = set(indirect_candidates[:12])

    # 2) Assign source_pages for each of the 20 claims
    #    Ensure long pages (page 0 and page 1) get claims from multiple entities,
    #    dispatch page (page 2) gets nickname-list claims, and all pages are populated.
    claim_source_pages: list[list[str]] = [[] for _ in range(20)]
    page_load = {p: 0 for p in page_names}

    for idx in range(20):
        ent_idx = idx // 4
        if idx in three_page_set:
            k_pages = 3
        elif idx in two_page_set:
            k_pages = 2
        else:
            k_pages = 1

        # Prefer placing at least one indirect claim per entity on long pages (0 or 1)
        preferred: list[str] = []
        if idx in indirect_set:
            long_pref = page_names[ent_idx % 2]
            preferred.append(long_pref)
            if k_pages >= 2 and page_names[2] not in preferred:
                preferred.append(page_names[2])  # dispatch nickname list
        else:
            preferred.append(page_names[(ent_idx + idx) % n_pages])

        chosen: list[str] = []
        for p in preferred:
            if p not in chosen and len(chosen) < k_pages:
                chosen.append(p)
        # Fill remaining slots choosing least-loaded pages deterministically
        while len(chosen) < k_pages:
            remaining = [p for p in page_names if p not in chosen]
            remaining.sort(key=lambda p: (page_load[p], rng.random()))
            chosen.append(remaining[0])

        # Preserve canonical page order
        chosen.sort(key=lambda p: page_names.index(p))
        claim_source_pages[idx] = chosen
        for p in chosen:
            page_load[p] += 1

    # Guarantee every content page has at least 2 claims
    for p in page_names:
        if page_load[p] == 0:
            # Swap into a single-page claim from the heaviest page
            heaviest = max(page_names, key=lambda x: page_load[x])
            for idx in range(20):
                if len(claim_source_pages[idx]) == 1 and claim_source_pages[idx][0] == heaviest:
                    claim_source_pages[idx] = [p]
                    page_load[heaviest] -= 1
                    page_load[p] += 1
                    break

    # 3) Generate cycle-0 values with 2 intentional cross-claim collision pairs (4 claims)
    forbidden_strings: set[str] = set()
    forbidden_cores: set[Any] = set()

    # Find pairs of claims with same unit_kind and different entities
    by_unit: dict[str, list[int]] = {}
    for idx, attr in enumerate(attrs):
        by_unit.setdefault(attr.unit_kind, []).append(idx)

    cross_pairs: list[tuple[int, int]] = []
    used_in_cross: set[int] = set()
    unit_keys = sorted(by_unit.keys())
    rng.shuffle(unit_keys)
    for uk in unit_keys:
        if len(cross_pairs) >= 2:
            break
        idxs = [i for i in by_unit[uk] if i not in used_in_cross]
        # Find two with different entities; avoid pairing a direct claim with an indirect claim on the same page
        pair_found = None
        for i_pos in range(len(idxs)):
            for j_pos in range(i_pos + 1, len(idxs)):
                a_i, b_i = idxs[i_pos], idxs[j_pos]
                if (a_i // 4) == (b_i // 4):
                    continue
                if (a_i in indirect_set) != (b_i in indirect_set):
                    if set(claim_source_pages[a_i]) & set(claim_source_pages[b_i]):
                        continue
                pair_found = (a_i, b_i)
                break
            if pair_found:
                break
        if pair_found:
            cross_pairs.append(pair_found)
            used_in_cross.update(pair_found)

    vals_c0: list[str] = [""] * 20
    cores_c0: list[Any] = [None] * 20

    for a_i, b_i in cross_pairs:
        uk = attrs[a_i].unit_kind
        v, c = gen_unique_value(uk, rng, forbidden_strings, forbidden_cores)
        forbidden_strings.add(v)
        forbidden_cores.add((uk, c))
        vals_c0[a_i] = v
        cores_c0[a_i] = c
        vals_c0[b_i] = v
        cores_c0[b_i] = c

    for idx in range(20):
        if vals_c0[idx]:
            continue
        uk = attrs[idx].unit_kind
        v, c = gen_unique_value(uk, rng, forbidden_strings, forbidden_cores)
        forbidden_strings.add(v)
        forbidden_cores.add((uk, c))
        vals_c0[idx] = v
        cores_c0[idx] = c

    # 4) Plan cycles 1..4: shuffled multiset {F, F, N, Z}
    cycle_types = list(CYCLE_TYPES_BASE)
    rng.shuffle(cycle_types)

    # Pick 4 distinct claims for the two F cycles:
    # Each F cycle gets 1 multi-page claim + 1 single-page claim so union(source_pages) <= 4 < n_pages
    # leaving at least 1 page strictly disjoint for the unrelated noise edit.
    multi_idxs = [i for i in range(20) if len(claim_source_pages[i]) >= 2]
    single_idxs = [i for i in range(20) if len(claim_source_pages[i]) == 1]
    rng.shuffle(multi_idxs)
    rng.shuffle(single_idxs)

    # Avoid picking both members of the same cross-claim pair
    def _pick_f_pair(already_picked: set[int]) -> tuple[list[int], str]:
        forbidden_partners: set[int] = set()
        for a_i, b_i in cross_pairs:
            if a_i in already_picked:
                forbidden_partners.add(b_i)
            if b_i in already_picked:
                forbidden_partners.add(a_i)
        for m in multi_idxs:
            if m in already_picked or m in forbidden_partners:
                continue
            for s in single_idxs:
                if s in already_picked or s in forbidden_partners or s == m:
                    continue
                # Avoid both in same cross pair
                if any({m, s} == {a_i, b_i} for a_i, b_i in cross_pairs):
                    continue
                covered = set(claim_source_pages[m]) | set(claim_source_pages[s])
                free_pages = [p for p in page_names if p not in covered]
                if free_pages:
                    noise_p = rng.choice(free_pages)
                    return sorted([m, s]), noise_p
        raise RuntimeError("Could not pick valid F-cycle claim pair")

    f_picked: set[int] = set()
    cycle_plans: list[dict[str, Any]] = []
    # Track truth values across cycles 0..4
    cycle_truth_rows: list[list[str]] = [list(vals_c0)]

    for cy_num, cy_type in enumerate(cycle_types, start=1):
        prev_row = list(cycle_truth_rows[-1])
        if cy_type == "Z":
            cycle_truth_rows.append(prev_row)
            cycle_plans.append({
                "cycle": cy_num,
                "type": "Z",
                "changed_claims": [],
                "noise_pages": [],
            })
        elif cy_type == "N":
            n_noise = rng.choice([1, 2])
            n_pages_chosen = sorted(rng.sample(page_names, k=n_noise), key=lambda p: page_names.index(p))
            cycle_truth_rows.append(prev_row)
            cycle_plans.append({
                "cycle": cy_num,
                "type": "N",
                "changed_claims": [],
                "noise_pages": n_pages_chosen,
            })
        elif cy_type == "F":
            chosen_idxs, noise_p = _pick_f_pair(f_picked)
            f_picked.update(chosen_idxs)
            new_row = list(prev_row)
            for idx in chosen_idxs:
                uk = attrs[idx].unit_kind
                new_val, new_core = gen_unique_value(uk, rng, forbidden_strings, forbidden_cores)
                forbidden_strings.add(new_val)
                forbidden_cores.add((uk, new_core))
                new_row[idx] = new_val
            cycle_truth_rows.append(new_row)
            cycle_plans.append({
                "cycle": cy_num,
                "type": "F",
                "changed_claims": [f"c{idx + 1:02d}" for idx in chosen_idxs],
                "noise_pages": [noise_p],
            })
        else:
            raise ValueError(f"Unknown cycle type: {cy_type}")

    # Build ClaimPlan objects
    claims: list[ClaimPlan] = []
    for idx in range(20):
        ent_idx = idx // 4
        ent = entities[ent_idx]
        attr = attrs[idx]
        cid = f"c{idx + 1:02d}"
        tline = f"- {ent.name} \u2014 {attr.label}: "
        claims.append(
            ClaimPlan(
                cid=cid,
                entity_idx=ent_idx,
                entity=ent,
                attr=attr,
                template_line=tline,
                source_pages=claim_source_pages[idx],
                is_indirect=(idx in indirect_set),
                val_c0=vals_c0[idx],
                core_c0=cores_c0[idx],
                cycle_values=[cycle_truth_rows[k][idx] for k in range(5)],
            )
        )

    # 5) Create 8 distractor-fact collisions (on top of 4 cross-claim collisions -> 12/20 = 60%!)
    #    Rules:
    #    - For direct-only claims: ALWAYS place colliding distractor on a page NOT in source_pages
    #      (prevents false-positive entity-free sentence count).
    #    - For indirect claims: ~half on another page, ~half on the same page (separate background section).
    non_cross_idxs = [i for i in range(20) if i not in used_in_cross]
    rng.shuffle(non_cross_idxs)
    # Include at least one F-changed claim among distractor collisions if possible
    f_non_cross = [i for i in non_cross_idxs if i in f_picked]
    other_non_cross = [i for i in non_cross_idxs if i not in f_picked]
    distractor_coll_idxs = (f_non_cross[:2] + other_non_cross)[:8]

    coll_distractors_by_page: dict[str, list[str]] = {p: [] for p in page_names}
    same_page_count = 0
    for idx in distractor_coll_idxs:
        cl = claims[idx]
        other_pages = [p for p in page_names if p not in cl.source_pages]
        use_same_page = cl.is_indirect and same_page_count < 3
        if use_same_page:
            target_page = rng.choice(cl.source_pages)
            same_page_count += 1
        else:
            target_page = rng.choice(other_pages)
        sent = _make_distractor_sentence(domain, cl.attr.unit_kind, cl.val_c0, rng)
        coll_distractors_by_page[target_page].append(sent)

    # 6) Generate abundant non-colliding distractors per page using the same units & magnitudes
    #    (strictly avoiding forbidden_strings and avoiding duplicate values/subjects within a page).
    set_units = sorted({a.unit_kind for a in attrs})
    regular_distractors_by_page: dict[str, list[str]] = {p: [] for p in page_names}
    for p in page_names:
        role = page_by_name[p].role
        count = 26 if role in ("manual", "dossier") else 12
        page_used_vals = set(forbidden_strings)
        page_used_subjects: set[str] = set()
        for _ in range(count):
            uk = rng.choice(set_units)
            dv, _ = gen_unique_value(uk, rng, page_used_vals, None)
            page_used_vals.add(dv)
            sent = _make_distractor_sentence(domain, uk, dv, rng, page_used_subjects)
            regular_distractors_by_page[p].append(sent)

    # 7) Decide per-(page, claim) phrasing style and deterministic variant index
    #    Guarantee:
    #    - Every indirect claim has AT LEAST ONE occurrence in an entity-name-free sentence.
    #    - On long pages (manual/dossier), indirect claims sit inside entity sections 18-28 lines
    #      below the entity heading using heading_indirect or ordinal phrasing!
    #    - On dispatch (.txt), indirect claims use table-free nickname-keyed bullets!
    #    - Every direct claim ONLY uses direct phrasing (never indirect).
    occ_style: dict[tuple[str, str], tuple[str, int]] = {}
    for cl in claims:
        if not cl.is_indirect:
            for j, p in enumerate(cl.source_pages):
                occ_style[(p, cl.cid)] = ("direct", (int(cl.cid[1:]) + j) % 4)
        else:
            has_indirect_slot = False
            for j, p in enumerate(cl.source_pages):
                role = page_by_name[p].role
                if role in ("manual", "dossier"):
                    st = "heading_indirect" if (int(cl.cid[1:]) + j) % 3 != 0 else "ordinal"
                    has_indirect_slot = True
                elif role == "dispatch":
                    st = "nickname"
                    has_indirect_slot = True
                elif role == "telemetry":
                    st = "anaphora"
                    has_indirect_slot = True
                elif role == "audit":
                    st = "nickname" if j % 2 == 0 else "ordinal"
                    has_indirect_slot = True
                else:
                    # Mix indirect and occasional direct on secondary pages if already indirect elsewhere
                    if has_indirect_slot and j == len(cl.source_pages) - 1 and (int(cl.cid[1:]) % 2 == 0):
                        st = "direct"
                    else:
                        st = ("anaphora", "ordinal", "nickname")[(int(cl.cid[1:]) + j) % 3]
                        has_indirect_slot = True
                occ_style[(p, cl.cid)] = (st, (int(cl.cid[1:]) + j) % 4)
            if not has_indirect_slot:
                p0 = cl.source_pages[0]
                occ_style[(p0, cl.cid)] = ("anaphora", int(cl.cid[1:]) % 3)

    # 8) Track noise_rev per page for each cycle 0..4
    noise_revs: list[dict[str, int]] = [{p: 0 for p in page_names}]
    for cy in cycle_plans:
        prev = dict(noise_revs[-1])
        for np in cy["noise_pages"]:
            prev[np] += 1
        noise_revs.append(prev)

    return {
        "set_id": set_id,
        "domain": domain,
        "index_name": index_name,
        "selected_pages": selected_pages,
        "page_names": page_names,
        "claims": claims,
        "cycle_plans": cycle_plans,
        "occ_style": occ_style,
        "coll_distractors_by_page": coll_distractors_by_page,
        "regular_distractors_by_page": regular_distractors_by_page,
        "noise_revs": noise_revs,
    }


# ---------------------------------------------------------------------------
# Rendering: template.md, index, and .md / .html / .txt content pages
# ---------------------------------------------------------------------------

def render_template(plan: dict[str, Any]) -> str:
    domain: DomainSpec = plan["domain"]
    claims: list[ClaimPlan] = plan["claims"]
    lines: list[str] = [
        f"# {domain.title} — Field Verification Template",
        "Record the exact current value from the site documents for each line below, keeping all units, symbols, and version prefixes intact.",
        "",
    ]
    for e_idx, ent in enumerate(domain.entities):
        lines.append(f"## {ent.name}")
        for cl in claims:
            if cl.entity_idx == e_idx:
                lines.append(f"{cl.template_line}____")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_index(plan: dict[str, Any]) -> str:
    domain: DomainSpec = plan["domain"]
    index_name: str = plan["index_name"]
    pages: list[PageSpec] = plan["selected_pages"]

    if index_name.endswith(".html"):
        items = "\n".join(
            f'      <li><a href="{html.escape(p.filename)}">{html.escape(p.title)}</a> ({html.escape(p.filename)})</li>'
            for p in pages
        )
        return (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '  <meta charset="utf-8">\n'
            f"  <title>{html.escape(domain.title)} — Document Index</title>\n"
            "</head>\n"
            "<body>\n"
            "  <main>\n"
            f"    <h1>{html.escape(domain.title)}</h1>\n"
            f"    <p>Published by {html.escape(domain.authority)} for the {html.escape(domain.region)} operating area.</p>\n"
            "    <h2>Site Documents</h2>\n"
            "    <ul>\n"
            f"{items}\n"
            "    </ul>\n"
            "  </main>\n"
            "</body>\n"
            "</html>\n"
        )
    else:
        lines = [
            f"# {domain.title}",
            "",
            f"Published by {domain.authority} covering the {domain.region} operating area.",
            "",
            "## Site Documents",
            "",
        ]
        for p in pages:
            lines.append(f"- [{p.title}]({p.filename}) — {p.role} reference")
        lines.append("")
        return "\n".join(lines)


def _noise_note_for_rev(domain: DomainSpec, page_idx: int, rev: int) -> str:
    notes = domain.noise_notes
    if rev == 0:
        return "Standard filing review completed with no general facility announcements pending."
    return notes[(page_idx + rev - 1) % len(notes)]


def _render_md_page(
    plan: dict[str, Any],
    page: PageSpec,
    page_idx: int,
    cycle: int,
) -> str:
    domain: DomainSpec = plan["domain"]
    claims: list[ClaimPlan] = plan["claims"]
    occ_style: dict[tuple[str, str], tuple[str, int]] = plan["occ_style"]
    reg_dist = list(plan["regular_distractors_by_page"][page.filename])
    coll_dist = list(plan["coll_distractors_by_page"][page.filename])
    noise_rev = plan["noise_revs"][cycle][page.filename]

    page_claims = [cl for cl in claims if page.filename in cl.source_pages]
    lines: list[str] = [
        f"# {page.title}",
        "",
        f"Prepared by {domain.authority} for {domain.region}.",
        "",
        "## Entity Callsign and Role Reference",
        "",
    ]
    for ent in domain.entities:
        lines.append(
            f"- {ent.name} is logged under callsign {ent.nickname}, designated as {ent.ordinal}, and referred to in operational notes as {ent.descriptor}."
        )
    lines.append("")

    dist_cursor = 0

    def next_reg_dist() -> str:
        nonlocal dist_cursor
        s = reg_dist[dist_cursor % len(reg_dist)]
        dist_cursor += 1
        return s

    if page.is_long:
        # Group claims on this page by entity; build long sections (>= 18 lines before claim!)
        by_ent: dict[int, list[ClaimPlan]] = {}
        for cl in page_claims:
            by_ent.setdefault(cl.entity_idx, []).append(cl)
        # Ensure at least 3 entity sections for generous length (>= 75 lines)
        covered_ents = sorted(by_ent.keys())
        for e_idx in range(len(domain.entities)):
            if len(covered_ents) >= 3:
                break
            if e_idx not in covered_ents:
                covered_ents.append(e_idx)
        covered_ents.sort()

        for sec_num, e_idx in enumerate(covered_ents):
            ent = domain.entities[e_idx]
            lines.append(f"## {ent.name}")
            lines.append("")
            # Insert 18-24 lines of realistic operational background + distractors BEFORE the claim sentence
            for t_off in range(3):
                topic = domain.background_topics[(e_idx + sec_num + t_off) % len(domain.background_topics)]
                lines.append(topic)
                lines.append("")
                lines.append(f"Regional benchmark note: {next_reg_dist()}")
                lines.append("")
            lines.append("### Sector Telemetry Context")
            lines.append("")
            lines.append(f"- {next_reg_dist()}")
            lines.append(f"- {next_reg_dist()}")
            lines.append(f"- {next_reg_dist()}")
            lines.append("")
            lines.append("Shift crews verify adjacent instrumentation against the district baseline before entering final operating figures.")
            lines.append("")
            lines.append("Maintenance supervisors cross-check seasonal tolerances and historical logs prior to quarterly reporting.")
            lines.append("")

            ent_claims = by_ent.get(e_idx, [])
            if ent_claims:
                lines.append("### Verified Operating Parameters")
                lines.append("")
                for cl in ent_claims:
                    st, v_idx = occ_style[(page.filename, cl.cid)]
                    val = cl.cycle_values[cycle]
                    lead, main = _format_claim_occurrence(cl, val, st, v_idx)
                    if st == "nickname":
                        lines.append(f"- {main}")
                    elif lead:
                        lines.append(f"{lead} {main}")
                        lines.append("")
                    else:
                        lines.append(main)
                        lines.append("")
                if lines and lines[-1] != "":
                    lines.append("")
    else:
        # Medium Markdown page (tariffs or audit)
        lines.append("## Operational Findings and Schedule Notes")
        lines.append("")
        lines.append(domain.background_topics[page_idx % len(domain.background_topics)])
        lines.append("")
        nickname_items: list[str] = []
        prose_items: list[str] = []
        for cl in page_claims:
            st, v_idx = occ_style[(page.filename, cl.cid)]
            val = cl.cycle_values[cycle]
            lead, main = _format_claim_occurrence(cl, val, st, v_idx)
            if st == "nickname":
                nickname_items.append(f"- {main}")
            elif lead:
                prose_items.append(f"{lead} {main}")
            else:
                prose_items.append(main)

        for idx_p, item in enumerate(prose_items):
            lines.append(item)
            lines.append("")
            if idx_p % 2 == 0:
                lines.append(next_reg_dist())
                lines.append("")

        if nickname_items:
            lines.append("## Callsign Quick Summary")
            lines.append("")
            lines.extend(nickname_items)
            lines.append("")

    # Dedicated comparative / distractor section (includes any same-value-different-meaning distractors)
    lines.append("## Regional Comparative Benchmarks")
    lines.append("")
    lines.append("The figures below summarize adjacent sector measurements and historical reference benchmarks rather than current facility allocations.")
    lines.append("")
    for cd in coll_dist:
        lines.append(f"- {cd}")
    while dist_cursor < len(reg_dist):
        lines.append(f"- {reg_dist[dist_cursor]}")
        dist_cursor += 1
    lines.append("")
    lines.append("## Administrative Notice")
    lines.append("")
    lines.append(_noise_note_for_rev(domain, page_idx, noise_rev))
    lines.append("")
    return "\n".join(lines)


def _render_html_page(
    plan: dict[str, Any],
    page: PageSpec,
    page_idx: int,
    cycle: int,
) -> str:
    domain: DomainSpec = plan["domain"]
    claims: list[ClaimPlan] = plan["claims"]
    occ_style: dict[tuple[str, str], tuple[str, int]] = plan["occ_style"]
    reg_dist = list(plan["regular_distractors_by_page"][page.filename])
    coll_dist = list(plan["coll_distractors_by_page"][page.filename])
    noise_rev = plan["noise_revs"][cycle][page.filename]

    page_claims = [cl for cl in claims if page.filename in cl.source_pages]
    esc = html.escape

    lines: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        f"  <title>{esc(page.title)} — {esc(domain.title)}</title>",
        "</head>",
        "<body>",
        "  <main>",
        f"    <h1>{esc(page.title)}</h1>",
        f"    <p>Issued by {esc(domain.authority)} for the {esc(domain.region)} network.</p>",
        '    <section id="sec-legend">',
        "      <h2>Asset Directory and Callsigns</h2>",
        "      <ul>",
    ]
    for ent in domain.entities:
        lines.append(
            f"        <li>{esc(ent.name)} uses callsign {esc(ent.nickname)}, corresponds to {esc(ent.ordinal)}, and is noted as {esc(ent.descriptor)}.</li>"
        )
    lines.extend([
        "      </ul>",
        "    </section>",
    ])

    dist_cursor = 0

    def next_reg_dist() -> str:
        nonlocal dist_cursor
        s = reg_dist[dist_cursor % len(reg_dist)]
        dist_cursor += 1
        return s

    if page.is_long:
        by_ent: dict[int, list[ClaimPlan]] = {}
        for cl in page_claims:
            by_ent.setdefault(cl.entity_idx, []).append(cl)
        covered_ents = sorted(by_ent.keys())
        for e_idx in range(len(domain.entities)):
            if len(covered_ents) >= 3:
                break
            if e_idx not in covered_ents:
                covered_ents.append(e_idx)
        covered_ents.sort()

        for sec_num, e_idx in enumerate(covered_ents, start=1):
            ent = domain.entities[e_idx]
            lines.append(f'    <section id="sec-ent-{sec_num}">')
            lines.append(f"      <h2>{esc(ent.name)}</h2>")
            # 18+ lines of background & distractor blocks BEFORE the claim sentence
            for t_off in range(3):
                topic = domain.background_topics[(e_idx + sec_num + t_off + 1) % len(domain.background_topics)]
                lines.append("      <p>")
                lines.append(f"        {esc(topic)}")
                lines.append("      </p>")
                lines.append("      <p>")
                lines.append(f"        {esc(next_reg_dist())}")
                lines.append("      </p>")
            lines.append("      <h3>Reference Sector Notes</h3>")
            lines.append("      <ul>")
            lines.append(f"        <li>{esc(next_reg_dist())}</li>")
            lines.append(f"        <li>{esc(next_reg_dist())}</li>")
            lines.append(f"        <li>{esc(next_reg_dist())}</li>")
            lines.append("      </ul>")
            lines.append("      <p>")
            lines.append("        Engineering teams reconcile adjacent archive readings before certifying active operating figures.")
            lines.append("      </p>")

            ent_claims = by_ent.get(e_idx, [])
            if ent_claims:
                lines.append("      <h3>Certified Operating Figures</h3>")
                for cl in ent_claims:
                    st, v_idx = occ_style[(page.filename, cl.cid)]
                    val = cl.cycle_values[cycle]
                    lead, main = _format_claim_occurrence(cl, val, st, v_idx)
                    if lead:
                        lines.append(f"      <p>{esc(lead)} {esc(main)}</p>")
                    else:
                        lines.append(f"      <p>{esc(main)}</p>")
            lines.append("    </section>")
    else:
        lines.append('    <section id="sec-telemetry">')
        lines.append("      <h2>Active Telemetry and Field Parameters</h2>")
        lines.append(f"      <p>{esc(domain.background_topics[(page_idx + 2) % len(domain.background_topics)])}</p>")
        nick_items: list[str] = []
        for idx_c, cl in enumerate(page_claims):
            st, v_idx = occ_style[(page.filename, cl.cid)]
            val = cl.cycle_values[cycle]
            lead, main = _format_claim_occurrence(cl, val, st, v_idx)
            if st == "nickname":
                nick_items.append(main)
            elif lead:
                lines.append(f"      <p>{esc(lead)} {esc(main)}</p>")
            else:
                lines.append(f"      <p>{esc(main)}</p>")
            if idx_c % 2 == 0:
                lines.append(f"      <p>{esc(next_reg_dist())}</p>")
        if nick_items:
            lines.append("      <h3>Callsign Register</h3>")
            lines.append("      <ul>")
            for ni in nick_items:
                lines.append(f"        <li>{esc(ni)}</li>")
            lines.append("      </ul>")
        lines.append("    </section>")

    lines.append('    <section id="sec-benchmarks">')
    lines.append("      <h2>Adjacent Sector Benchmarks</h2>")
    lines.append("      <p>The following archival figures describe neighboring assets and historical tests rather than active facility specs.</p>")
    lines.append("      <ul>")
    for cd in coll_dist:
        lines.append(f"        <li>{esc(cd)}</li>")
    while dist_cursor < len(reg_dist):
        lines.append(f"        <li>{esc(reg_dist[dist_cursor])}</li>")
        dist_cursor += 1
    lines.append("      </ul>")
    lines.append("    </section>")
    lines.append("    <footer>")
    lines.append(f"      <p>Facility bulletin: {esc(_noise_note_for_rev(domain, page_idx, noise_rev))}</p>")
    lines.append("    </footer>")
    lines.append("  </main>")
    lines.append("</body>")
    lines.append("</html>")
    lines.append("")
    return "\n".join(lines)


def _render_txt_page(
    plan: dict[str, Any],
    page: PageSpec,
    page_idx: int,
    cycle: int,
) -> str:
    domain: DomainSpec = plan["domain"]
    claims: list[ClaimPlan] = plan["claims"]
    occ_style: dict[tuple[str, str], tuple[str, int]] = plan["occ_style"]
    reg_dist = list(plan["regular_distractors_by_page"][page.filename])
    coll_dist = list(plan["coll_distractors_by_page"][page.filename])
    noise_rev = plan["noise_revs"][cycle][page.filename]

    page_claims = [cl for cl in claims if page.filename in cl.source_pages]

    lines: list[str] = [
        f"=== {page.title.upper()} ===",
        f"Authority: {domain.authority}",
        f"Region: {domain.region}",
        "",
        "=== CALLSIGN AND ORDINAL KEY ===",
        "",
    ]
    for ent in domain.entities:
        lines.append(
            f"* {ent.nickname} = {ent.name} ({ent.ordinal}; also noted as {ent.descriptor})."
        )
    lines.append("")

    dist_cursor = 0

    def next_reg_dist() -> str:
        nonlocal dist_cursor
        s = reg_dist[dist_cursor % len(reg_dist)]
        dist_cursor += 1
        return s

    lines.append("=== OPERATIONAL CONTEXT ===")
    lines.append("")
    for t_off in range(3 if page.is_long else 2):
        lines.append(domain.background_topics[(page_idx + t_off) % len(domain.background_topics)])
        lines.append("")
        lines.append(next_reg_dist())
        lines.append("")

    # Table-free list keyed by nickname (plus prose notes)
    nick_lines: list[str] = []
    prose_lines: list[str] = []
    for cl in page_claims:
        st, v_idx = occ_style[(page.filename, cl.cid)]
        val = cl.cycle_values[cycle]
        lead, main = _format_claim_occurrence(cl, val, st, v_idx)
        if st == "nickname":
            nick_lines.append(f"* {main}")
        elif lead:
            prose_lines.append(f"{lead} {main}")
        else:
            prose_lines.append(main)

    if nick_lines:
        lines.append("=== CALLSIGN DISPATCH LIST ===")
        lines.append("")
        lines.extend(nick_lines)
        lines.append("")

    if prose_lines:
        lines.append("=== FIELD LOG ENTRIES ===")
        lines.append("")
        for idx_p, pl in enumerate(prose_lines):
            lines.append(pl)
            lines.append("")
            if idx_p % 2 == 0:
                lines.append(next_reg_dist())
                lines.append("")

    lines.append("=== ADJACENT SECTOR REFERENCE NUMBERS ===")
    lines.append("")
    lines.append("Historical and external benchmark readings are listed below for cross-reference only.")
    lines.append("")
    for cd in coll_dist:
        lines.append(f"- {cd}")
    while dist_cursor < len(reg_dist):
        lines.append(f"- {reg_dist[dist_cursor]}")
        dist_cursor += 1
    lines.append("")
    lines.append("=== ADMINISTRATIVE NOTE ===")
    lines.append("")
    lines.append(_noise_note_for_rev(domain, page_idx, noise_rev))
    lines.append("")
    return "\n".join(lines)


def render_page(plan: dict[str, Any], page: PageSpec, page_idx: int, cycle: int) -> str:
    if page.filename.endswith(".md"):
        return _render_md_page(plan, page, page_idx, cycle)
    if page.filename.endswith(".html"):
        return _render_html_page(plan, page, page_idx, cycle)
    if page.filename.endswith(".txt"):
        return _render_txt_page(plan, page, page_idx, cycle)
    raise ValueError(f"Unsupported page format: {page.filename}")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Main dataset generator
# ---------------------------------------------------------------------------

def generate_dataset(seed: int, n_sets: int, out_dir: Path) -> None:
    if n_sets < 1:
        raise ValueError("--sets must be >= 1")

    if out_dir.exists():
        if not out_dir.is_dir():
            raise RuntimeError(f"Output path exists and is not a directory: {out_dir}")
        if any(out_dir.iterdir()):
            raise RuntimeError(f"Refusing to write into non-empty directory: {out_dir}")
    else:
        out_dir.mkdir(parents=True, exist_ok=True)

    sets_manifest: list[dict[str, Any]] = []

    for set_idx in range(n_sets):
        plan = _build_set_plan(set_idx, seed)
        set_id: str = plan["set_id"]
        domain: DomainSpec = plan["domain"]
        index_name: str = plan["index_name"]
        selected_pages: list[PageSpec] = plan["selected_pages"]
        page_names: list[str] = plan["page_names"]
        claims: list[ClaimPlan] = plan["claims"]
        cycle_plans: list[dict[str, Any]] = plan["cycle_plans"]

        set_dir = out_dir / "sets" / set_id
        set_dir.mkdir(parents=True, exist_ok=True)

        # Write template.md
        template_text = render_template(plan)
        (set_dir / "template.md").write_text(template_text, encoding="utf-8")

        # Write cycles 0..4
        index_bytes = render_index(plan).encode("utf-8")
        page_sha256_by_cycle: list[dict[str, str]] = []

        for cycle in range(5):
            site_dir = set_dir / f"cycle_{cycle}" / "site"
            site_dir.mkdir(parents=True, exist_ok=True)

            cycle_hashes: dict[str, str] = {}
            (site_dir / index_name).write_bytes(index_bytes)
            cycle_hashes[index_name] = _sha256_bytes(index_bytes)

            for p_idx, page in enumerate(selected_pages):
                content_bytes = render_page(plan, page, p_idx, cycle).encode("utf-8")
                (site_dir / page.filename).write_bytes(content_bytes)
                cycle_hashes[page.filename] = _sha256_bytes(content_bytes)

            page_sha256_by_cycle.append(cycle_hashes)

        truth_list = [
            {cl.cid: cl.cycle_values[cycle] for cl in claims}
            for cycle in range(5)
        ]

        claims_manifest = [
            {
                "id": cl.cid,
                "entity": cl.entity.name,
                "label": cl.attr.label,
                "template_line": cl.template_line,
                "source_pages": list(cl.source_pages),
            }
            for cl in claims
        ]

        sets_manifest.append({
            "set": set_id,
            "domain": domain.domain_id,
            "index": index_name,
            "pages": page_names,
            "claims": claims_manifest,
            "truth": truth_list,
            "cycles": cycle_plans,
            "page_sha256": page_sha256_by_cycle,
        })

    manifest = {
        "schema": SCHEMA_VERSION,
        "generator": GENERATOR_NAME,
        "seed": seed,
        "n_sets": n_sets,
        "cycle_types": list(CYCLE_TYPES_BASE),
        "sets": sets_manifest,
    }

    manifest_bytes = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    (out_dir / "manifest.json").write_bytes(manifest_bytes)
    manifest_digest = _sha256_bytes(manifest_bytes)
    (out_dir / "manifest.sha256").write_text(f"{manifest_digest}\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate heldout-v2 benchmark sets.")
    parser.add_argument("--seed", type=int, required=True, help="Deterministic integer RNG seed.")
    parser.add_argument("--sets", type=int, required=True, help="Number of sets to generate (>= 1).")
    parser.add_argument("--out", type=Path, required=True, help="Output directory (must not be non-empty).")
    args = parser.parse_args(argv)

    try:
        generate_dataset(seed=args.seed, n_sets=args.sets, out_dir=args.out)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
