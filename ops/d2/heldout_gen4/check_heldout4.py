#!/usr/bin/env python3
"""Independent validator and metrics checker for heldout-v4 datasets.

CLI: python3 check_heldout4.py <dir>
Exits non-zero on any schema, layout, semantic, or threshold violation.
Prints measured shares for requirements (3), (4), (5), (6), (7).

Python 3.12 stdlib only.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

EXPECTED_SCHEMA = "vacant.d2.manifest/1"
EXPECTED_GENERATOR = "heldout-v4"
VALID_CONTENT_EXTS = {".json", ".csv", ".tsv", ".yaml", ".xml", ".txt", ".md", ".html"}
SPECIAL_EXTS = {".yaml", ".xml", ".tsv"}
VALID_PLACEHOLDERS = {"{{FETCH_TS}}", "{{FETCH_COUNT}}", "{{FETCH_ID}}"}
PLACEHOLDER_RE = re.compile(r"\{\{[^{}]*\}\}")
TEMPLATE_CLAIM_RE = re.compile(r"^- (.+) \u2014 (.+): ____$")
VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+$")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
PAGINATED_RE = re.compile(r"^(.+)-page-([12])(\.[a-z0-9]+)$")


def norm_key(k: str) -> str:
    return re.sub(r"[\s_]+", " ", k.strip().lower())


def is_valid_value(val: str) -> bool:
    if not isinstance(val, str) or not val.strip():
        return False
    if VERSION_RE.match(val):
        return True
    nums = NUMBER_RE.findall(val)
    return len(nums) == 1


# ---------------------------------------------------------------------------
# Link extractor for top index & section index pages (.html / .md)
# ---------------------------------------------------------------------------

class _HrefParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            for k, v in attrs:
                if k.lower() == "href" and v is not None:
                    self.hrefs.append(v.strip())


def extract_links(path: Path, text: str) -> list[str]:
    if path.suffix == ".html":
        p = _HrefParser()
        p.feed(text)
        return p.hrefs
    if path.suffix == ".md":
        return [m.group(1).strip() for m in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text)]
    return []


# ---------------------------------------------------------------------------
# Multi-format content page parsers (Python 3.12 stdlib only)
# ---------------------------------------------------------------------------

@dataclass
class ParsedPage:
    records: list[dict[str, str]]       # ordered list of {normalized_key: raw_value}
    record_has_ph: list[bool]           # whether same record/row/line carries a placeholder
    has_history: bool
    history_text: str
    raw_text: str


class _HtmlContentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_current = False
        self.in_history = False
        self.section_depth = 0
        self.in_thead = False
        self.in_tbody = False
        self.in_tr = False
        self.in_cell = False
        self.cell_buf: list[str] = []
        self.headers: list[str] = []
        self.rows: list[list[str]] = []
        self.cur_row: list[str] = []
        self.history_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        if t == "section":
            sid = attr_map.get("id", "").lower()
            if sid == "current":
                self.in_current = True
            elif sid == "history":
                self.in_history = True
        elif t == "thead" and self.in_current:
            self.in_thead = True
        elif t == "tbody" and self.in_current:
            self.in_tbody = True
        elif t == "tr" and (self.in_thead or self.in_tbody):
            self.in_tr = True
            self.cur_row = []
        elif t in ("th", "td") and self.in_tr:
            self.in_cell = True
            self.cell_buf = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t == "section":
            self.in_current = False
            self.in_history = False
        elif t == "thead":
            self.in_thead = False
        elif t == "tbody":
            self.in_tbody = False
        elif t == "tr" and self.in_tr:
            self.in_tr = False
            if self.in_thead:
                self.headers = self.cur_row
            elif self.in_tbody:
                self.rows.append(self.cur_row)
        elif t in ("th", "td") and self.in_cell:
            self.in_cell = False
            self.cur_row.append("".join(self.cell_buf).strip())

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell_buf.append(data)
        if self.in_history:
            self.history_chunks.append(data)


def _unquote_yaml_scalar(raw: str) -> str:
    s = raw.strip()
    if s.startswith('"'):
        # Parse double-quoted string up to closing unescaped quote (ignore trailing # comment)
        out: list[str] = []
        i = 1
        while i < len(s):
            ch = s[i]
            if ch == "\\" and i + 1 < len(s):
                out.append(s[i + 1])
                i += 2
            elif ch == '"':
                break
            else:
                out.append(ch)
                i += 1
        return "".join(out)
    # Strip trailing comment if unquoted
    if " #" in s:
        s = s.split(" #", 1)[0].strip()
    return s


def parse_yaml_page(text: str) -> ParsedPage:
    lines = text.splitlines()
    mode: str | None = None
    records: list[dict[str, str]] = []
    record_has_ph: list[bool] = []
    history_lines: list[str] = []
    has_history = False
    cur_rec: dict[str, str] | None = None
    cur_ph = False

    def flush_rec() -> None:
        nonlocal cur_rec, cur_ph
        if cur_rec is not None:
            records.append(cur_rec)
            record_has_ph.append(cur_ph)
            cur_rec = None
            cur_ph = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if not line.startswith(" ") and stripped.endswith(":"):
            flush_rec()
            section = stripped[:-1]
            if section == "records":
                mode = "records"
            elif section == "history":
                mode = "history"
                has_history = True
            else:
                mode = None
            continue
        if mode == "records":
            if line.startswith("  - "):
                flush_rec()
                cur_rec = {}
                cur_ph = any(ph in line for ph in VALID_PLACEHOLDERS)
                kv = line[4:]
                k, _, v = kv.partition(":")
                cur_rec[norm_key(k)] = _unquote_yaml_scalar(v)
            elif line.startswith("    ") and cur_rec is not None:
                if any(ph in line for ph in VALID_PLACEHOLDERS):
                    cur_ph = True
                k, _, v = line.strip().partition(":")
                cur_rec[norm_key(k)] = _unquote_yaml_scalar(v)
        elif mode == "history":
            history_lines.append(line)

    flush_rec()
    return ParsedPage(
        records=records,
        record_has_ph=record_has_ph,
        has_history=has_history,
        history_text="\n".join(history_lines),
        raw_text=text,
    )


def parse_json_page(text: str) -> ParsedPage:
    data = json.loads(text)
    raw_recs = data.get("records", [])
    records: list[dict[str, str]] = []
    record_has_ph: list[bool] = []
    for item in raw_recs:
        normed = {norm_key(k): str(v) for k, v in item.items()}
        has_ph = any(any(ph in str(v) for ph in VALID_PLACEHOLDERS) for v in item.values())
        records.append(normed)
        record_has_ph.append(has_ph)
    has_history = "history" in data and isinstance(data["history"], list)
    hist_text = json.dumps(data.get("history", []), ensure_ascii=False) if has_history else ""
    return ParsedPage(
        records=records,
        record_has_ph=record_has_ph,
        has_history=has_history,
        history_text=hist_text,
        raw_text=text,
    )


def parse_xml_page(text: str) -> ParsedPage:
    root = ET.fromstring(text)
    records: list[dict[str, str]] = []
    record_has_ph: list[bool] = []
    recs_el = root.find("records")
    if recs_el is not None:
        for rec_el in recs_el.findall("record"):
            rec: dict[str, str] = {}
            has_ph = any(any(ph in v for ph in VALID_PLACEHOLDERS) for v in rec_el.attrib.values())
            for child in rec_el:
                val = (child.text or "").strip()
                rec[norm_key(child.tag)] = val
                if any(ph in val for ph in VALID_PLACEHOLDERS):
                    has_ph = True
            records.append(rec)
            record_has_ph.append(has_ph)
    hist_el = root.find("history")
    has_history = hist_el is not None
    hist_text = ET.tostring(hist_el, encoding="unicode") if hist_el is not None else ""
    return ParsedPage(
        records=records,
        record_has_ph=record_has_ph,
        has_history=has_history,
        history_text=hist_text,
        raw_text=text,
    )


def parse_delimited_page(text: str, delimiter: str) -> ParsedPage:
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    records: list[dict[str, str]] = []
    record_has_ph: list[bool] = []
    for row in reader:
        normed = {norm_key(k): (v or "").strip() for k, v in row.items() if k is not None}
        has_ph = any(any(ph in v for ph in VALID_PLACEHOLDERS) for v in normed.values())
        records.append(normed)
        record_has_ph.append(has_ph)
    return ParsedPage(
        records=records,
        record_has_ph=record_has_ph,
        has_history=False,
        history_text="",
        raw_text=text,
    )


def parse_txt_page(text: str) -> ParsedPage:
    lines = text.splitlines()
    records: list[dict[str, str]] = []
    record_has_ph: list[bool] = []
    has_history = False
    history_lines: list[str] = []

    header_idx: int | None = None
    for i, line in enumerate(lines):
        if line.startswith("ENTITY") and i + 1 < len(lines) and set(lines[i + 1].strip()) == {"-"}:
            header_idx = i
            break

    if header_idx is not None:
        headers = [norm_key(h) for h in re.split(r" {2,}", lines[header_idx].strip())]
        i = header_idx + 2
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                break
            cells = [c.strip() for c in re.split(r" {2,}", line.strip())]
            if len(cells) == len(headers):
                rec = dict(zip(headers, cells))
                has_ph = any(ph in line for ph in VALID_PLACEHOLDERS)
                records.append(rec)
                record_has_ph.append(has_ph)
            i += 1
        # Check for REVISION HISTORY section
        while i < len(lines):
            if lines[i].strip().upper() == "REVISION HISTORY":
                has_history = True
                history_lines = lines[i + 2 :]
                break
            i += 1

    return ParsedPage(
        records=records,
        record_has_ph=record_has_ph,
        has_history=has_history,
        history_text="\n".join(history_lines),
        raw_text=text,
    )


def parse_md_page(text: str) -> ParsedPage:
    lines = text.splitlines()
    records: list[dict[str, str]] = []
    record_has_ph: list[bool] = []
    has_history = False
    history_lines: list[str] = []

    mode = "top"
    headers: list[str] | None = None
    for line in lines:
        s = line.strip()
        if s.lower().startswith("## current"):
            mode = "current"
            continue
        if s.lower().startswith("## revision history"):
            mode = "history"
            has_history = True
            continue
        if mode == "current" and s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if headers is None:
                headers = [norm_key(c) for c in cells]
            elif all(set(c) <= {"-", ":"} for c in cells):
                continue
            else:
                rec = dict(zip(headers, cells))
                has_ph = any(ph in line for ph in VALID_PLACEHOLDERS)
                records.append(rec)
                record_has_ph.append(has_ph)
        elif mode == "history":
            history_lines.append(line)

    return ParsedPage(
        records=records,
        record_has_ph=record_has_ph,
        has_history=has_history,
        history_text="\n".join(history_lines),
        raw_text=text,
    )


def parse_html_page(text: str) -> ParsedPage:
    parser = _HtmlContentParser()
    parser.feed(text)
    headers = [norm_key(h) for h in parser.headers]
    records: list[dict[str, str]] = []
    record_has_ph: list[bool] = []
    for row in parser.rows:
        if len(row) == len(headers):
            rec = dict(zip(headers, row))
            has_ph = any(any(ph in c for ph in VALID_PLACEHOLDERS) for c in row)
            records.append(rec)
            record_has_ph.append(has_ph)
    has_history = 'id="history"' in text
    return ParsedPage(
        records=records,
        record_has_ph=record_has_ph,
        has_history=has_history,
        history_text=" ".join(parser.history_chunks),
        raw_text=text,
    )


def parse_content_page(path: Path, text: str) -> ParsedPage:
    ext = path.suffix.lower()
    if ext == ".json":
        return parse_json_page(text)
    if ext == ".yaml":
        return parse_yaml_page(text)
    if ext == ".xml":
        return parse_xml_page(text)
    if ext == ".csv":
        return parse_delimited_page(text, ",")
    if ext == ".tsv":
        return parse_delimited_page(text, "\t")
    if ext == ".txt":
        return parse_txt_page(text)
    if ext == ".md":
        return parse_md_page(text)
    if ext == ".html":
        return parse_html_page(text)
    raise ValueError(f"Unsupported content extension: {ext}")


# ---------------------------------------------------------------------------
# Main validation logic
# ---------------------------------------------------------------------------

def check_dataset(root: Path) -> int:
    errors: list[str] = []

    def fail(msg: str) -> None:
        errors.append(msg)

    if not root.is_dir():
        print(f"FAIL: dataset directory does not exist: {root}", file=sys.stderr)
        return 1

    manifest_path = root / "manifest.json"
    sha_path = root / "manifest.sha256"
    if not manifest_path.is_file():
        print(f"FAIL: missing {manifest_path}", file=sys.stderr)
        return 1
    if not sha_path.is_file():
        print(f"FAIL: missing {sha_path}", file=sys.stderr)
        return 1

    manifest_bytes = manifest_path.read_bytes()
    actual_sha = hashlib.sha256(manifest_bytes).hexdigest()
    sha_text = sha_path.read_text(encoding="utf-8")
    if sha_text != f"{actual_sha}\n":
        fail(f"manifest.sha256 mismatch: expected '{actual_sha}\\n', got {sha_text!r}")

    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except Exception as exc:
        print(f"FAIL: invalid manifest.json: {exc}", file=sys.stderr)
        return 1

    # Top-level manifest schema
    if manifest.get("schema") != EXPECTED_SCHEMA:
        fail(f"schema mismatch: {manifest.get('schema')!r}")
    if manifest.get("generator") != EXPECTED_GENERATOR:
        fail(f"generator mismatch: {manifest.get('generator')!r}")
    if not isinstance(manifest.get("seed"), int):
        fail("manifest.seed must be int")
    n_sets = manifest.get("n_sets")
    if not isinstance(n_sets, int) or n_sets < 1:
        fail(f"manifest.n_sets invalid: {n_sets!r}")
    if manifest.get("cycle_types") != ["F", "F", "N", "Z"]:
        fail(f"manifest.cycle_types must be ['F','F','N','Z'], got {manifest.get('cycle_types')!r}")

    sets_list = manifest.get("sets")
    if not isinstance(sets_list, list) or len(sets_list) != n_sets:
        fail(f"manifest.sets length mismatch: expected {n_sets}, got {type(sets_list)}")
        sets_list = []

    # Global measurement accumulators
    total_claims = 0
    claims_on_history_pages_c0 = 0
    claims_with_row_placeholder_c0 = 0
    claims_with_shared_value_c0 = 0

    total_changed_claims = 0
    changed_old_val_in_history = 0
    changed_old_val_on_source_page = 0
    changed_old_val_in_same_record = 0

    total_content_pages = 0
    reordered_content_pages = 0
    total_all_files = 0
    total_n_cycles = 0
    n_cycles_with_reorder = 0
    total_f_cycles = 0
    f_cycles_with_reorder = 0

    sets_with_pagination_move = 0
    total_pagination_moves = 0

    for idx_s, sdata in enumerate(sets_list):
        expected_sid = f"s{idx_s + 1:02d}"
        sid = sdata.get("set")
        if sid != expected_sid:
            fail(f"set[{idx_s}]: expected id {expected_sid}, got {sid!r}")
        if not isinstance(sdata.get("domain"), str) or not sdata["domain"]:
            fail(f"{sid}: missing domain")

        set_dir = root / "sets" / str(sid)
        if not set_dir.is_dir():
            fail(f"{sid}: missing directory {set_dir}")
            continue

        top_index = sdata.get("index")
        pages_list = sdata.get("pages")
        if not isinstance(top_index, str) or not isinstance(pages_list, list):
            fail(f"{sid}: invalid index/pages fields")
            continue
        if top_index in pages_list:
            fail(f"{sid}: index file {top_index!r} must not also appear in pages")
        if len(set(pages_list)) != len(pages_list):
            fail(f"{sid}: duplicate filenames in pages")
        expected_files = {top_index} | set(pages_list)

        # Validate template.md and claims
        claims_list = sdata.get("claims")
        if not isinstance(claims_list, list) or len(claims_list) != 20:
            fail(f"{sid}: must have exactly 20 claims")
            continue

        tpl_path = set_dir / "template.md"
        if not tpl_path.is_file():
            fail(f"{sid}: missing template.md")
        else:
            tpl_lines = tpl_path.read_text(encoding="utf-8").splitlines()
            non_empty = [ln for ln in tpl_lines if ln.strip()]
            if len(non_empty) < 22 or not non_empty[0].startswith("# "):
                fail(f"{sid}: template.md missing title/instruction/claim lines")
            found_tpl_claims: list[tuple[str, str, str]] = []
            for ln in tpl_lines[2:]:
                s_ln = ln.strip()
                if not s_ln or s_ln.startswith("## "):
                    continue
                m = TEMPLATE_CLAIM_RE.match(ln)
                if not m:
                    fail(f"{sid}: invalid template line: {ln!r}")
                else:
                    found_tpl_claims.append((m.group(1), m.group(2), f"- {m.group(1)} \u2014 {m.group(2)}: "))
            if len(found_tpl_claims) != 20:
                fail(f"{sid}: template.md expected 20 claim lines, found {len(found_tpl_claims)}")
            prefixes = [t[2] for t in found_tpl_claims]
            if len(set(prefixes)) != len(prefixes):
                fail(f"{sid}: duplicate template_line prefixes in template.md")
            manifest_prefixes = [c.get("template_line") for c in claims_list]
            if set(prefixes) != set(manifest_prefixes):
                fail(f"{sid}: template.md claim lines do not match manifest claims")

        # Validate claim objects & entity digit ratio
        claim_by_id: dict[str, dict[str, Any]] = {}
        numbered_claim_count = 0
        unique_entities: set[str] = set()
        for ci, c in enumerate(claims_list):
            expected_cid = f"c{ci + 1:02d}"
            if c.get("id") != expected_cid:
                fail(f"{sid}: claim[{ci}] expected id {expected_cid}, got {c.get('id')!r}")
            ent = c.get("entity", "")
            lbl = c.get("label", "")
            tline = c.get("template_line", "")
            if tline != f"- {ent} \u2014 {lbl}: ":
                fail(f"{sid}/{expected_cid}: template_line mismatch: {tline!r}")
            if any(ch.isdigit() for ch in ent):
                numbered_claim_count += 1
            unique_entities.add(ent)
            claim_by_id[expected_cid] = c

        num_ent_ratio = numbered_claim_count / 20.0
        uniq_num_ratio = sum(1 for e in unique_entities if any(ch.isdigit() for ch in e)) / len(unique_entities)
        if num_ent_ratio < 0.30 or uniq_num_ratio < 0.30:
            fail(f"{sid}: <30% entity names contain a number (claims={num_ent_ratio:.2f}, unique={uniq_num_ratio:.2f})")
        if numbered_claim_count == 20:
            fail(f"{sid}: all entity names contain a number; rest must be words only")

        # Validate manifest arrays lengths
        truth_arr = sdata.get("truth")
        spbc_arr = sdata.get("source_pages_by_cycle")
        cycles_arr = sdata.get("cycles")
        sha_arr = sdata.get("page_sha256")
        if not (
            isinstance(truth_arr, list) and len(truth_arr) == 5
            and isinstance(spbc_arr, list) and len(spbc_arr) == 5
            and isinstance(cycles_arr, list) and len(cycles_arr) == 4
            and isinstance(sha_arr, list) and len(sha_arr) == 5
        ):
            fail(f"{sid}: invalid lengths for truth/source_pages_by_cycle/cycles/page_sha256")
            continue

        # Check source_pages == source_pages_by_cycle[0]
        for cid, c in claim_by_id.items():
            if c.get("source_pages") != spbc_arr[0].get(cid):
                fail(f"{sid}/{cid}: claim.source_pages != source_pages_by_cycle[0]")

        # Validate each cycle's site files, sha256, placeholders, navigation, and parse content pages
        parsed_by_cycle: list[dict[str, ParsedPage]] = []
        raw_by_cycle: list[dict[str, str]] = []
        content_pages_set: set[str] | None = None
        section_pages_set: set[str] | None = None

        for k in range(5):
            site_dir = set_dir / f"cycle_{k}" / "site"
            if not site_dir.is_dir():
                fail(f"{sid}/cycle_{k}: missing site directory")
                parsed_by_cycle.append({})
                raw_by_cycle.append({})
                continue

            entries = list(site_dir.iterdir())
            subdirs = [e.name for e in entries if e.is_dir()]
            if subdirs:
                fail(f"{sid}/cycle_{k}: subdirectories not allowed in site/: {subdirs}")
            disk_files = {e.name for e in entries if e.is_file()}
            if disk_files != expected_files:
                fail(f"{sid}/cycle_{k}: disk files mismatch manifest (extra={disk_files - expected_files}, missing={expected_files - disk_files})")

            if set(sha_arr[k].keys()) != expected_files:
                fail(f"{sid}/cycle_{k}: page_sha256 keys mismatch expected files")

            cycle_raw: dict[str, str] = {}
            for fname in sorted(disk_files):
                fpath = site_dir / fname
                b = fpath.read_bytes()
                h = hashlib.sha256(b).hexdigest()
                if sha_arr[k].get(fname) != h:
                    fail(f"{sid}/cycle_{k}/{fname}: sha256 mismatch")
                txt = b.decode("utf-8")
                cycle_raw[fname] = txt

                # Placeholder checks on EVERY page
                for req_ph in VALID_PLACEHOLDERS:
                    if req_ph not in txt:
                        fail(f"{sid}/cycle_{k}/{fname}: missing placeholder {req_ph}")
                tokens = PLACEHOLDER_RE.findall(txt)
                bad_tokens = [t for t in tokens if t not in VALID_PLACEHOLDERS]
                if bad_tokens:
                    fail(f"{sid}/cycle_{k}/{fname}: malformed placeholder tokens: {bad_tokens}")
                stripped_valid = PLACEHOLDER_RE.sub("", txt)
                if "{{" in stripped_valid or "}}" in stripped_valid:
                    fail(f"{sid}/cycle_{k}/{fname}: stray unmatched '{{{{' or '}}}}'")

                # Check placeholders never touch alnum without separator
                for m in PLACEHOLDER_RE.finditer(txt):
                    if m.start() > 0 and txt[m.start() - 1].isalnum():
                        fail(f"{sid}/cycle_{k}/{fname}: placeholder touches preceding alphanumeric char")
                    if m.end() < len(txt) and txt[m.end()].isalnum():
                        fail(f"{sid}/cycle_{k}/{fname}: placeholder touches following alphanumeric char")

            raw_by_cycle.append(cycle_raw)

            # Navigation reachability check (two-level)
            if Path(top_index).suffix not in (".html", ".md"):
                fail(f"{sid}/cycle_{k}: top index must be .html or .md, got {top_index}")
            top_links = extract_links(site_dir / top_index, cycle_raw[top_index])
            top_link_set = set(top_links)
            if not (2 <= len(top_link_set) <= 3):
                fail(f"{sid}/cycle_{k}: top index must link to 2-3 section pages, got {len(top_link_set)}: {top_links}")
            if not top_link_set.issubset(set(pages_list)):
                fail(f"{sid}/cycle_{k}: top index links to unknown pages: {top_link_set - set(pages_list)}")

            sec_set = top_link_set
            cont_set = set(pages_list) - sec_set
            if content_pages_set is None:
                content_pages_set = cont_set
                section_pages_set = sec_set
            elif cont_set != content_pages_set or sec_set != section_pages_set:
                fail(f"{sid}/cycle_{k}: navigation structure changed across cycles")

            if not (6 <= len(cont_set) <= 9):
                fail(f"{sid}/cycle_{k}: expected 6-9 content pages, got {len(cont_set)}")

            reachable_content: set[str] = set()
            for sf in sorted(sec_set):
                if Path(sf).suffix not in (".html", ".md"):
                    fail(f"{sid}/cycle_{k}: section index {sf} must be .html or .md")
                slinks = set(extract_links(site_dir / sf, cycle_raw[sf]))
                if not slinks:
                    fail(f"{sid}/cycle_{k}: section index {sf} has no outgoing links")
                if slinks & sec_set:
                    fail(f"{sid}/cycle_{k}: section index {sf} links to section index")
                invalid_slinks = slinks - cont_set - {top_index}
                if invalid_slinks:
                    fail(f"{sid}/cycle_{k}: section index {sf} links to unknown files: {invalid_slinks}")
                reachable_content |= (slinks & cont_set)

            if reachable_content != cont_set:
                fail(f"{sid}/cycle_{k}: unreachable content pages: {cont_set - reachable_content}")

            # Parse every content page
            parsed_k: dict[str, ParsedPage] = {}
            for cf in sorted(cont_set):
                ext = Path(cf).suffix.lower()
                if ext not in VALID_CONTENT_EXTS:
                    fail(f"{sid}/cycle_{k}/{cf}: unsupported content format {ext}")
                    continue
                try:
                    parsed_k[cf] = parse_content_page(site_dir / cf, cycle_raw[cf])
                except Exception as exc:
                    fail(f"{sid}/cycle_{k}/{cf}: failed to parse: {exc}")
            parsed_by_cycle.append(parsed_k)

            # Verify truth values & current-value presence on every source_pages_by_cycle[k]
            truth_k = truth_arr[k]
            spbc_k = spbc_arr[k]
            if set(truth_k.keys()) != set(claim_by_id.keys()):
                fail(f"{sid}/cycle_{k}: truth keys mismatch claims")
                continue
            for cid, c in claim_by_id.items():
                val = truth_k[cid]
                if not is_valid_value(val):
                    fail(f"{sid}/cycle_{k}/{cid}: invalid value string {val!r}")
                spages = spbc_k.get(cid, [])
                if not isinstance(spages, list) or not spages:
                    fail(f"{sid}/cycle_{k}/{cid}: empty source_pages_by_cycle")
                    continue
                ent = c["entity"]
                n_lbl = norm_key(c["label"])
                for sp in spages:
                    if sp not in parsed_k:
                        fail(f"{sid}/cycle_{k}/{cid}: source page {sp} not a parsed content page")
                        continue
                    pp = parsed_k[sp]
                    # Check placeholder does not touch value without separator
                    if f"{val}{{{{" in pp.raw_text or f"}}}}{val}" in pp.raw_text:
                        fail(f"{sid}/cycle_{k}/{cid}/{sp}: placeholder directly touches value")
                    matching_recs = [r for r in pp.records if r.get("entity") == ent]
                    if not matching_recs:
                        fail(f"{sid}/cycle_{k}/{cid}/{sp}: entity {ent!r} not found in current records")
                        continue
                    if not any(r.get(n_lbl) == val for r in matching_recs):
                        fail(
                            f"{sid}/cycle_{k}/{cid}/{sp}: current value {val!r} not verbatim in field "
                            f"{n_lbl!r} for entity {ent!r} (got {[r.get(n_lbl) for r in matching_recs]})"
                        )

        assert content_pages_set is not None
        total_content_pages += len(content_pages_set)
        total_all_files += len(expected_files)

        # Format diversity check per set
        content_exts = {Path(cf).suffix.lower() for cf in content_pages_set}
        if len(content_exts) < 5:
            fail(f"{sid}: expected >=5 distinct content formats, got {len(content_exts)}: {sorted(content_exts)}")
        if len(content_exts & SPECIAL_EXTS) < 2:
            fail(f"{sid}: expected >=2 of {{yaml, xml, tsv}}, got {sorted(content_exts & SPECIAL_EXTS)}")

        # Pagination pair existence check per set
        pag_groups: dict[tuple[str, str], set[str]] = {}
        for cf in content_pages_set:
            m = PAGINATED_RE.match(cf)
            if m:
                pag_groups.setdefault((m.group(1), m.group(3)), set()).add(m.group(2))
        valid_pag_pairs = [k for k, nums in pag_groups.items() if nums == {"1", "2"}]
        if not valid_pag_pairs:
            fail(f"{sid}: no paginated pair ('...-page-1.<ext>', '...-page-2.<ext>') found")

        # Cycle-0 claim property measurements (Req 3 >=40% history pages, Req 4 row placeholders, Req 5 >=20% shared)
        set_hist_claims_c0 = 0
        set_shared_claims_c0 = 0
        for cid, c in claim_by_id.items():
            total_claims += 1
            spages0 = spbc_arr[0][cid]
            ent = c["entity"]
            n_lbl = norm_key(c["label"])
            val0 = truth_arr[0][cid]

            on_hist = any(parsed_by_cycle[0][sp].has_history for sp in spages0 if sp in parsed_by_cycle[0])
            if on_hist:
                set_hist_claims_c0 += 1
                claims_on_history_pages_c0 += 1

            has_row_ph = False
            has_shared = False
            for sp in spages0:
                pp = parsed_by_cycle[0].get(sp)
                if pp is None:
                    continue
                for r_idx, rec in enumerate(pp.records):
                    if rec.get("entity") == ent and rec.get(n_lbl) == val0:
                        if pp.record_has_ph[r_idx]:
                            has_row_ph = True
                        # Check if ANOTHER field in the SAME record has identical value string
                        for fk, fv in rec.items():
                            if fk not in ("entity", n_lbl) and fv == val0:
                                has_shared = True
            if has_row_ph:
                claims_with_row_placeholder_c0 += 1
            if has_shared:
                set_shared_claims_c0 += 1
                claims_with_shared_value_c0 += 1

        if set_hist_claims_c0 / 20.0 < 0.40:
            fail(f"{sid}: <40% of claims on history-enabled pages ({set_hist_claims_c0}/20)")
        if set_shared_claims_c0 / 20.0 < 0.20:
            fail(f"{sid}: <20% of claims have shared value in same record at cycle 0 ({set_shared_claims_c0}/20)")

        # Validate cycle evolution (cycles 1..4)
        ctypes_seen: list[str] = []
        ever_changed_claims: set[str] = set()
        reordered_pages_in_set: set[str] = set()
        set_had_pag_move = False

        for c_idx, cmeta in enumerate(cycles_arr):
            k = c_idx + 1
            if cmeta.get("cycle") != k:
                fail(f"{sid}: cycle[{c_idx}].cycle expected {k}, got {cmeta.get('cycle')!r}")
            ctype = cmeta.get("type")
            ctypes_seen.append(str(ctype))
            ch_claims = cmeta.get("changed_claims", [])
            noise_pages = cmeta.get("noise_pages", [])

            changed_files = {
                fn for fn in expected_files
                if sha_arr[k].get(fn) != sha_arr[k - 1].get(fn)
            }
            actual_changed_claims = sorted(
                cid for cid in claim_by_id if truth_arr[k][cid] != truth_arr[k - 1][cid]
            )

            # Detect reordered pages in cycle k
            cycle_reordered = False
            for cf in sorted(content_pages_set):
                p_prev = parsed_by_cycle[k - 1].get(cf)
                p_curr = parsed_by_cycle[k].get(cf)
                if p_prev is None or p_curr is None:
                    continue
                ents_prev = [r.get("entity", "") for r in p_prev.records]
                ents_curr = [r.get("entity", "") for r in p_curr.records]
                common = set(ents_prev) & set(ents_curr)
                if len(common) >= 2:
                    f_prev = [e for e in ents_prev if e in common]
                    f_curr = [e for e in ents_curr if e in common]
                    if f_prev != f_curr:
                        reordered_pages_in_set.add(cf)
                        cycle_reordered = True

            # Detect pagination moves in cycle k
            for cid, c in claim_by_id.items():
                prev_sp = set(spbc_arr[k - 1][cid])
                curr_sp = set(spbc_arr[k][cid])
                if prev_sp != curr_sp:
                    for prefix, ext in valid_pag_pairs:
                        p1 = f"{prefix}-page-1{ext}"
                        p2 = f"{prefix}-page-2{ext}"
                        if (p1 in prev_sp and p2 in curr_sp) or (p2 in prev_sp and p1 in curr_sp):
                            old_p = p1 if p1 in prev_sp else p2
                            new_p = p2 if p1 in prev_sp else p1
                            # Verify row truly disappeared from old_p and appeared on new_p
                            ent = c["entity"]
                            still_on_old = any(r.get("entity") == ent for r in parsed_by_cycle[k][old_p].records)
                            now_on_new = any(r.get("entity") == ent for r in parsed_by_cycle[k][new_p].records)
                            if still_on_old or not now_on_new:
                                fail(f"{sid}/cycle_{k}/{cid}: invalid pagination move {old_p} -> {new_p}")
                            set_had_pag_move = True
                            total_pagination_moves += 1

            if ctype == "Z":
                if ch_claims or noise_pages:
                    fail(f"{sid}/cycle_{k} (Z): changed_claims and noise_pages must be empty")
                if actual_changed_claims:
                    fail(f"{sid}/cycle_{k} (Z): truth changed for {actual_changed_claims}")
                if changed_files:
                    fail(f"{sid}/cycle_{k} (Z): site is not byte-identical; changed={sorted(changed_files)}")
                if spbc_arr[k] != spbc_arr[k - 1]:
                    fail(f"{sid}/cycle_{k} (Z): source_pages_by_cycle changed")

            elif ctype == "N":
                total_n_cycles += 1
                if cycle_reordered:
                    n_cycles_with_reorder += 1
                if ch_claims or actual_changed_claims:
                    fail(f"{sid}/cycle_{k} (N): claims must not change")
                if not (1 <= len(noise_pages) <= 2):
                    fail(f"{sid}/cycle_{k} (N): expected 1-2 noise_pages, got {noise_pages}")
                if changed_files != set(noise_pages):
                    fail(f"{sid}/cycle_{k} (N): changed files {sorted(changed_files)} != noise_pages {sorted(noise_pages)}")

            elif ctype == "F":
                total_f_cycles += 1
                if cycle_reordered:
                    f_cycles_with_reorder += 1
                if len(ch_claims) != 2 or sorted(ch_claims) != actual_changed_claims:
                    fail(f"{sid}/cycle_{k} (F): expected 2 changed_claims matching truth diff (meta={ch_claims}, actual={actual_changed_claims})")
                for cid in ch_claims:
                    if cid in ever_changed_claims:
                        fail(f"{sid}/cycle_{k} (F): claim {cid} changed more than once")
                    ever_changed_claims.add(cid)

                claim_pages: set[str] = set()
                for cid in ch_claims:
                    claim_pages |= set(spbc_arr[k - 1][cid]) | set(spbc_arr[k][cid])

                if len(noise_pages) != 1:
                    fail(f"{sid}/cycle_{k} (F): expected 1 noise_page, got {noise_pages}")
                elif noise_pages[0] in claim_pages:
                    fail(f"{sid}/cycle_{k} (F): noise_page {noise_pages[0]} overlaps changed claim pages")
                expected_changed = claim_pages | set(noise_pages)
                if changed_files != expected_changed:
                    fail(f"{sid}/cycle_{k} (F): changed files {sorted(changed_files)} != expected {sorted(expected_changed)}")

                # Measure (3) old value still on source page (and in history) + (5) old value still in same record
                for cid in ch_claims:
                    total_changed_claims += 1
                    old_val = truth_arr[k - 1][cid]
                    new_val = truth_arr[k][cid]
                    if old_val == new_val:
                        fail(f"{sid}/cycle_{k}/{cid}: new value equals old value {old_val!r}")
                    ent = claim_by_id[cid]["entity"]
                    n_lbl = norm_key(claim_by_id[cid]["label"])
                    in_hist = False
                    on_src = False
                    in_same_rec = False
                    for sp in spbc_arr[k][cid]:
                        pp = parsed_by_cycle[k].get(sp)
                        if pp is None:
                            continue
                        if old_val in pp.raw_text:
                            on_src = True
                        if pp.has_history and old_val in pp.history_text:
                            in_hist = True
                        for rec in pp.records:
                            if rec.get("entity") == ent:
                                for fk, fv in rec.items():
                                    if fk not in ("entity", n_lbl) and fv == old_val:
                                        in_same_rec = True
                    if in_hist:
                        changed_old_val_in_history += 1
                    if on_src:
                        changed_old_val_on_source_page += 1
                    if in_same_rec:
                        changed_old_val_in_same_record += 1
            else:
                fail(f"{sid}/cycle_{k}: unknown cycle type {ctype!r}")

        if sorted(ctypes_seen) != ["F", "F", "N", "Z"]:
            fail(f"{sid}: cycle types must be permutation of ['F','F','N','Z'], got {ctypes_seen}")

        reordered_content_pages += len(reordered_pages_in_set)
        if set_had_pag_move:
            sets_with_pagination_move += 1

    # Compute measured shares
    share_3_source = changed_old_val_on_source_page / total_changed_claims if total_changed_claims else 0.0
    share_3_history = changed_old_val_in_history / total_changed_claims if total_changed_claims else 0.0
    share_3_c0 = claims_on_history_pages_c0 / total_claims if total_claims else 0.0
    share_4 = claims_with_row_placeholder_c0 / total_claims if total_claims else 0.0
    share_5_c0 = claims_with_shared_value_c0 / total_claims if total_claims else 0.0
    share_5 = changed_old_val_in_same_record / total_changed_claims if total_changed_claims else 0.0
    share_6_content = reordered_content_pages / total_content_pages if total_content_pages else 0.0
    share_6_all = reordered_content_pages / total_all_files if total_all_files else 0.0
    share_7 = sets_with_pagination_move / len(sets_list) if sets_list else 0.0

    # Threshold enforcement
    if share_3_source < 0.35 or share_3_history < 0.35:
        fail(f"Requirement (3) below 0.35: source={share_3_source:.4f}, history={share_3_history:.4f}")
    if share_4 < 0.30:
        fail(f"Requirement (4) below 0.30: {share_4:.4f}")
    if share_5 < 0.15:
        fail(f"Requirement (5) below 0.15: {share_5:.4f}")
    if share_6_content < 0.30:
        fail(f"Requirement (6) below 0.30: {share_6_content:.4f}")
    if total_n_cycles > 0 and n_cycles_with_reorder < total_n_cycles / 2:
        fail(f"Requirement (6): fewer than half of N cycles reordered ({n_cycles_with_reorder}/{total_n_cycles})")
    if total_f_cycles > 0 and f_cycles_with_reorder == 0:
        fail("Requirement (6): no F cycle had a reordered page")
    if sets_with_pagination_move == 0:
        fail("Requirement (7): no set had a pagination move")

    # Print measured shares report
    print(f"Dataset: {root} (generator={manifest.get('generator')}, seed={manifest.get('seed')}, sets={len(sets_list)})")
    print(f"  (3) History old-value persistence (source / history): {share_3_source:.4f} / {share_3_history:.4f} "
          f"({changed_old_val_on_source_page}/{total_changed_claims} source, {changed_old_val_in_history}/{total_changed_claims} history; "
          f"cycle-0 claims on history pages: {share_3_c0:.4f}) [min 0.35]")
    print(f"  (4) Per-fetch placeholder same line/record/row:       {share_4:.4f} "
          f"({claims_with_row_placeholder_c0}/{total_claims}) [min 0.30]")
    print(f"  (5) Shared value in same record after F change:       {share_5:.4f} "
          f"({changed_old_val_in_same_record}/{total_changed_claims}; cycle-0 shared claims: {share_5_c0:.4f}) [min 0.15]")
    print(f"  (6) Reordered pages (content / all site files):       {share_6_content:.4f} / {share_6_all:.4f} "
          f"({reordered_content_pages}/{total_content_pages} content, {reordered_content_pages}/{total_all_files} all; "
          f"N cycles={n_cycles_with_reorder}/{total_n_cycles}, F cycles={f_cycles_with_reorder}/{total_f_cycles}) [min 0.30]")
    print(f"  (7) Pagination moves (sets with move / total moves):  {share_7:.4f} "
          f"({sets_with_pagination_move}/{len(sets_list)} sets, {total_pagination_moves} moves) [min 1 set]")

    if errors:
        print(f"\nFAIL ({len(errors)} violation(s)):", file=sys.stderr)
        for e in errors[:50]:
            print(f"  - {e}", file=sys.stderr)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more", file=sys.stderr)
        return 1

    print("PASS: all heldout-v4 checks satisfied.")
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if len(argv) != 1:
        print("Usage: python3 check_heldout4.py <dir>", file=sys.stderr)
        return 2
    return check_dataset(Path(argv[0]))


if __name__ == "__main__":
    raise SystemExit(main())
