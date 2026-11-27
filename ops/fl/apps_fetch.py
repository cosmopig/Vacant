#!/usr/bin/env python3
"""ops.fl.apps_fetch — Download, licence-check, parse examples, and filter the APPS test split.

Downloads `test.jsonl` from Hugging Face (`codeparrot/apps`) in a single sequential request
with User-Agent `research-client/1.0`, verifies the dataset card licence is MIT, records
provenance and counts in `MANIFEST.json`, and writes the filtered stdin/stdout bank
`apps_fl_bank.jsonl`.

Filter criteria:
- `difficulty` in `{"interview", "competition"}`
- `input_output` parseable with >= 6 test cases, all string inputs/outputs
- stdin-style (no `fn_name`)
- Parseable example section in `question` (deterministic regex parser; failures counted & excluded)
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys
import urllib.request
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.fl import atomic_write_json, atomic_write_text, sha256_bytes, sha256_file, utc_now_iso

APPS_DATASET_CARD_URL = "https://huggingface.co/datasets/codeparrot/apps/raw/main/README.md"
APPS_TEST_URL = "https://huggingface.co/datasets/codeparrot/apps/resolve/main/test.jsonl"
USER_AGENT = "research-client/1.0"
DEFAULT_APPS_DIR = pathlib.Path("~/dev/ops/ref/apps").expanduser()
ALLOWED_DIFFICULTIES = frozenset({"interview", "competition"})
ALLOWED_DIFFICULTIES_V2 = frozenset({"introductory", "interview", "competition"})
MIN_HIDDEN_TESTS = 6

# Regex patterns for deterministic APPS statement example parsing
_DASHED_SECTION_RE = re.compile(r"^-{3,}[ \t]*[A-Za-z][^\n]*?-{3,}", re.M)
_EXAMPLES_HDR_RE = re.compile(r"^-{3,}[ \t]*Examples?[ \t]*-{3,}[^\n]*$", re.M | re.I)
_SAMPLE_IO_HDR_RE = re.compile(
    r"^-{3,}[ \t]*Sample[ \t]+(Input|Output)(?:[ \t]+\d+)?[ \t]*-{3,}[^\n]*$",
    re.M | re.I,
)
_INNER_IO_LABEL_RE = re.compile(
    r"^[ \t]*(?:(?:Sample|Example)[ \t]+)?(Input|Output)(?:[ \t]+\d+)?[ \t]*:?[ \t]*$",
    re.M | re.I,
)
_STANDALONE_SAMPLE_IO_RE = re.compile(
    r"^[ \t]*Sample[ \t]+(Input|Output)(?:[ \t]+\d+)?[ \t]*:?[ \t]*$",
    re.M | re.I,
)


def _clean_block_lines(raw: str) -> str:
    """Normalize line endings, strip trailing whitespace per line, strip leading/trailing blank lines."""
    lines = [ln.rstrip() for ln in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _first_paragraph(raw: str) -> str:
    """Extract the first contiguous non-blank paragraph (strips AtCoder trailing prose explanations)."""
    cleaned = _clean_block_lines(raw)
    if not cleaned:
        return ""
    out_lines: list[str] = []
    for ln in cleaned.split("\n"):
        if ln == "":
            break
        out_lines.append(ln)
    return "\n".join(out_lines)


def parse_apps_examples(question: str) -> tuple[list[dict[str, str]], str | None]:
    """Deterministically parse stdin/stdout example pairs from an APPS problem statement.

    Supports:
    1. `-----Example-----` / `-----Examples-----` sections containing `Input`/`Output`
       (or `Sample Input N:` / `Sample Output N:`) blocks (Codeforces / Kattis / CodeChef).
    2. `-----Sample Input [N]-----` / `-----Sample Output [N]-----` sections (AtCoder),
       stripping prose explanations that follow a blank line after sample output.
    3. Standalone `Sample Input [N]:` / `Sample Output [N]:` blocks without dashed headers.

    Returns `(examples, error_reason)`. On failure, returns `([], reason)`.
    """
    text = (question or "").replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        return [], "empty_question"

    # Strategy 1: -----Example----- / -----Examples----- section
    m_ex = _EXAMPLES_HDR_RE.search(text)
    if m_ex is not None:
        rest = text[m_ex.end() :]
        m_next = _DASHED_SECTION_RE.search(rest)
        sec = rest[: m_next.start()] if m_next is not None else rest

        markers = list(_INNER_IO_LABEL_RE.finditer(sec))
        if not markers:
            return [], "examples_section_no_io_labels"
        if len(markers) % 2 != 0:
            return [], f"examples_section_unpaired_labels({len(markers)})"

        pairs: list[dict[str, str]] = []
        for i in range(0, len(markers), 2):
            m_in, m_out = markers[i], markers[i + 1]
            if m_in.group(1).lower() != "input" or m_out.group(1).lower() != "output":
                return [], "examples_section_bad_label_order"
            in_raw = sec[m_in.end() : m_out.start()]
            out_end = markers[i + 2].start() if (i + 2) < len(markers) else len(sec)
            out_raw = sec[m_out.end() : out_end]

            inp = _clean_block_lines(in_raw)
            out = _clean_block_lines(out_raw)
            if not out:
                return [], f"empty_example_output_at_{i // 2}"
            pairs.append({"input": inp + "\n" if inp else "", "output": out})

        if not pairs:
            return [], "examples_section_zero_pairs"
        return pairs, None

    # Strategy 2: -----Sample Input [N]----- / -----Sample Output [N]----- sections
    sample_hdrs = list(_SAMPLE_IO_HDR_RE.finditer(text))
    if sample_hdrs:
        if len(sample_hdrs) % 2 != 0:
            return [], f"sample_headers_unpaired({len(sample_hdrs)})"
        pairs = []
        for i in range(0, len(sample_hdrs), 2):
            m_in, m_out = sample_hdrs[i], sample_hdrs[i + 1]
            if m_in.group(1).lower() != "input" or m_out.group(1).lower() != "output":
                return [], "sample_headers_bad_order"

            in_slice = text[m_in.end() : m_out.start()]
            m_in_next = _DASHED_SECTION_RE.search(in_slice)
            if m_in_next is not None:
                in_slice = in_slice[: m_in_next.start()]

            next_start = sample_hdrs[i + 2].start() if (i + 2) < len(sample_hdrs) else len(text)
            out_slice = text[m_out.end() : next_start]
            m_out_next = _DASHED_SECTION_RE.search(out_slice)
            if m_out_next is not None:
                out_slice = out_slice[: m_out_next.start()]

            inp = _first_paragraph(in_slice)
            out = _first_paragraph(out_slice)
            if not out:
                return [], f"empty_sample_output_at_{i // 2}"
            pairs.append({"input": inp + "\n" if inp else "", "output": out})

        if not pairs:
            return [], "sample_headers_zero_pairs"
        return pairs, None

    # Strategy 3: Standalone Sample Input / Sample Output labels without dashed headers
    standalone = list(_STANDALONE_SAMPLE_IO_RE.finditer(text))
    if standalone and len(standalone) % 2 == 0:
        pairs = []
        for i in range(0, len(standalone), 2):
            m_in, m_out = standalone[i], standalone[i + 1]
            if m_in.group(1).lower() != "input" or m_out.group(1).lower() != "output":
                return [], "standalone_sample_bad_order"
            in_raw = text[m_in.end() : m_out.start()]
            out_end = standalone[i + 2].start() if (i + 2) < len(standalone) else len(text)
            out_raw = text[m_out.end() : out_end]
            m_next = _DASHED_SECTION_RE.search(out_raw)
            if m_next is not None:
                out_raw = out_raw[: m_next.start()]
            inp = _first_paragraph(in_raw)
            out = _first_paragraph(out_raw)
            if not out:
                return [], f"empty_standalone_output_at_{i // 2}"
            pairs.append({"input": inp + "\n" if inp else "", "output": out})
        if pairs:
            return pairs, None

    return [], "no_example_section_found"


def fetch_and_verify_mit_licence(
    card_url: str = APPS_DATASET_CARD_URL,
    *,
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    """Fetch the Hugging Face dataset card README.md (single request) and verify MIT licence."""
    req = urllib.request.Request(card_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw_bytes = resp.read()
    text = raw_bytes.decode("utf-8", errors="replace")

    m_fm = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m_fm:
        raise ValueError(f"Dataset card at {card_url} is missing YAML frontmatter")
    fm = m_fm.group(1)
    # Match either `license: mit` or YAML list `license:\n- mit`
    m_lic = re.search(
        r"^license:\s*(?:(mit)\b|\n(?:[ \t]*-[ \t]*[^\n]+\n)*?[ \t]*-[ \t]*(mit)\b)",
        fm,
        re.M | re.I,
    )
    if not m_lic:
        raise ValueError(f"Dataset card at {card_url} does not declare MIT licence in frontmatter:\n{fm}")
    evidence_lines = [ln for ln in fm.splitlines() if "license" in ln.lower() or ln.strip().lower() == "- mit"]
    return {
        "licence": "MIT",
        "dataset_card_url": card_url,
        "dataset_card_sha256": sha256_bytes(raw_bytes),
        "frontmatter_evidence": "\n".join(evidence_lines),
    }


def download_single_request(url: str, dest: pathlib.Path, *, timeout_s: float = 300.0) -> int:
    """Download `url` to `dest` atomically using a single sequential HTTP request."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.download.tmp")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    total = 0
    with urllib.request.urlopen(req, timeout=timeout_s) as resp, open(tmp, "wb") as fh:
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            fh.write(chunk)
            total += len(chunk)
    tmp.replace(dest)
    return total


