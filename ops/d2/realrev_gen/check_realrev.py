#!/usr/bin/env python3
"""Validate a frozen realrev dataset directory and print measured shares.

Usage:
  check_realrev.py <dir>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from realrev_lib import (
    DOMAIN_NAME,
    LICENSE_NOTE,
    MANIFEST_GENERATOR,
    MANIFEST_SCHEMA,
    TEMPLATE_INSTRUCTION,
    TEMPLATE_TITLE,
    classify_value_shape,
    compute_timepoints,
    extract_infobox_claims,
    normalize_ws,
    parse_iso_utc,
    sha256_bytes,
)

PAGE_NAME_RE = re.compile(r"^[a-z0-9-]+\.html$")


class _LinkAndTagInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []
        self.has_script = False
        self.has_style = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t == "script":
            self.has_script = True
        elif t == "style":
            self.has_style = True
        elif t == "a":
            for k, v in attrs:
                if k.lower() == "href" and v is not None:
                    self.hrefs.append(v)


def check_dataset(root: Path) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []

    manifest_path = root / "manifest.json"
    sha_path = root / "manifest.sha256"
    sources_path = root / "SOURCES.md"

    if not manifest_path.is_file():
        errors.append(f"Missing {manifest_path}")
        return errors, {}
    if not sha_path.is_file():
        errors.append(f"Missing {sha_path}")
    if not sources_path.is_file():
        errors.append(f"Missing {sources_path}")

    manifest_bytes = manifest_path.read_bytes()
    actual_manifest_sha = sha256_bytes(manifest_bytes)
    if sha_path.is_file():
        recorded_sha = sha_path.read_text(encoding="utf-8")
        if recorded_sha != actual_manifest_sha + "\n":
            errors.append(
                f"manifest.sha256 mismatch: expected {actual_manifest_sha!r}+newline, "
                f"got {recorded_sha!r}"
            )

    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except Exception as exc:
        errors.append(f"Invalid manifest.json: {exc}")
        return errors, {}

    if manifest.get("schema") != MANIFEST_SCHEMA:
        errors.append(f"Invalid schema: {manifest.get('schema')!r}")
    if manifest.get("generator") != MANIFEST_GENERATOR:
        errors.append(f"Invalid generator: {manifest.get('generator')!r}")
    if not isinstance(manifest.get("seed"), int):
        errors.append(f"Invalid seed: {manifest.get('seed')!r}")

    n_sets = manifest.get("n_sets")
    sets = manifest.get("sets")
    if not isinstance(n_sets, int) or n_sets < 1:
        errors.append(f"Invalid n_sets: {n_sets!r}")
    if not isinstance(sets, list) or len(sets) != n_sets:
        errors.append(f"sets length mismatch: expected {n_sets}, got {type(sets).__name__}")
        return errors, {}

    window = manifest.get("window", {})
    end_str = window.get("end")
    days = window.get("days")
    timepoints = window.get("timepoints")
    if not isinstance(end_str, str) or not isinstance(days, int) or not isinstance(timepoints, list):
        errors.append("Invalid window metadata")
    else:
        expected_tps = compute_timepoints(end_str, days)
        if timepoints != expected_tps:
            errors.append(f"window.timepoints mismatch: expected {expected_tps}, got {timepoints}")

    sources_text = sources_path.read_text(encoding="utf-8") if sources_path.is_file() else ""
    if sources_path.is_file() and LICENSE_NOTE not in sources_text:
        errors.append(f"SOURCES.md missing license note {LICENSE_NOTE!r}")

    total_articles = 0
    total_claims = 0
    claims_changed_once = 0
    cycle_type_counts: Counter[str] = Counter()
    value_shape_counts: Counter[str] = Counter()

    for s_entry in sets:
        set_name = s_entry.get("set")
        if not isinstance(set_name, str) or not set_name:
            errors.append(f"Invalid set name: {set_name!r}")
            continue

        set_dir = root / "sets" / set_name
        if not set_dir.is_dir():
            errors.append(f"[{set_name}] Missing set directory {set_dir}")
            continue

        if not s_entry.get("domain"):
            errors.append(f"[{set_name}] Unexpected domain: {s_entry.get('domain')!r}")
        if s_entry.get("index") != "index.html":
            errors.append(f"[{set_name}] Unexpected index: {s_entry.get('index')!r}")

        pages = s_entry.get("pages")
        if not isinstance(pages, list) or not (3 <= len(pages) <= 6) or len(set(pages)) != len(pages):
            errors.append(f"[{set_name}] pages must be 3..6 distinct filenames, got {pages!r}")
            continue
        for p in pages:
            if not isinstance(p, str) or p == "index.html" or not PAGE_NAME_RE.match(p):
                errors.append(f"[{set_name}] Invalid page filename: {p!r}")

        total_articles += len(pages)

        claims = s_entry.get("claims")
        if not isinstance(claims, list) or not (8 <= len(claims) <= 20):
            errors.append(
                f"[{set_name}] claims count must be in 8..20, got {len(claims) if isinstance(claims, list) else type(claims).__name__}"
            )
            continue

        total_claims += len(claims)

        claim_ids: list[str] = []
        claim_by_id: dict[str, dict[str, Any]] = {}
        seen_prefixes: set[str] = set()
        per_page_claim_count: Counter[str] = Counter()

        for idx, c in enumerate(claims, start=1):
            expected_cid = f"c{idx:02d}"
            cid = c.get("id")
            if cid != expected_cid:
                errors.append(f"[{set_name}] Expected claim id {expected_cid}, got {cid!r}")
            entity = c.get("entity")
            label = c.get("label")
            tline = c.get("template_line")
            spages = c.get("source_pages")
            expected_tline = f"- {entity} \u2014 {label}: "
            if tline != expected_tline:
                errors.append(
                    f"[{set_name}:{cid}] template_line mismatch: expected {expected_tline!r}, got {tline!r}"
                )
            if tline in seen_prefixes:
                errors.append(f"[{set_name}:{cid}] Duplicate template_line prefix: {tline!r}")
            seen_prefixes.add(tline)

            if not isinstance(spages, list) or len(spages) != 1 or spages[0] not in pages:
                errors.append(f"[{set_name}:{cid}] Invalid source_pages: {spages!r}")
            else:
                per_page_claim_count[spages[0]] += 1

            claim_ids.append(cid)
            claim_by_id[cid] = c

        for p, cnt in per_page_claim_count.items():
            if cnt > 8:
                errors.append(f"[{set_name}] Page {p} has {cnt} claims (> 8)")

        # Verify template.md
        tmpl_path = set_dir / "template.md"
        if not tmpl_path.is_file():
            errors.append(f"[{set_name}] Missing template.md")
        else:
            non_empty = [
                line for line in tmpl_path.read_text(encoding="utf-8").splitlines() if line.strip()
            ]
            expected_lines = [
                non_empty[0] if non_empty and non_empty[0].startswith("# ") else TEMPLATE_TITLE,
                TEMPLATE_INSTRUCTION,
                *[f"{c['template_line']}____" for c in claims],
            ]
            if non_empty != expected_lines:
                errors.append(
                    f"[{set_name}] template.md lines mismatch "
                    f"(expected {len(expected_lines)} non-empty lines, got {len(non_empty)})"
                )

        truth = s_entry.get("truth")
        page_sha256 = s_entry.get("page_sha256")
        revisions = s_entry.get("revisions")
        cycles = s_entry.get("cycles")

        if not isinstance(truth, list) or len(truth) != 5:
            errors.append(f"[{set_name}] truth must have 5 entries")
            continue
        if not isinstance(page_sha256, list) or len(page_sha256) != 5:
            errors.append(f"[{set_name}] page_sha256 must have 5 entries")
            continue
        if not isinstance(revisions, list) or len(revisions) != 5:
            errors.append(f"[{set_name}] revisions must have 5 entries")
            continue
        if not isinstance(cycles, list) or len(cycles) != 4:
            errors.append(f"[{set_name}] cycles must have 4 entries")
            continue

        # Per-cycle file, sha256, revision, index, and infobox verbatim checks
        for k in range(5):
            site_dir = set_dir / f"cycle_{k}" / "site"
            if not site_dir.is_dir():
                errors.append(f"[{set_name}:cycle_{k}] Missing site dir {site_dir}")
                continue

            idx_path = site_dir / "index.html"
            if not idx_path.is_file():
                errors.append(f"[{set_name}:cycle_{k}] Missing index.html")
            else:
                insp = _LinkAndTagInspector()
                insp.feed(idx_path.read_text(encoding="utf-8"))
                missing_links = [p for p in pages if p not in insp.hrefs]
                if missing_links:
                    errors.append(
                        f"[{set_name}:cycle_{k}] index.html missing links to {missing_links}"
                    )

            if set(page_sha256[k].keys()) != set(pages):
                errors.append(f"[{set_name}:cycle_{k}] page_sha256 keys != pages")
            if set(revisions[k].keys()) != set(pages):
                errors.append(f"[{set_name}:cycle_{k}] revisions keys != pages")
            if set(truth[k].keys()) != set(claim_ids):
                errors.append(f"[{set_name}:cycle_{k}] truth keys != claim ids")

            infobox_by_page: dict[str, dict[str, tuple[str, str]]] = {}

            for p in pages:
                fpath = site_dir / p
                if not fpath.is_file():
                    errors.append(f"[{set_name}:cycle_{k}] Missing page file {fpath}")
                    continue
                raw_bytes = fpath.read_bytes()
                actual_sha = sha256_bytes(raw_bytes)
                if page_sha256[k].get(p) != actual_sha:
                    errors.append(
                        f"[{set_name}:cycle_{k}] SHA-256 mismatch for {p}: "
                        f"manifest={page_sha256[k].get(p)}, actual={actual_sha}"
                    )

                html_str = raw_bytes.decode("utf-8")
                insp = _LinkAndTagInspector()
                insp.feed(html_str)
                if insp.has_script or insp.has_style:
                    errors.append(
                        f"[{set_name}:cycle_{k}] Page {p} still contains <script> or <style>"
                    )

                parsed = extract_infobox_claims(html_str)
                infobox_by_page[p] = {lbl: (val, row_txt) for lbl, val, row_txt in parsed}

                rev_info = revisions[k].get(p, {})
                r_title = rev_info.get("title")
                r_id = rev_info.get("revid")
                r_ts = rev_info.get("timestamp")
                if not isinstance(r_title, str) or not isinstance(r_id, int) or not isinstance(r_ts, str):
                    errors.append(f"[{set_name}:cycle_{k}] Invalid revision metadata for {p}")
                else:
                    if isinstance(timepoints, list) and len(timepoints) == 5:
                        if parse_iso_utc(r_ts) > parse_iso_utc(timepoints[k]):
                            errors.append(
                                f"[{set_name}:cycle_{k}] Revision timestamp {r_ts} > t_{k} ({timepoints[k]})"
                            )
                    if sources_text:
                        if str(r_id) not in sources_text or actual_sha not in sources_text:
                            errors.append(
                                f"[{set_name}:cycle_{k}] SOURCES.md missing revid={r_id} / sha={actual_sha}"
                            )

            # Verify every truth value at cycle k appears verbatim in cycle-k infobox under its label
            for c in claims:
                cid = c["id"]
                val = truth[k].get(cid)
                if not isinstance(val, str) or not val:
                    errors.append(f"[{set_name}:cycle_{k}:{cid}] Empty/non-str truth value")
                    continue
                value_shape_counts[classify_value_shape(val)] += 1

                sp = c["source_pages"][0]
                ib_map = infobox_by_page.get(sp, {})
                lbl = c["label"]
                if lbl not in ib_map:
                    errors.append(
                        f"[{set_name}:cycle_{k}:{cid}] Label {lbl!r} not found in {sp} infobox"
                    )
                else:
                    parsed_val, row_txt = ib_map[lbl]
                    norm_val = normalize_ws(val)
                    if parsed_val != norm_val:
                        errors.append(
                            f"[{set_name}:cycle_{k}:{cid}] Truth value {norm_val!r} != "
                            f"infobox value {parsed_val!r} under label {lbl!r} in {sp}"
                        )
                    elif norm_val not in row_txt:
                        errors.append(
                            f"[{set_name}:cycle_{k}:{cid}] Truth value {norm_val!r} "
                            f"not verbatim in row text {row_txt!r}"
                        )

        # Count claims that change at least once across cycles 0..4
        for cid in claim_ids:
            vals = {truth[k].get(cid) for k in range(5)}
            if len(vals) > 1:
                claims_changed_once += 1

        # Verify cycle transitions k = 1..4
        for k in range(1, 5):
            centry = cycles[k - 1]
            if centry.get("cycle") != k:
                errors.append(f"[{set_name}] Expected cycle {k}, got {centry.get('cycle')!r}")

            expected_changed_claims = [
                cid for cid in claim_ids if truth[k].get(cid) != truth[k - 1].get(cid)
            ]
            if centry.get("changed_claims") != expected_changed_claims:
                errors.append(
                    f"[{set_name}:cycle_{k}] changed_claims mismatch: "
                    f"expected {expected_changed_claims}, got {centry.get('changed_claims')}"
                )

            changed_pages = [
                p for p in pages if page_sha256[k].get(p) != page_sha256[k - 1].get(p)
            ]
            claim_changed_pages = {
                p for cid in expected_changed_claims for p in claim_by_id[cid]["source_pages"]
            }
            if not claim_changed_pages.issubset(set(changed_pages)):
                errors.append(
                    f"[{set_name}:cycle_{k}] Claim changed on page(s) whose sha256 did not change: "
                    f"{claim_changed_pages - set(changed_pages)}"
                )

            expected_noise_pages = [p for p in changed_pages if p not in claim_changed_pages]
            if centry.get("noise_pages") != expected_noise_pages:
                errors.append(
                    f"[{set_name}:cycle_{k}] noise_pages mismatch: "
                    f"expected {expected_noise_pages}, got {centry.get('noise_pages')}"
                )

            if expected_changed_claims:
                expected_type = "F"
            elif changed_pages:
                expected_type = "N"
            else:
                expected_type = "Z"

            if centry.get("type") != expected_type:
                errors.append(
                    f"[{set_name}:cycle_{k}] cycle type mismatch: "
                    f"expected {expected_type!r}, got {centry.get('type')!r}"
                )
            cycle_type_counts[expected_type] += 1

    metrics = {
        "n_sets": len(sets),
        "n_articles": total_articles,
        "n_claims": total_claims,
        "claims_changed_once": claims_changed_once,
        "cycle_type_counts": cycle_type_counts,
        "value_shape_counts": value_shape_counts,
    }
    return errors, metrics


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Check a frozen realrev dataset and print measured shares."
    )
    ap.add_argument("dir", type=Path, help="Dataset directory to validate")
    args = ap.parse_args(argv)

    root = args.dir.resolve()
    errors, metrics = check_dataset(root)

    if errors:
        print(f"FAIL: {len(errors)} violation(s) found in {root}:", file=sys.stderr)
        for err in errors[:50]:
            print(f"  - {err}", file=sys.stderr)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more", file=sys.stderr)
        return 1

    n_sets = metrics["n_sets"]
    n_articles = metrics["n_articles"]
    n_claims = metrics["n_claims"]
    changed_once = metrics["claims_changed_once"]
    changed_share = (changed_once / n_claims) if n_claims else 0.0
    ctypes: Counter[str] = metrics["cycle_type_counts"]
    total_cycles = sum(ctypes.values())
    shapes: Counter[str] = metrics["value_shape_counts"]
    total_vals = sum(shapes.values())

    print(f"PASS: {root}")
    print(f"Sets: {n_sets}")
    print(f"Articles: {n_articles}")
    print(f"Claims: {n_claims}")
    print(
        f"Claims changing >=1 time: {changed_once}/{n_claims} ({changed_share * 100:.1f}%)"
    )
    print("Cycle type counts (k=1..4):")
    for t in ("F", "N", "Z"):
        cnt = ctypes.get(t, 0)
        pct = (cnt / total_cycles * 100.0) if total_cycles else 0.0
        print(f"  {t}: {cnt}/{total_cycles} ({pct:.1f}%)")
    print(f"Value shape distribution (across {total_vals} claim-cycle values):")
    for shape in ("plain integer", '"a (b)"', "with unit", "other"):
        cnt = shapes.get(shape, 0)
        pct = (cnt / total_vals * 100.0) if total_vals else 0.0
        print(f"  {shape}: {cnt}/{total_vals} ({pct:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
