#!/usr/bin/env python3
"""Verify heldout-v2 benchmark directory layout, manifest, cycles, and difficulty distribution.

CLI:
    python3 check_heldout2.py <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from typing import Any


EXPECTED_SCHEMA = "vacant.d2.manifest/1"
EXPECTED_GENERATOR = "heldout-v2"
EXPECTED_CYCLE_TYPES = ["F", "F", "N", "Z"]
ALLOWED_EXTS = {".html", ".md", ".txt"}

VERSION_RE = re.compile(r"^v\d+\.\d+(?:\.\d+)?$")
NUMBER_VAL_RE = re.compile(r"^(?:[$€£])?\d+(?:\.\d+)?(?: ?(?:%|[A-Za-z]+(?:/[A-Za-z]+)?))?$")
NUMBER_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?")
ANY_VAL_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9.$€£])(?:v\d+\.\d+(?:\.\d+)?|(?:[$€£])?\d+(?:\.\d+)?(?: ?(?:%|[A-Za-z]+(?:/[A-Za-z]+)?))?)(?!(?:[A-Za-z0-9%/]|\.\d))"
)
BAD_SLUG_RE = re.compile(r"(?:^|[^A-Za-z0-9])p\d", re.IGNORECASE)
TEMPLATE_CLAIM_RE = re.compile(r"^- (.+) \u2014 (.+): ____$")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_pattern(val: str) -> re.Pattern[str]:
    return re.compile(
        r"(?<![A-Za-z0-9.$€£])" + re.escape(val) + r"(?!(?:[A-Za-z0-9%/]|\.\d))"
    )


def parse_value_core(val: str) -> tuple[str, Any] | None:
    """Validate that val contains exactly one number or one version string, with optional unit/currency."""
    if not isinstance(val, str) or not val or val != val.strip():
        return None
    if VERSION_RE.fullmatch(val):
        parts = tuple(int(x) for x in val[1:].split("."))
        return ("ver", parts)
    if NUMBER_VAL_RE.fullmatch(val):
        nums = NUMBER_TOKEN_RE.findall(val)
        if len(nums) == 1:
            return ("num", float(nums[0]))
    return None


def extract_sentences(text: str, ext: str) -> list[str]:
    """Extract clean text sentences from .html, .md, or .txt without losing sentence boundaries."""
    if ext == ".html":
        # Remove head/title/script/style blocks
        cleaned = re.sub(r"<(head|script|style)\b[^>]*>.*?</\1>", "\n", text, flags=re.IGNORECASE | re.DOTALL)
        # Convert block boundaries to newlines
        cleaned = re.sub(
            r"</?(?:p|li|ul|ol|div|section|article|main|header|footer|h[1-6]|tr|td|th|br)\b[^>]*>",
            "\n",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = html.unescape(cleaned)
    else:
        cleaned = text

    sentences: list[str] = []
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ext == ".md":
            # Strip heading markers and bullet prefixes
            line = re.sub(r"^#{1,6}\s+", "", line)
            line = re.sub(r"^[-*+]\s+", "", line)
        elif ext == ".txt":
            line = re.sub(r"^===.*===$", "", line).strip()
            line = re.sub(r"^[-*]\s+", "", line)
        if not line:
            continue
        # Split on sentence-ending punctuation followed by whitespace
        parts = re.split(r"(?<=[.!?])\s+", line)
        for p in parts:
            s = p.strip()
            if s:
                sentences.append(s)
    return sentences


def count_bounded_occurrences(text: str, ext: str, val: str) -> int:
    """Count bounded occurrences of val in visible body text of a page."""
    if ext == ".html":
        body = re.sub(r"<(head|script|style)\b[^>]*>.*?</\1>", "\n", text, flags=re.IGNORECASE | re.DOTALL)
        body = re.sub(r"<[^>]+>", " ", body)
        body = html.unescape(body)
    else:
        body = text
    return len(value_pattern(val).findall(body))


def check_heading_distance(text: str, ext: str, entity: str, val: str) -> int | None:
    """If the page has a heading for entity and a later entity-free line with val, return line distance."""
    lines = text.splitlines()
    ent_lower = entity.lower()
    val_pat = value_pattern(val)

    heading_line: int | None = None
    best_dist: int | None = None

    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        is_heading = False
        if ext == ".md" and stripped.startswith("#"):
            is_heading = True
        elif ext == ".html" and re.search(r"<h[1-6]\b", stripped, re.IGNORECASE):
            is_heading = True
        elif ext == ".txt" and stripped.startswith("===") and stripped.endswith("==="):
            is_heading = True

        if is_heading:
            plain_h = html.unescape(re.sub(r"<[^>]+>", " ", stripped)).lower()
            if ent_lower in plain_h:
                heading_line = idx
            elif heading_line is not None and (
                (ext == ".md" and stripped.startswith("## "))
                or (ext == ".html" and re.search(r"<h2\b", stripped, re.IGNORECASE))
                or (ext == ".txt" and stripped.startswith("==="))
            ):
                heading_line = None
            continue

        if heading_line is not None:
            plain_l = html.unescape(re.sub(r"<[^>]+>", " ", stripped))
            if val_pat.search(plain_l) and ent_lower not in plain_l.lower():
                dist = idx - heading_line
                if best_dist is None or dist > best_dist:
                    best_dist = dist

    return best_dist


def verify_dataset(root: Path) -> tuple[bool, list[str], dict[str, Any]]:
    errors: list[str] = []

    def err(msg: str) -> None:
        errors.append(msg)

    if not root.exists() or not root.is_dir():
        err(f"Dataset directory does not exist or is not a directory: {root}")
        return False, errors, {}

    manifest_path = root / "manifest.json"
    sha_path = root / "manifest.sha256"

    if not manifest_path.is_file():
        err(f"Missing manifest.json at {manifest_path}")
        return False, errors, {}
    if not sha_path.is_file():
        err(f"Missing manifest.sha256 at {sha_path}")
    else:
        manifest_bytes = manifest_path.read_bytes()
        expected_digest = hashlib.sha256(manifest_bytes).hexdigest()
        sha_raw = sha_path.read_text(encoding="utf-8").strip()
        sha_tokens = sha_raw.split()
        if not sha_tokens or sha_tokens[0] != expected_digest or len(sha_tokens) > 2:
            err(f"manifest.sha256 mismatch: expected {expected_digest}, got {sha_raw!r}")
        elif len(sha_tokens) == 2 and sha_tokens[1] != "manifest.json":
            err(f"manifest.sha256 unexpected filename token: {sha_tokens[1]!r}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        err(f"Invalid JSON in manifest.json: {exc}")
        return False, errors, {}

    # Top-level manifest schema
    if manifest.get("schema") != EXPECTED_SCHEMA:
        err(f"schema mismatch: expected {EXPECTED_SCHEMA!r}, got {manifest.get('schema')!r}")
    if manifest.get("generator") != EXPECTED_GENERATOR:
        err(f"generator mismatch: expected {EXPECTED_GENERATOR!r}, got {manifest.get('generator')!r}")
    if not isinstance(manifest.get("seed"), int) or isinstance(manifest.get("seed"), bool):
        err(f"seed must be int, got {manifest.get('seed')!r}")
    n_sets = manifest.get("n_sets")
    if not isinstance(n_sets, int) or isinstance(n_sets, bool) or n_sets < 1:
        err(f"n_sets must be positive int, got {n_sets!r}")
        return False, errors, {}
    if manifest.get("cycle_types") != EXPECTED_CYCLE_TYPES:
        err(f"cycle_types mismatch: expected {EXPECTED_CYCLE_TYPES!r}, got {manifest.get('cycle_types')!r}")

    sets_list = manifest.get("sets")
    if not isinstance(sets_list, list) or len(sets_list) != n_sets:
        err(f"sets length mismatch: expected {n_sets}, got {len(sets_list) if isinstance(sets_list, list) else type(sets_list)}")
        return False, errors, {}

    sets_dir = root / "sets"
    if not sets_dir.is_dir():
        err(f"Missing sets/ directory at {sets_dir}")
        return False, errors, {}

    expected_set_ids = [f"s{i + 1:02d}" for i in range(n_sets)]
    actual_set_dirs = sorted(p.name for p in sets_dir.iterdir() if p.is_dir())
    if actual_set_dirs != expected_set_ids:
        err(f"Set directories mismatch: expected {expected_set_ids}, got {actual_set_dirs}")

    # Global difficulty metrics accumulators
    total_claims = 0
    entity_free_claims = 0
    same_val_diff_meaning_claims = 0
    multi_page_claims = 0
    long_pages_total = 0
    far_heading_claims = 0
    total_claim_occs = 0
    total_val_tokens = 0

    for idx_s, s_entry in enumerate(sets_list):
        sid = s_entry.get("set")
        exp_sid = expected_set_ids[idx_s]
        if sid != exp_sid:
            err(f"Set #{idx_s}: expected id {exp_sid!r}, got {sid!r}")
            continue

        s_dir = sets_dir / sid
        domain = s_entry.get("domain")
        if not isinstance(domain, str) or not domain.strip():
            err(f"[{sid}] Missing or empty domain")

        index_file = s_entry.get("index")
        pages = s_entry.get("pages")
        if not isinstance(index_file, str) or Path(index_file).suffix not in ALLOWED_EXTS:
            err(f"[{sid}] Invalid index filename: {index_file!r}")
            continue
        if not isinstance(pages, list) or not (5 <= len(pages) <= 7):
            err(f"[{sid}] pages must be list of 5..7 files, got {pages!r}")
            continue
        if len(set(pages)) != len(pages):
            err(f"[{sid}] Duplicate filenames in pages: {pages!r}")
        if index_file in pages:
            err(f"[{sid}] index {index_file!r} must not appear in pages")

        all_files = [index_file] + pages
        exts_all = set()
        exts_content = set()
        for fn in all_files:
            if "/" in fn or "\\" in fn:
                err(f"[{sid}] Filename must be relative basename without path separators: {fn!r}")
            ext = Path(fn).suffix
            if ext not in ALLOWED_EXTS:
                err(f"[{sid}] Unsupported file extension on {fn!r}")
            exts_all.add(ext)
            if fn != index_file:
                exts_content.add(ext)
                stem = Path(fn).stem
                if BAD_SLUG_RE.search(stem):
                    err(f"[{sid}] Non-descriptive slug matching p<digit>: {fn!r}")

        if len(exts_all) < 2 or len(exts_content) < 2:
            err(f"[{sid}] Need >= 2 file formats per set, got content={sorted(exts_content)}, all={sorted(exts_all)}")

        # Claims & template verification
        claims = s_entry.get("claims")
        if not isinstance(claims, list) or len(claims) != 20:
            err(f"[{sid}] Expected exactly 20 claims, got {len(claims) if isinstance(claims, list) else type(claims)}")
            continue

        expected_cids = [f"c{i + 1:02d}" for i in range(20)]
        claim_by_id: dict[str, dict[str, Any]] = {}
        entities_in_set: set[str] = set()
        prefixes_seen: set[str] = set()

        for c_idx, cl in enumerate(claims):
            cid = cl.get("id")
            if cid != expected_cids[c_idx]:
                err(f"[{sid}] Claim #{c_idx}: expected id {expected_cids[c_idx]!r}, got {cid!r}")
            ent = cl.get("entity")
            lbl = cl.get("label")
            tline = cl.get("template_line")
            spages = cl.get("source_pages")
            if not isinstance(ent, str) or not ent.strip():
                err(f"[{sid} {cid}] Invalid entity: {ent!r}")
            else:
                entities_in_set.add(ent)
            if not isinstance(lbl, str) or not lbl.strip():
                err(f"[{sid} {cid}] Invalid label: {lbl!r}")
            expected_tline = f"- {ent} \u2014 {lbl}: "
            if tline != expected_tline:
                err(f"[{sid} {cid}] template_line mismatch: expected {expected_tline!r}, got {tline!r}")
            if tline in prefixes_seen:
                err(f"[{sid} {cid}] Duplicate template_line prefix: {tline!r}")
            prefixes_seen.add(tline)

            if not isinstance(spages, list) or not spages:
                err(f"[{sid} {cid}] source_pages must be non-empty list, got {spages!r}")
            else:
                if len(set(spages)) != len(spages):
                    err(f"[{sid} {cid}] Duplicate entries in source_pages: {spages!r}")
                for sp in spages:
                    if sp not in pages:
                        err(f"[{sid} {cid}] source_page {sp!r} not in pages")
            claim_by_id[cid] = cl

        # Verify template.md
        tmpl_path = s_dir / "template.md"
        if not tmpl_path.is_file():
            err(f"[{sid}] Missing template.md")
        else:
            tmpl_lines = tmpl_path.read_text(encoding="utf-8").splitlines()
            non_empty = [ln for ln in tmpl_lines if ln.strip()]
            if len(non_empty) < 22:
                err(f"[{sid}] template.md too short ({len(non_empty)} non-empty lines)")
            else:
                if not non_empty[0].startswith("# "):
                    err(f"[{sid}] template.md first line must be title '# ...', got {non_empty[0]!r}")
                if non_empty[1].startswith("#") or non_empty[1].startswith("- "):
                    err(f"[{sid}] template.md second non-empty line must be instruction line, got {non_empty[1]!r}")

            claim_lines = [ln for ln in tmpl_lines if ln.startswith("- ")]
            if len(claim_lines) != 20:
                err(f"[{sid}] template.md must have exactly 20 '- ' claim lines, got {len(claim_lines)}")
            else:
                tmpl_prefixes = set()
                for c_idx, ln in enumerate(claim_lines):
                    m = TEMPLATE_CLAIM_RE.fullmatch(ln)
                    if not m:
                        err(f"[{sid}] template.md line {ln!r} does not match '- <Entity> — <label>: ____'")
                        continue
                    expected_full = claims[c_idx]["template_line"] + "____"
                    if ln != expected_full:
                        err(f"[{sid}] template.md line #{c_idx+1} mismatch: expected {expected_full!r}, got {ln!r}")
                    tmpl_prefixes.add(ln[:-4])
                if len(tmpl_prefixes) != 20:
                    err(f"[{sid}] template.md prefixes through ': ' are not unique")

            # Check optional headings and ensure no stray unexpected lines
            for ln in non_empty[2:]:
                if ln.startswith("- "):
                    continue
                if ln.startswith("## "):
                    continue
                err(f"[{sid}] template.md unexpected line outside title/instruction/headings/claims: {ln!r}")

        # Truth validation
        truth = s_entry.get("truth")
        if not isinstance(truth, list) or len(truth) != 5:
            err(f"[{sid}] truth must have length 5, got {len(truth) if isinstance(truth, list) else type(truth)}")
            continue
        for k in range(5):
            if not isinstance(truth[k], dict) or sorted(truth[k].keys()) != expected_cids:
                err(f"[{sid} cycle {k}] truth keys mismatch")
            else:
                for cid, val in truth[k].items():
                    if parse_value_core(val) is None:
                        err(f"[{sid} cycle {k} {cid}] Invalid value format (must be 1 number or 1 version): {val!r}")

        # Check cycle directories and page_sha256
        page_sha256 = s_entry.get("page_sha256")
        if not isinstance(page_sha256, list) or len(page_sha256) != 5:
            err(f"[{sid}] page_sha256 must have length 5")
            continue

        expected_cycle_dirs = [f"cycle_{k}" for k in range(5)]
        actual_cycle_dirs = sorted(p.name for p in s_dir.iterdir() if p.is_dir())
        if actual_cycle_dirs != expected_cycle_dirs:
            err(f"[{sid}] Cycle directories mismatch: expected {expected_cycle_dirs}, got {actual_cycle_dirs}")

        site_texts: list[dict[str, str]] = []
        for k in range(5):
            site_dir = s_dir / f"cycle_{k}" / "site"
            if not site_dir.is_dir():
                err(f"[{sid} cycle {k}] Missing site/ directory")
                site_texts.append({})
                continue
            actual_files = sorted(p.name for p in site_dir.iterdir() if p.is_file())
            if actual_files != sorted(all_files):
                err(f"[{sid} cycle {k}] Site files mismatch: expected {sorted(all_files)}, got {actual_files}")
            sha_map = page_sha256[k]
            if not isinstance(sha_map, dict) or sorted(sha_map.keys()) != sorted(all_files):
                err(f"[{sid} cycle {k}] page_sha256 keys mismatch")
            texts_k: dict[str, str] = {}
            for fn in all_files:
                fpath = site_dir / fn
                if fpath.is_file():
                    actual_hash = sha256_file(fpath)
                    if isinstance(sha_map, dict) and sha_map.get(fn) != actual_hash:
                        err(f"[{sid} cycle {k} {fn}] sha256 mismatch: manifest={sha_map.get(fn)}, disk={actual_hash}")
                    texts_k[fn] = fpath.read_text(encoding="utf-8")
            site_texts.append(texts_k)

            # Check index lists every content page with a relative link
            idx_text = texts_k.get(index_file, "")
            for pfn in pages:
                if index_file.endswith(".html"):
                    if f'href="{pfn}"' not in idx_text and f'href="./{pfn}"' not in idx_text:
                        err(f"[{sid} cycle {k}] HTML index missing relative link to {pfn!r}")
                elif index_file.endswith(".md"):
                    if f"]({pfn})" not in idx_text and f"](./{pfn})" not in idx_text:
                        err(f"[{sid} cycle {k}] Markdown index missing relative link to {pfn!r}")
                else:
                    if pfn not in idx_text:
                        err(f"[{sid} cycle {k}] Text index missing reference to {pfn!r}")

            # Check every claim's value at cycle k appears on every page in source_pages
            for cl in claims:
                cid = cl["id"]
                val = truth[k][cid]
                for sp in cl["source_pages"]:
                    txt = texts_k.get(sp, "")
                    if count_bounded_occurrences(txt, Path(sp).suffix, val) < 1:
                        err(f"[{sid} cycle {k} {cid}] Value {val!r} not found in source page {sp!r}")

        # Cycles metadata & transitions verification
        cycles = s_entry.get("cycles")
        if not isinstance(cycles, list) or len(cycles) != 4:
            err(f"[{sid}] cycles must have length 4")
            continue

        seen_types = [cy.get("type") for cy in cycles]
        if sorted(seen_types) != sorted(EXPECTED_CYCLE_TYPES):
            err(f"[{sid}] Cycle types multiset mismatch: expected {EXPECTED_CYCLE_TYPES}, got {seen_types}")

        ever_changed_claims: set[str] = set()
        for idx_cy, cy in enumerate(cycles):
            k = idx_cy + 1
            if cy.get("cycle") != k:
                err(f"[{sid}] cycles[{idx_cy}].cycle expected {k}, got {cy.get('cycle')!r}")
            ctype = cy.get("type")
            c_changed = cy.get("changed_claims")
            c_noise = cy.get("noise_pages")

            actual_truth_changed = [
                cid for cid in expected_cids if truth[k][cid] != truth[k - 1][cid]
            ]
            actual_file_changed = {
                fn for fn in all_files if page_sha256[k].get(fn) != page_sha256[k - 1].get(fn)
            }

            if ctype == "Z":
                if c_changed != [] or c_noise != []:
                    err(f"[{sid} cycle {k}] Z cycle must have empty changed_claims and noise_pages")
                if actual_truth_changed:
                    err(f"[{sid} cycle {k}] Z cycle changed truth values: {actual_truth_changed}")
                if actual_file_changed:
                    err(f"[{sid} cycle {k}] Z cycle is not byte-identical; changed files: {sorted(actual_file_changed)}")
                # Also double-check raw bytes on disk
                for fn in all_files:
                    b0 = (s_dir / f"cycle_{k-1}" / "site" / fn).read_bytes()
                    b1 = (s_dir / f"cycle_{k}" / "site" / fn).read_bytes()
                    if b0 != b1:
                        err(f"[{sid} cycle {k}] Z cycle file {fn!r} raw bytes differ")
            elif ctype == "N":
                if c_changed != []:
                    err(f"[{sid} cycle {k}] N cycle must have empty changed_claims")
                if not isinstance(c_noise, list) or not (1 <= len(c_noise) <= 2) or len(set(c_noise)) != len(c_noise):
                    err(f"[{sid} cycle {k}] N cycle must have 1-2 unique noise_pages, got {c_noise!r}")
                elif not set(c_noise).issubset(set(pages)):
                    err(f"[{sid} cycle {k}] N cycle noise_pages not in pages: {c_noise!r}")
                if actual_truth_changed:
                    err(f"[{sid} cycle {k}] N cycle must not change truth values: {actual_truth_changed}")
                if actual_file_changed != set(c_noise or []):
                    err(f"[{sid} cycle {k}] N cycle file changes {sorted(actual_file_changed)} != noise_pages {c_noise}")
            elif ctype == "F":
                if not isinstance(c_changed, list) or len(c_changed) != 2 or len(set(c_changed)) != 2:
                    err(f"[{sid} cycle {k}] F cycle must change exactly 2 distinct claims, got {c_changed!r}")
                    continue
                if not isinstance(c_noise, list) or len(c_noise) != 1 or c_noise[0] not in pages:
                    err(f"[{sid} cycle {k}] F cycle must have exactly 1 noise_page in pages, got {c_noise!r}")
                    continue
                if set(actual_truth_changed) != set(c_changed):
                    err(f"[{sid} cycle {k}] F cycle truth diffs {actual_truth_changed} != changed_claims {c_changed}")
                expected_changed_files: set[str] = set(c_noise)
                for cid in c_changed:
                    if cid in ever_changed_claims:
                        err(f"[{sid} cycle {k}] Claim {cid} changed more than once")
                    ever_changed_claims.add(cid)
                    old_v = truth[k - 1][cid]
                    new_v = truth[k][cid]
                    old_core = parse_value_core(old_v)
                    new_core = parse_value_core(new_v)
                    if old_core == new_core:
                        err(f"[{sid} cycle {k} {cid}] New value {new_v!r} does not differ numerically from old {old_v!r}")
                    expected_changed_files.update(claim_by_id[cid]["source_pages"])
                if actual_file_changed != expected_changed_files:
                    err(
                        f"[{sid} cycle {k}] F cycle changed files {sorted(actual_file_changed)} "
                        f"!= expected {sorted(expected_changed_files)}"
                    )
                # Verify colliding non-claim occurrences of old values stayed intact!
                for cid in c_changed:
                    old_v = truth[k - 1][cid]
                    # Count total occurrences of old_v across content pages at k-1 and k
                    occ_before = sum(
                        count_bounded_occurrences(site_texts[k - 1][p], Path(p).suffix, old_v)
                        for p in pages
                    )
                    occ_after = sum(
                        count_bounded_occurrences(site_texts[k][p], Path(p).suffix, old_v)
                        for p in pages
                    )
                    dropped_expected = sum(
                        len(claim_by_id[c2]["source_pages"])
                        for c2 in c_changed
                        if truth[k - 1][c2] == old_v
                    )
                    if occ_before > dropped_expected and occ_after < (occ_before - dropped_expected):
                        err(
                            f"[{sid} cycle {k} {cid}] Non-claim occurrences of old value {old_v!r} "
                            f"were unexpectedly altered (before={occ_before}, after={occ_after}, dropped={dropped_expected})"
                        )
            else:
                err(f"[{sid} cycle {k}] Invalid cycle type: {ctype!r}")

        # ---------------------------------------------------------------
        # HARDER distribution measurements for this set (at cycle 0)
        # ---------------------------------------------------------------
        texts_c0 = site_texts[0]
        sentences_c0: dict[str, list[str]] = {
            p: extract_sentences(texts_c0[p], Path(p).suffix) for p in pages
        }

        set_long_pages = 0
        for p in pages:
            n_lines = len(texts_c0[p].splitlines())
            if n_lines >= 60:
                set_long_pages += 1
            # Count numeric/version tokens for distractor density check
            body_text = "\n".join(sentences_c0[p])
            total_val_tokens += len(ANY_VAL_TOKEN_RE.findall(body_text))
        long_pages_total += set_long_pages
        if set_long_pages < 1:
            err(f"[{sid}] Expected at least 1 long content page (>= 60 lines), found 0")

        set_far_heading = 0
        for cl in claims:
            total_claims += 1
            cid = cl["id"]
            ent = cl["entity"]
            ent_lower = ent.lower()
            other_ents_lower = [e.lower() for e in entities_in_set if e != ent]
            val = truth[0][cid]
            val_pat = value_pattern(val)
            spages = cl["source_pages"]
            total_claim_occs += len(spages)

            # 1) Entity-name-free sentence share
            found_entity_free = False
            for sp in spages:
                for sent in sentences_c0[sp]:
                    if not val_pat.search(sent):
                        continue
                    s_low = sent.lower()
                    if ent_lower in s_low:
                        continue
                    if any(oe in s_low for oe in other_ents_lower):
                        continue
                    found_entity_free = True
                    break
                if found_entity_free:
                    break
            if found_entity_free:
                entity_free_claims += 1

            # 2) Same value, different meaning share
            other_claim_same_val = any(
                c2["id"] != cid and truth[0][c2["id"]] == val for c2 in claims
            )
            total_occ_in_set = sum(
                count_bounded_occurrences(texts_c0[p], Path(p).suffix, val) for p in pages
            )
            if other_claim_same_val or total_occ_in_set > len(spages):
                same_val_diff_meaning_claims += 1

            # 3) Multi-page claim share
            if len(spages) >= 2:
                multi_page_claims += 1
                if len(spages) > 3:
                    err(f"[{sid} {cid}] Multi-page claim appears on {len(spages)} pages (expected 2-3)")

            # 4) Long-page distance from entity heading
            for sp in spages:
                if len(texts_c0[sp].splitlines()) >= 60:
                    dist = check_heading_distance(texts_c0[sp], Path(sp).suffix, ent, val)
                    if dist is not None and dist >= 15:
                        set_far_heading += 1
                        far_heading_claims += 1
                        break

        if set_far_heading < 1:
            err(f"[{sid}] Expected at least 1 claim on a long page (>=60 lines) at least 15 lines from its entity heading")

    # Compute overall shares
    if total_claims == 0:
        err("No claims were evaluated")
        return False, errors, {}

    share_entity_free = entity_free_claims / total_claims
    share_same_val_diff = same_val_diff_meaning_claims / total_claims
    share_multi_page = multi_page_claims / total_claims
    distractor_ratio = (total_val_tokens - total_claim_occs) / max(1, total_claim_occs)

    if share_entity_free < 0.35:
        err(f"entity_free_sentence_share={share_entity_free:.3f} < 0.35 threshold")
    if share_same_val_diff < 0.35:
        err(f"same_value_different_meaning_share={share_same_val_diff:.3f} < 0.35 threshold")
    if share_multi_page < 0.35:
        err(f"multi_page_claim_share={share_multi_page:.3f} < 0.35 threshold")
    if distractor_ratio < 1.5:
        err(f"Low distractor number density: distractor_to_claim_ratio={distractor_ratio:.2f} < 1.5")

    metrics = {
        "n_sets": n_sets,
        "total_claims": total_claims,
        "entity_free_claims": entity_free_claims,
        "entity_free_sentence_share": share_entity_free,
        "same_val_diff_meaning_claims": same_val_diff_meaning_claims,
        "same_value_different_meaning_share": share_same_val_diff,
        "multi_page_claims": multi_page_claims,
        "multi_page_claim_share": share_multi_page,
        "long_pages_total": long_pages_total,
        "far_heading_claims": far_heading_claims,
        "total_claim_occurrences": total_claim_occs,
        "total_value_tokens": total_val_tokens,
        "distractor_to_claim_ratio": distractor_ratio,
    }
    return len(errors) == 0, errors, metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a heldout-v2 benchmark directory.")
    parser.add_argument("dir", type=Path, help="Generated dataset directory to verify.")
    args = parser.parse_args(argv)

    ok, errors, metrics = verify_dataset(args.dir)

    if metrics:
        print(f"Sets checked: {metrics['n_sets']} ({metrics['total_claims']} claims)")
        print(
            f"entity_free_sentence_share:         {metrics['entity_free_sentence_share']:.3f} "
            f"({metrics['entity_free_claims']}/{metrics['total_claims']})"
        )
        print(
            f"same_value_different_meaning_share: {metrics['same_value_different_meaning_share']:.3f} "
            f"({metrics['same_val_diff_meaning_claims']}/{metrics['total_claims']})"
        )
        print(
            f"multi_page_claim_share:             {metrics['multi_page_claim_share']:.3f} "
            f"({metrics['multi_page_claims']}/{metrics['total_claims']})"
        )
        print(
            f"long_pages (>=60 lines):            {metrics['long_pages_total']} "
            f"(far-from-heading claims: {metrics['far_heading_claims']})"
        )
        print(
            f"distractor_to_claim_ratio:          {metrics['distractor_to_claim_ratio']:.2f} "
            f"(total numeric/version tokens: {metrics['total_value_tokens']}, claim occs: {metrics['total_claim_occurrences']})"
        )

    if not ok:
        print(f"\nFAILED with {len(errors)} violation(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print("\nALL CHECKS PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