def build_apps_fl_bank(
    raw_test_jsonl: pathlib.Path,
    out_bank_jsonl: pathlib.Path,
    *,
    allowed_difficulties: frozenset[str] = ALLOWED_DIFFICULTIES,
) -> dict[str, Any]:
    """Stream `raw_test_jsonl`, filter to allowed difficulties stdin tasks with >=6 tests & parseable examples."""
    allowed = frozenset(d.strip().lower() for d in allowed_difficulties)
    counts: dict[str, int] = {
        "total_fetched": 0,
        "excluded_difficulty": 0,
        "excluded_no_or_bad_io": 0,
        "excluded_fn_name": 0,
        "excluded_too_few_tests": 0,
        "excluded_non_str_io": 0,
        "excluded_example_parse_failure": 0,
        "kept": 0,
    }
    by_difficulty: dict[str, int] = collections.Counter()
    parse_fail_reasons: dict[str, int] = collections.Counter()
    parse_fail_ids: list[str] = []

    out_bank_jsonl.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = out_bank_jsonl.with_name(f".{out_bank_jsonl.name}.tmp")

    with open(raw_test_jsonl, "r", encoding="utf-8") as fin, open(tmp_out, "w", encoding="utf-8") as fout:
        for line_no, raw_line in enumerate(fin, start=1):
            s = raw_line.strip()
            if not s:
                continue
            counts["total_fetched"] += 1
            row = json.loads(s)
            pid = row.get("problem_id", row.get("id", line_no - 1))
            tid = f"apps_{pid}"
            diff = str(row.get("difficulty") or "").strip().lower()
            if diff not in allowed:
                counts["excluded_difficulty"] += 1
                continue

            io_raw = row.get("input_output")
            if not isinstance(io_raw, str) or not io_raw.strip():
                counts["excluded_no_or_bad_io"] += 1
                continue
            try:
                io = json.loads(io_raw)
            except ValueError:
                counts["excluded_no_or_bad_io"] += 1
                continue
            if not isinstance(io, dict):
                counts["excluded_no_or_bad_io"] += 1
                continue
            if io.get("fn_name"):
                counts["excluded_fn_name"] += 1
                continue

            ins = io.get("inputs")
            outs = io.get("outputs")
            if (
                not isinstance(ins, list)
                or not isinstance(outs, list)
                or len(ins) != len(outs)
                or len(ins) < MIN_HIDDEN_TESTS
            ):
                counts["excluded_too_few_tests"] += 1
                continue

            if any((not isinstance(x, str)) or (not isinstance(y, str)) for x, y in zip(ins, outs)):
                counts["excluded_non_str_io"] += 1
                continue

            question = str(row.get("question") or "")
            examples, parse_err = parse_apps_examples(question)
            if parse_err is not None or not examples:
                counts["excluded_example_parse_failure"] += 1
                reason = parse_err or "zero_examples"
                parse_fail_reasons[reason] += 1
                parse_fail_ids.append(tid)
                continue

            bank_row = {
                "task_id": tid,
                "difficulty": diff,
                "prompt": question,
                "examples": examples,
                "hidden_tests": [{"input": x, "output": y} for x, y in zip(ins, outs)],
            }
            fout.write(json.dumps(bank_row, ensure_ascii=False) + "\n")
            counts["kept"] += 1
            by_difficulty[diff] += 1

    tmp_out.replace(out_bank_jsonl)
    return {
        "counts": counts,
        "by_difficulty": dict(sorted(by_difficulty.items())),
        "parse_failure_reasons": dict(sorted(parse_fail_reasons.items())),
        "parse_failure_task_ids": parse_fail_ids,
        "bank_sha256": sha256_file(out_bank_jsonl),
        "bank_size_bytes": out_bank_jsonl.stat().st_size,
    }


