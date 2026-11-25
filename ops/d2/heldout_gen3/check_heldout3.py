#!/usr/bin/env python3
"""Validator and metric measurer for heldout-v3 benchmark datasets."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "vacant.d2.manifest/1"
GENERATOR_NAME = "heldout-v3"
ALLOWED_CONTENT_EXTS = {".json", ".csv", ".txt", ".md", ".html"}
STRUCTURED_EXTS = {".json", ".csv", ".txt"}
ALLOWED_INDEX_EXTS = {".html", ".md"}
VALID_PLACEHOLDERS = {"{{FETCH_TS}}", "{{FETCH_COUNT}}", "{{FETCH_ID}}"}

# Value string: either one version string (vX.Y.Z) OR one number with optional unit/currency
VALUE_RE = re.compile(
    r"^(?:v\d+\.\d+\.\d+|-?\d+(?:\.\d+)?(?:%| [A-Za-z][A-Za-z/-]*)?)$"
)
BAD_SLUG_RE = re.compile(r"^p\d+", re.IGNORECASE)
PLACEHOLDER_BRACES_RE = re.compile(r"\{\{[^}]*\}\}")
CLAIM_LINE_RE = re.compile(r"^- (.+) \u2014 (.+): ____$")


class LeafTextExtractor(HTMLParser):
    """Collect text inside leaf HTML elements (td, th, li, p, span, dd, dt)."""

    TARGET_TAGS = {"td", "th", "li", "p", "span", "dd", "dt"}

    def __init__(self) -> None:
        super().__init__()
        self._stack: list[str] = []
        self._buf: list[str] = []
        self.cells: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self._stack.append(tag)
        if tag in self.TARGET_TAGS:
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.TARGET_TAGS:
            text = "".join(self._buf).strip()
            if text:
                self.cells.append(text)
            self._buf = []
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        if any(t in self.TARGET_TAGS for t in self._stack):
            self._buf.append(data)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def iter_json_string_leaves(obj: Any, path: str = "$") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.extend(iter_json_string_leaves(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(iter_json_string_leaves(v, f"{path}[{i}]"))
    elif isinstance(obj, str):
        out.append((path, obj))
    return out


def json_object_has_val_and_placeholder(obj: Any, val: str) -> bool:
    """Return True if any JSON dict contains a leaf string == val AND a leaf string with a placeholder."""
    if isinstance(obj, dict):
        str_vals = [v for v in obj.values() if isinstance(v, str)]
        has_val = any(v == val for v in str_vals)
        has_ph = any(any(ph in v for ph in VALID_PLACEHOLDERS) for v in str_vals)
        if has_val and has_ph:
            return True
        return any(json_object_has_val_and_placeholder(v, val) for v in obj.values())
    if isinstance(obj, list):
        return any(json_object_has_val_and_placeholder(v, val) for v in obj)
    return False


def bounded_match(line: str, val: str) -> bool:
    """Check if val appears in line with non-alphanumeric boundaries (not part of a larger number/word)."""
    pattern = r"(?<![A-Za-z0-9.])" + re.escape(val) + r"(?![A-Za-z0-9.])"
    return re.search(pattern, line) is not None


def count_value_occurrences_for_different_items(page_name: str, text: str, val: str) -> int:
    """Count distinct item/attribute slots on page carrying exact value val."""
    ext = Path(page_name).suffix.lower()
    if ext == ".json":
        data = json.loads(text)
        leaves = iter_json_string_leaves(data)
        return sum(1 for _, leaf in leaves if leaf == val)
    if ext == ".csv":
        rows = list(csv.reader(io.StringIO(text)))
        count = 0
        for row in rows[1:]:  # skip header
            for cell in row:
                if cell == val:
                    count += 1
        return count
    if ext == ".html":
        parser = LeafTextExtractor()
        parser.feed(text)
        return sum(1 for cell in parser.cells if cell == val or bounded_match(cell, val))
    if ext == ".md":
        count = 0
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("|") and s.endswith("|"):
                cells = [c.strip() for c in s.strip("|").split("|")]
                count += sum(1 for c in cells if c == val)
            elif bounded_match(line, val):
                count += 1
        return count
    if ext == ".txt":
        count = 0
        for line in text.splitlines():
            if not line.strip():
                continue
            # Split fixed-width table columns by >= 2 spaces
            cells = [c.strip() for c in re.split(r" {2,}", line.strip()) if c.strip()]
            cell_hits = sum(1 for c in cells if c == val)
            if cell_hits > 0:
                count += cell_hits
            elif bounded_match(line, val):
                count += 1
        return count
    return 0


def has_placeholder_same_line_or_row(page_name: str, text: str, val: str) -> bool:
    """Check if a valid placeholder appears on the same line / JSON object line / CSV row as val."""
    ext = Path(page_name).suffix.lower()
    if ext == ".csv":
        rows = list(csv.reader(io.StringIO(text)))
        for row in rows[1:]:
            has_val = any(cell == val for cell in row)
            has_ph = any(any(ph in cell for ph in VALID_PLACEHOLDERS) for cell in row)
            if has_val and has_ph:
                return True
        return False
    if ext == ".json":
        data = json.loads(text)
        # Must be in the SAME JSON object AND on the same physical line in raw text
        if not json_object_has_val_and_placeholder(data, val):
            return False
        for line in text.splitlines():
            if f'"{val}"' in line and any(ph in line for ph in VALID_PLACEHOLDERS):
                return True
        return False
    # .txt, .md, .html: same physical line
    for line in text.splitlines():
        if bounded_match(line, val) and any(ph in line for ph in VALID_PLACEHOLDERS):
            return True
    return False


def check_placeholders_in_file(
    file_label: str,
    text: str,
    errors: list[str],
) -> None:
    found = PLACEHOLDER_BRACES_RE.findall(text)
    if not found:
        errors.append(f"{file_label}: missing required per-fetch placeholder")
        return
    for tok in found:
        if tok not in VALID_PLACEHOLDERS:
            errors.append(f"{file_label}: invalid placeholder token {tok!r}")
    stripped = text
    for ph in VALID_PLACEHOLDERS:
        stripped = stripped.replace(ph, "")
    if "{{" in stripped:
        errors.append(f"{file_label}: malformed/unclosed '{{{{' outside valid placeholders")


def check_dataset(root: Path) -> int:
    errors: list[str] = []

    manifest_path = root / "manifest.json"
    sha_path = root / "manifest.sha256"

    if not manifest_path.is_file():
        print(f"FAIL: missing {manifest_path}", file=sys.stderr)
        return 1
    if not sha_path.is_file():
        print(f"FAIL: missing {sha_path}", file=sys.stderr)
        return 1

    manifest_bytes = manifest_path.read_bytes()
    actual_manifest_sha = sha256_bytes(manifest_bytes)
    sha_text = sha_path.read_text(encoding="utf-8")
    if not sha_text.endswith("\n"):
        errors.append("manifest.sha256: missing trailing newline")
    expected_sha = sha_text.strip()
    if expected_sha != actual_manifest_sha:
        errors.append(
            f"manifest.sha256 mismatch: file has {expected_sha!r}, actual {actual_manifest_sha!r}"
        )

    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except Exception as exc:
        print(f"FAIL: manifest.json invalid JSON: {exc}", file=sys.stderr)
        return 1

    # Top-level schema checks
    if manifest.get("schema") != SCHEMA_VERSION:
        errors.append(f"manifest.schema != {SCHEMA_VERSION!r}: {manifest.get('schema')!r}")
    if manifest.get("generator") != GENERATOR_NAME:
        errors.append(f"manifest.generator != {GENERATOR_NAME!r}: {manifest.get('generator')!r}")
    if not isinstance(manifest.get("seed"), int) or isinstance(manifest.get("seed"), bool):
        errors.append(f"manifest.seed must be int: {manifest.get('seed')!r}")
    n_sets = manifest.get("n_sets")
    if not isinstance(n_sets, int) or n_sets < 1:
        errors.append(f"manifest.n_sets must be positive int: {n_sets!r}")
    if manifest.get("cycle_types") != ["F", "F", "N", "Z"]:
        errors.append(f"manifest.cycle_types must be ['F','F','N','Z']: {manifest.get('cycle_types')!r}")

    sets_list = manifest.get("sets")
    if not isinstance(sets_list, list) or len(sets_list) != n_sets:
        errors.append(f"manifest.sets length mismatch: expected {n_sets}, got {type(sets_list)}")
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    sets_dir = root / "sets"
    if not sets_dir.is_dir():
        errors.append(f"missing directory {sets_dir}")
    else:
        actual_set_dirs = sorted(p.name for p in sets_dir.iterdir() if p.is_dir())
        expected_set_dirs = [f"s{i:02d}" for i in range(1, n_sets + 1)]
        if actual_set_dirs != expected_set_dirs:
            errors.append(f"sets/ subdirs {actual_set_dirs} != expected {expected_set_dirs}")

    # Global metric accumulators
    total_claims = 0
    a_structured_only = 0
    b_same_val_dup = 0
    c_multi_entities = 0
    c_split_entities = 0
    d_same_line_ph = 0

    saw_json_pretty = False
    saw_json_compact = False
    domains_seen: set[str] = set()

    for idx, s in enumerate(sets_list, start=1):
        expected_sid = f"s{idx:02d}"
        sid = s.get("set")
        if sid != expected_sid:
            errors.append(f"set[{idx-1}].set={sid!r} != {expected_sid!r}")
        domain = s.get("domain")
        if not isinstance(domain, str) or not domain.strip():
            errors.append(f"{sid}: invalid domain {domain!r}")
        else:
            domains_seen.add(domain)

        index_file = s.get("index")
        pages = s.get("pages")
        if not isinstance(index_file, str) or Path(index_file).suffix.lower() not in ALLOWED_INDEX_EXTS:
            errors.append(f"{sid}: invalid index {index_file!r}")
        elif "/" in index_file or ".." in index_file or BAD_SLUG_RE.match(Path(index_file).stem):
            errors.append(f"{sid}: invalid index filename {index_file!r}")

        if not isinstance(pages, list) or not (5 <= len(pages) <= 8):
            errors.append(f"{sid}: pages must have 5-8 content pages, got {len(pages) if isinstance(pages, list) else pages!r}")
            continue
        if len(set(pages)) != len(pages):
            errors.append(f"{sid}: duplicate entries in pages")
        if index_file in pages:
            errors.append(f"{sid}: index {index_file!r} must not appear in pages")

        exts_used: set[str] = set()
        for p in pages:
            if not isinstance(p, str) or "/" in p or ".." in p:
                errors.append(f"{sid}: invalid page filename {p!r}")
                continue
            ext = Path(p).suffix.lower()
            if ext not in ALLOWED_CONTENT_EXTS:
                errors.append(f"{sid}: disallowed extension for {p!r}")
            else:
                exts_used.add(ext)
            if BAD_SLUG_RE.match(Path(p).stem):
                errors.append(f"{sid}: page slug must be descriptive (not p<digit>): {p!r}")
        if len(exts_used) < 4:
            errors.append(f"{sid}: uses only {len(exts_used)} formats ({sorted(exts_used)}); need >= 4")

        # Validate claims
        claims = s.get("claims")
        if not isinstance(claims, list) or len(claims) != 20:
            errors.append(f"{sid}: claims must have length 20")
            continue

        claim_by_id: dict[str, dict[str, Any]] = {}
        seen_prefixes: set[str] = set()
        pages_set = set(pages)
        for c_i, c in enumerate(claims, start=1):
            exp_cid = f"c{c_i:02d}"
            cid = c.get("id")
            if cid != exp_cid:
                errors.append(f"{sid}: claim[{c_i-1}].id={cid!r} != {exp_cid!r}")
            ent = c.get("entity")
            lbl = c.get("label")
            tline = c.get("template_line")
            spages = c.get("source_pages")
            if not isinstance(ent, str) or not ent.strip():
                errors.append(f"{sid}/{cid}: invalid entity {ent!r}")
            if not isinstance(lbl, str) or not lbl.strip():
                errors.append(f"{sid}/{cid}: invalid label {lbl!r}")
            exp_tline = f"- {ent} \u2014 {lbl}: "
            if tline != exp_tline:
                errors.append(f"{sid}/{cid}: template_line {tline!r} != {exp_tline!r}")
            if tline in seen_prefixes:
                errors.append(f"{sid}/{cid}: duplicate template_line {tline!r}")
            seen_prefixes.add(tline)
            if not isinstance(spages, list) or not spages or len(set(spages)) != len(spages):
                errors.append(f"{sid}/{cid}: invalid source_pages {spages!r}")
            else:
                for sp in spages:
                    if sp not in pages_set:
                        errors.append(f"{sid}/{cid}: source_page {sp!r} not in pages")
            claim_by_id[cid] = c

        # Validate template.md
        tmpl_path = sets_dir / sid / "template.md"
        if not tmpl_path.is_file():
            errors.append(f"{sid}: missing {tmpl_path}")
        else:
            non_empty = [ln for ln in tmpl_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            if len(non_empty) < 22:
                errors.append(f"{sid}/template.md: too few non-empty lines ({len(non_empty)})")
            else:
                if not non_empty[0].startswith("# "):
                    errors.append(f"{sid}/template.md: first line must be title ('# ...'), got {non_empty[0]!r}")
                if non_empty[1].startswith("#") or non_empty[1].startswith("- "):
                    errors.append(f"{sid}/template.md: second non-empty line must be instruction line, got {non_empty[1]!r}")
                tmpl_claim_lines: list[str] = []
                for ln in non_empty[2:]:
                    if ln.startswith("## "):
                        continue
                    m = CLAIM_LINE_RE.match(ln)
                    if not m:
                        errors.append(f"{sid}/template.md: unexpected line format: {ln!r}")
                    else:
                        tmpl_claim_lines.append(ln)
                if len(tmpl_claim_lines) != 20:
                    errors.append(f"{sid}/template.md: expected 20 claim lines, got {len(tmpl_claim_lines)}")
                else:
                    expected_lines = [c["template_line"] + "____" for c in claims]
                    if set(tmpl_claim_lines) != set(expected_lines):
                        errors.append(f"{sid}/template.md: claim lines do not match manifest claims")

        # Validate truth[0..4], cycles[1..4], page_sha256[0..4]
        truth = s.get("truth")
        cycles = s.get("cycles")
        page_sha256 = s.get("page_sha256")
        if not isinstance(truth, list) or len(truth) != 5:
            errors.append(f"{sid}: truth must have length 5")
            continue
        if not isinstance(cycles, list) or len(cycles) != 4:
            errors.append(f"{sid}: cycles must have length 4")
            continue
        if not isinstance(page_sha256, list) or len(page_sha256) != 5:
            errors.append(f"{sid}: page_sha256 must have length 5")
            continue

        expected_cids = set(claim_by_id.keys())
        for k in range(5):
            if set(truth[k].keys()) != expected_cids:
                errors.append(f"{sid}: truth[{k}] keys mismatch")
            else:
                for cid, val in truth[k].items():
                    if not isinstance(val, str) or "{{" in val or "}}" in val:
                        errors.append(f"{sid}: truth[{k}][{cid}] invalid value {val!r}")
                    elif not VALUE_RE.match(val):
                        errors.append(f"{sid}: truth[{k}][{cid}] fails value syntax: {val!r}")

        # Verify site files and page_sha256 across cycles 0..4
        all_site_files = {index_file} | pages_set
        site_texts: list[dict[str, str]] = []
        for k in range(5):
            site_dir = sets_dir / sid / f"cycle_{k}" / "site"
            if not site_dir.is_dir():
                errors.append(f"{sid}: missing {site_dir}")
                site_texts.append({})
                continue
            actual_files = {p.name for p in site_dir.iterdir() if p.is_file()}
            if actual_files != all_site_files:
                errors.append(f"{sid}/cycle_{k}: site files {sorted(actual_files)} != expected {sorted(all_site_files)}")
            if set(page_sha256[k].keys()) != all_site_files:
                errors.append(f"{sid}: page_sha256[{k}] keys != expected site files")

            texts_k: dict[str, str] = {}
            for fname in sorted(actual_files):
                fpath = site_dir / fname
                raw = fpath.read_bytes()
                dig = sha256_bytes(raw)
                if page_sha256[k].get(fname) != dig:
                    errors.append(f"{sid}/cycle_{k}/{fname}: sha256 mismatch")
                text = raw.decode("utf-8")
                texts_k[fname] = text
                check_placeholders_in_file(f"{sid}/cycle_{k}/{fname}", text, errors)

                # Format syntax validation
                ext = Path(fname).suffix.lower()
                if fname == index_file:
                    for cp in pages:
                        if ext == ".html":
                            if f'href="{cp}"' not in text and f"href='{cp}'" not in text:
                                errors.append(f"{sid}/cycle_{k}/{fname}: missing relative link to {cp}")
                        else:
                            if f"]({cp})" not in text:
                                errors.append(f"{sid}/cycle_{k}/{fname}: missing markdown link to {cp}")
                elif ext == ".json":
                    try:
                        json.loads(text)
                    except Exception as exc:
                        errors.append(f"{sid}/cycle_{k}/{fname}: invalid JSON: {exc}")
                    n_lines = len(text.splitlines())
                    if n_lines == 1:
                        saw_json_compact = True
                    elif n_lines > 1:
                        saw_json_pretty = True
                elif ext == ".csv":
                    rows = list(csv.reader(io.StringIO(text)))
                    if len(rows) < 3:
                        errors.append(f"{sid}/cycle_{k}/{fname}: CSV needs header + >=2 data rows")
                    else:
                        ncols = len(rows[0])
                        if any(len(r) != ncols for r in rows[1:]):
                            errors.append(f"{sid}/cycle_{k}/{fname}: inconsistent CSV column counts")
                elif ext == ".html":
                    if "<html" not in text.lower() or "</html>" not in text.lower():
                        errors.append(f"{sid}/cycle_{k}/{fname}: malformed HTML document")
            site_texts.append(texts_k)

        # Verify F/N/Z cycle semantics
        ctypes_seen: list[str] = []
        changed_claim_cycle: dict[str, int] = {}
        for k_idx, cmeta in enumerate(cycles, start=1):
            if cmeta.get("cycle") != k_idx:
                errors.append(f"{sid}: cycles[{k_idx-1}].cycle={cmeta.get('cycle')!r} != {k_idx}")
            ctype = cmeta.get("type")
            ctypes_seen.append(ctype)
            ch_claims = cmeta.get("changed_claims")
            n_pages = cmeta.get("noise_pages")
            if not isinstance(ch_claims, list) or len(set(ch_claims)) != len(ch_claims):
                errors.append(f"{sid}/cycle_{k_idx}: invalid changed_claims {ch_claims!r}")
                continue
            if not isinstance(n_pages, list) or len(set(n_pages)) != len(n_pages):
                errors.append(f"{sid}/cycle_{k_idx}: invalid noise_pages {n_pages!r}")
                continue
            for cid in ch_claims:
                if cid not in claim_by_id:
                    errors.append(f"{sid}/cycle_{k_idx}: unknown changed claim {cid!r}")
                elif cid in changed_claim_cycle:
                    errors.append(f"{sid}/cycle_{k_idx}: claim {cid} changed more than once")
                else:
                    changed_claim_cycle[cid] = k_idx
            for np in n_pages:
                if np not in pages_set:
                    errors.append(f"{sid}/cycle_{k_idx}: noise_page {np!r} not in pages")

            changed_files = {
                f for f in all_site_files
                if page_sha256[k_idx].get(f) != page_sha256[k_idx - 1].get(f)
            }
            truth_diffs = {
                cid for cid in expected_cids
                if truth[k_idx].get(cid) != truth[k_idx - 1].get(cid)
            }

            if ctype == "Z":
                if ch_claims or n_pages:
                    errors.append(f"{sid}/cycle_{k_idx} (Z): changed_claims and noise_pages must be empty")
                if truth_diffs:
                    errors.append(f"{sid}/cycle_{k_idx} (Z): truth changed on {sorted(truth_diffs)}")
                if changed_files:
                    errors.append(f"{sid}/cycle_{k_idx} (Z): site not byte-identical; changed {sorted(changed_files)}")
            elif ctype == "N":
                if ch_claims:
                    errors.append(f"{sid}/cycle_{k_idx} (N): changed_claims must be empty")
                if not (1 <= len(n_pages) <= 2):
                    errors.append(f"{sid}/cycle_{k_idx} (N): expected 1-2 noise_pages, got {len(n_pages)}")
                if truth_diffs:
                    errors.append(f"{sid}/cycle_{k_idx} (N): truth changed on {sorted(truth_diffs)}")
                if changed_files != set(n_pages):
                    errors.append(
                        f"{sid}/cycle_{k_idx} (N): changed files {sorted(changed_files)} != noise_pages {sorted(n_pages)}"
                    )
            elif ctype == "F":
                if len(ch_claims) != 2:
                    errors.append(f"{sid}/cycle_{k_idx} (F): expected 2 changed_claims, got {len(ch_claims)}")
                if len(n_pages) != 1:
                    errors.append(f"{sid}/cycle_{k_idx} (F): expected 1 noise_page, got {len(n_pages)}")
                if truth_diffs != set(ch_claims):
                    errors.append(
                        f"{sid}/cycle_{k_idx} (F): truth_diffs {sorted(truth_diffs)} != changed_claims {sorted(ch_claims)}"
                    )
                expected_changed = set(n_pages)
                for cid in ch_claims:
                    if cid in claim_by_id:
                        expected_changed.update(claim_by_id[cid]["source_pages"])
                if changed_files != expected_changed:
                    errors.append(
                        f"{sid}/cycle_{k_idx} (F): changed files {sorted(changed_files)} != expected {sorted(expected_changed)}"
                    )
            else:
                errors.append(f"{sid}/cycle_{k_idx}: unknown cycle type {ctype!r}")

        if sorted(ctypes_seen) != ["F", "F", "N", "Z"]:
            errors.append(f"{sid}: cycle types {ctypes_seen} not a permutation of F,F,N,Z")

        # Verify claimed values appear verbatim on all source_pages at every cycle k,
        # appear as exact JSON string / CSV cell in JSON/CSV, never adjacent to placeholder,
        # and old values do NOT appear on any source_page after changing.
        for k in range(5):
            texts_k = site_texts[k]
            for c in claims:
                cid = c["id"]
                val = truth[k][cid]
                for sp in c["source_pages"]:
                    text = texts_k.get(sp, "")
                    if val not in text:
                        errors.append(f"{sid}/cycle_{k}/{sp}: value {val!r} for {cid} missing verbatim")
                    ext = Path(sp).suffix.lower()
                    if ext == ".json":
                        try:
                            leaves = [v for _, v in iter_json_string_leaves(json.loads(text))]
                            if val not in leaves:
                                errors.append(f"{sid}/cycle_{k}/{sp}: value {val!r} for {cid} not a JSON string value")
                        except Exception:
                            pass
                    elif ext == ".csv":
                        rows = list(csv.reader(io.StringIO(text)))
                        cells = [cell for row in rows[1:] for cell in row]
                        if val not in cells:
                            errors.append(f"{sid}/cycle_{k}/{sp}: value {val!r} for {cid} not a CSV cell")
                    # Placeholder adjacency check
                    for ph in VALID_PLACEHOLDERS:
                        if f"{val}{ph}" in text or f"{ph}{val}" in text:
                            errors.append(f"{sid}/cycle_{k}/{sp}: placeholder {ph} adjacent to {val!r} without separator")
                    # Disappearance check after change
                    chg_k = changed_claim_cycle.get(cid)
                    if chg_k is not None and k >= chg_k:
                        old_val = truth[chg_k - 1][cid]
                        if old_val in text:
                            errors.append(
                                f"{sid}/cycle_{k}/{sp}: old value {old_val!r} of {cid} still occurs after cycle {chg_k}"
                            )

        # Measure v3 metrics on cycle 0
        texts_0 = site_texts[0]
        ent_claims: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for c in claims:
            cid = c["id"]
            val = truth[0][cid]
            total_claims += 1
            ent_claims[c["entity"]].append(c)

            # (a) all source pages in json/csv/txt
            if all(Path(sp).suffix.lower() in STRUCTURED_EXTS for sp in c["source_pages"]):
                a_structured_only += 1

            # (b) exact value also appears on the SAME page for a different item/attribute
            if any(
                count_value_occurrences_for_different_items(sp, texts_0.get(sp, ""), val) >= 2
                for sp in c["source_pages"]
            ):
                b_same_val_dup += 1

            # (d) placeholder on same line / JSON object line / CSV row as value
            if any(
                has_placeholder_same_line_or_row(sp, texts_0.get(sp, ""), val)
                for sp in c["source_pages"]
            ):
                d_same_line_ph += 1

        # (c) multi-claim entities with split pages
        for ent, ecl in ent_claims.items():
            if len(ecl) >= 2:
                c_multi_entities += 1
                unique_page_sets = {tuple(sorted(c["source_pages"])) for c in ecl}
                union_pages = {sp for c in ecl for sp in c["source_pages"]}
                if len(union_pages) >= 2 and len(unique_page_sets) >= 2:
                    c_split_entities += 1

    if not (saw_json_pretty and saw_json_compact):
        errors.append(
            f"JSON variety check failed: saw_json_pretty={saw_json_pretty}, saw_json_compact={saw_json_compact}"
        )

    share_a = a_structured_only / total_claims if total_claims else 0.0
    share_b = b_same_val_dup / total_claims if total_claims else 0.0
    share_c = c_split_entities / c_multi_entities if c_multi_entities else 0.0
    share_d = d_same_line_ph / total_claims if total_claims else 0.0

    print("Measured v3 shares:")
    print(f"  (a) all sources in json/csv/txt:              {a_structured_only}/{total_claims} ({share_a:.4f}) [min 0.45]")
    print(f"  (b) same value on same page (diff item/attr): {b_same_val_dup}/{total_claims} ({share_b:.4f}) [min 0.35]")
    print(f"  (c) multi-claim entities with split pages:    {c_split_entities}/{c_multi_entities} ({share_c:.4f}) [min 0.25]")
    print(f"  (d) placeholder on same line/row/object-line: {d_same_line_ph}/{total_claims} ({share_d:.4f}) [min 0.30]")

    if share_a < 0.45:
        errors.append(f"Metric (a) below threshold: {share_a:.4f} < 0.45")
    if share_b < 0.35:
        errors.append(f"Metric (b) below threshold: {share_b:.4f} < 0.35")
    if c_multi_entities == 0 or share_c < 0.25:
        errors.append(f"Metric (c) below threshold: {share_c:.4f} < 0.25 (multi_entities={c_multi_entities})")
    if share_d < 0.30:
        errors.append(f"Metric (d) below threshold: {share_d:.4f} < 0.30")

    if errors:
        print(f"\nFAIL: {len(errors)} violation(s) found:", file=sys.stderr)
        for err in errors[:50]:
            print(f"  - {err}", file=sys.stderr)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more", file=sys.stderr)
        return 1

    print(f"\nPASS: {n_sets} set(s), {len(domains_seen)} domain(s) verified with 0 violations.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a heldout-v3 generated dataset.")
    parser.add_argument("dir", type=Path, help="Dataset root directory.")
    args = parser.parse_args(argv)
    return check_dataset(args.dir)


if __name__ == "__main__":
    raise SystemExit(main())