def fetch_and_build(
    out_dir: pathlib.Path = DEFAULT_APPS_DIR,
    *,
    force_download: bool = False,
) -> dict[str, Any]:
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "test.jsonl"
    bank_path = out_dir / "apps_fl_bank.jsonl"
    manifest_path = out_dir / "MANIFEST.json"

    licence_info = fetch_and_verify_mit_licence(APPS_DATASET_CARD_URL)
    if force_download or not raw_path.is_file() or raw_path.stat().st_size == 0:
        download_single_request(APPS_TEST_URL, raw_path)

    raw_sha = sha256_file(raw_path)
    raw_size = raw_path.stat().st_size
    build_res = build_apps_fl_bank(raw_path, bank_path)

    manifest: dict[str, Any] = {
        "schema": "vacant.fl.apps_manifest/1",
        "source_url": APPS_TEST_URL,
        "dataset_card_url": licence_info["dataset_card_url"],
        "dataset_card_sha256": licence_info["dataset_card_sha256"],
        "licence": licence_info["licence"],
        "licence_evidence": licence_info["frontmatter_evidence"],
        "user_agent": USER_AGENT,
        "fetch_date": utc_now_iso(),
        "raw_file": str(raw_path),
        "sha256": raw_sha,
        "raw_size_bytes": raw_size,
        "filtered_bank_file": str(bank_path),
        "filtered_bank_sha256": build_res["bank_sha256"],
        "filtered_bank_size_bytes": build_res["bank_size_bytes"],
        "filter_criteria": {
            "difficulties": sorted(ALLOWED_DIFFICULTIES),
            "min_hidden_tests": MIN_HIDDEN_TESTS,
            "stdin_only_no_fn_name": True,
            "require_parseable_examples": True,
        },
        "counts": build_res["counts"],
        "by_difficulty": build_res["by_difficulty"],
        "parse_failure_reasons": build_res["parse_failure_reasons"],
        "parse_failure_task_ids": build_res["parse_failure_task_ids"],
    }
    atomic_write_json(manifest_path, manifest)
    return manifest


def build_v2_from_existing(
    out_dir: pathlib.Path = DEFAULT_APPS_DIR,
) -> dict[str, Any]:
    """Re-filter already-downloaded `test.jsonl` (no network download) into `apps_fl_bank_v2.jsonl`
    including `introductory`, `interview`, and `competition`, and record a `v2` entry in `MANIFEST.json`.
    """
    out_dir = out_dir.expanduser().resolve()
    raw_path = out_dir / "test.jsonl"
    if not raw_path.is_file() or raw_path.stat().st_size == 0:
        raise FileNotFoundError(f"Already-downloaded APPS test.jsonl not found: {raw_path}")

    bank_v2_path = out_dir / "apps_fl_bank_v2.jsonl"
    manifest_path = out_dir / "MANIFEST.json"

    build_res = build_apps_fl_bank(
        raw_path,
        bank_v2_path,
        allowed_difficulties=ALLOWED_DIFFICULTIES_V2,
    )

    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {
            "schema": "vacant.fl.apps_manifest/1",
            "raw_file": str(raw_path),
            "sha256": sha256_file(raw_path),
            "raw_size_bytes": raw_path.stat().st_size,
        }

    v2_entry: dict[str, Any] = {
        "built_date": utc_now_iso(),
        "filtered_bank_file": str(bank_v2_path),
        "filtered_bank_sha256": build_res["bank_sha256"],
        "filtered_bank_size_bytes": build_res["bank_size_bytes"],
        "filter_criteria": {
            "difficulties": sorted(ALLOWED_DIFFICULTIES_V2),
            "min_hidden_tests": MIN_HIDDEN_TESTS,
            "stdin_only_no_fn_name": True,
            "require_parseable_examples": True,
        },
        "counts": build_res["counts"],
        "by_difficulty": build_res["by_difficulty"],
        "parse_failure_reasons": build_res["parse_failure_reasons"],
        "parse_failure_task_ids": build_res["parse_failure_task_ids"],
    }
    manifest["v2"] = v2_entry
    atomic_write_json(manifest_path, manifest)
    return v2_entry


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch APPS test split from HF and build apps_fl_bank[_v2].jsonl")
    ap.add_argument("--out-dir", type=pathlib.Path, default=DEFAULT_APPS_DIR, help="Output directory (default ~/dev/ops/ref/apps)")
    ap.add_argument("--force", action="store_true", help="Re-download test.jsonl even if already present")
    ap.add_argument(
        "--v2",
        action="store_true",
        help="Re-filter already-downloaded test.jsonl (no download) including introductory -> apps_fl_bank_v2.jsonl",
    )
    args = ap.parse_args()

    if args.v2:
        v2_entry = build_v2_from_existing(args.out_dir)
        print(json.dumps({k: v for k, v in v2_entry.items() if k != "parse_failure_task_ids"}, ensure_ascii=False, indent=2))
        return 0

    manifest = fetch_and_build(args.out_dir, force_download=args.force)
    print(json.dumps({k: v for k, v in manifest.items() if k != "parse_failure_task_ids"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
