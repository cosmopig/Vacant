#!/usr/bin/env python3
"""Experiment T feedback builder, record-only / blank / oracle flaggers, Haiku escalation, and signed Logbook chain.

Implements the seven cycle-0 arms of Experiment T:
  - A   : native shared c0 draft only (0 extra rounds)
  - G   : yoked generic review — triggers ONLY when T would send feedback on the same shared c0
          draft, and runs the exact same number of rounds as T actually used for that (set, rep)
  - T   : up to 2 extra rounds; recompute F1/F3 flags from RECORDS ONLY after each round;
          send back ONLY flagged lines using `vacant_network.trace.review` wording (`unsourced`
          via `review.line_for`) plus KS-1-checked templates for no-value and changed-without-source,
          plus the agent's own egress fetched-page list; stop when none flagged
  - TB  : blank-only control — send back ONLY lines with no value using template (a), same rounds
          and stop rule as T, no record info
  - TO  : oracle upper bound — send back lines that are actually wrong per the audited cycle-0
          answer key (including wrong_read) using neutral wording, NEVER revealing the correct value
  - TE  : host-side Claude Haiku escalation on RECORD-flagged lines (same flag set as T), given only
          the pages this cell actually fetched from the frozen revision-0 snapshot; replace only those lines
  - TER : host-side Claude Haiku escalation on the same number of lines chosen uniformly at random
          (seeded), using the same frozen fetched pages; replace only those lines

KS-1 iron rule (CLAUDE.md):
  - Value-not-in-fetched-content lines reuse `vacant_network.trace.review.line_for` (`unsourced`).
  - All Experiment T static templates are defined in one registry (`STATIC_TEMPLATES`) and checked
    at import time through BOTH `vacant_network.memory.assert_ks1_clean` AND
    `vacant_network.trace.feedback.feedback_ks1_clean`.
  - Every rendered agent-facing line is checked through `feedback_ks1_clean(line, actor_tokens)`;
    any line that fails is replaced by `review.WITHHELD` and counted (`withheld`).
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import html as _html
import json
import os
import pathlib
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Mapping, Sequence

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from vacant_network.memory import KS1Violation, assert_ks1_clean as mem_assert_ks1_clean  # noqa: E402
from vacant_network.trace import blame as B  # noqa: E402
from vacant_network.trace import feedback as FB_CORE  # noqa: E402
from vacant_network.trace import review as REV  # noqa: E402
from vacant_network.trace import sources as S  # noqa: E402
from vacant_network.trace.feedback import KS1FeedbackError, feedback_ks1_clean  # noqa: E402
from vacant_network.trace.recorder import Recorder  # noqa: E402

#: Valid Experiment T arms (T0 removed from plans/metrics; legacy helper kept unused).
EXPT_ARMS: tuple[str, ...] = ("A", "G", "T", "TB", "TO", "TE", "TER")

#: Signed logbook event types.
EXPT_EVENT_TYPE: str = "EXPT_FEEDBACK"
EXPT_ESCALATION_EVENT_TYPE: str = "EXPT_ESCALATION"

#: Problem-kind machine labels (stored in evidence / flags JSON).
PROBLEM_MISSING: str = "missing value"
PROBLEM_NOT_IN_FETCHED: str = "value not in any fetched page"
PROBLEM_CHANGED_NO_SOURCE: str = "changed without reading a source"
PROBLEM_ORACLE_WRONG: str = "oracle wrong"

#: Default Claude Haiku escalation settings.
DEFAULT_HAIKU_MODEL: str = "claude-haiku-5-5"
DEFAULT_ANTHROPIC_API_URL: str = "https://api.anthropic.com/v1/messages"
DEFAULT_HAIKU_PRICE_PER_MTOK_IN: float = 1.00
DEFAULT_HAIKU_PRICE_PER_MTOK_OUT: float = 5.00
DEFAULT_HAIKU_PRICE_PER_MTOK_CACHE_WRITE: float = 1.25
DEFAULT_HAIKU_PRICE_PER_MTOK_CACHE_READ: float = 0.10

# =============================================================================
# Single-Source Template Registry (KS-1 Checked at Import Time)
# =============================================================================

#: Header/footer reused for non-record arms (TB, TO) in the exact style of `review.py`.
REPORT_REVIEW_HEADER: str = "Before delivery: a check of report.md found points to redo."
TB_FOOTER: str = "This review lists lines in report.md without values; it does not say whether other answers are right."
TO_FOOTER: str = "Check the listed lines against the pages for this task; leave other lines as they are."

#: (a) Line has no value.
NO_VALUE_LINE_TEMPLATE: str = (
    "- {path} line {n}: no value is given. "
    "Look it up in the pages for this task and write it, or mark it as unknown on that line."
)
NO_VALUE_DELETED_TEMPLATE: str = (
    "- {path} ({label}): no value is given (line missing). "
    "Look it up in the pages for this task and write it, or mark it as unknown."
)

#: (b) Line changed in a step that read no source.
CHANGED_NO_SOURCE_LINE_TEMPLATE: str = (
    "- {path} line {n}: this line was changed in a step that read no page. "
    "Check it against the pages for this task and correct it if needed."
)
CHANGED_NO_SOURCE_DELETED_TEMPLATE: str = (
    "- {path} ({label}): this line was changed in a step that read no page. "
    "Check it against the pages for this task and correct it if needed."
)

#: TO (oracle upper bound) neutral line template — never includes the correct value.
ORACLE_WRONG_LINE_TEMPLATE: str = (
    "- {path} line {n}: this value may be wrong. "
    "Check it against the pages for this task and correct it if needed."
)
ORACLE_WRONG_DELETED_TEMPLATE: str = (
    "- {path} ({label}): this line is missing and its value may be wrong. "
    "Check it against the pages for this task and correct it if needed."
)

#: Fetched-pages tail for arm T.
T_FETCHED_HEADER: str = "Pages fetched in this task:"
T_FETCHED_NONE: str = "Pages fetched in this task: (none)"

#: Generic review prompt for yoked arm G (no record info).
GENERIC_REVIEW_PROMPT: str = (
    "Re-check report.md for completeness and correctness against the pages for this task "
    "and fix anything that is wrong."
)

#: Legacy unused count-only sentence (T0 removed from plans/metrics; still KS-1 checked).
T0_FEEDBACK_TEMPLATE: str = (
    "{n} line(s) in report.md have no supporting source in the fetched pages. "
    "Check and correct them against the pages for this task."
)

#: Host-side Claude Haiku escalation prompt templates (TE / TER).
HAIKU_ESCALATION_SYSTEM_PROMPT: str = (
    "Extract values for the listed report lines strictly from the provided source page texts. "
    "Do not use outside knowledge or guess. "
    "If a line's value cannot be found in the provided source page texts, output exactly: "
    "not found in sources. "
    "Return one line per requested item in the exact format: "
    "[CLAIM_ID]: <value or not found in sources>"
)
HAIKU_ESCALATION_USER_TEMPLATE: str = (
    "Fill each listed report line using strictly the provided fetched page texts below. "
    "If a value is not present in these pages, write: not found in sources.\n\n"
    "Lines to fill:\n"
    "{lines_block}\n\n"
    "Fetched pages (frozen revision-0 snapshot):\n"
    "{pages_block}\n\n"
    "Output one line per item in the format:\n"
    "[CLAIM_ID]: <value or not found in sources>"
)
HAIKU_LINE_WITH_VALUE_TEMPLATE: str = "- [{claim_id}] {label} (current value: {value})"
HAIKU_LINE_NO_VALUE_TEMPLATE: str = "- [{claim_id}] {label} (current value: none)"

#: Single registry of all static templates (reused from review.py + Experiment T new templates).
STATIC_TEMPLATES: dict[str, str] = {
    "review.REVIEW_HEADER": REV.REVIEW_HEADER,
    "review.PERSONA": REV.PERSONA,
    "review.FOOTER": REV.FOOTER,
    "review.WITHHELD": REV.WITHHELD,
    "review.line_for(unsourced)": REV.line_for(
        {"kind": "unsourced", "path": "report.md", "line": 1, "value": "example"}
    ),
    "REPORT_REVIEW_HEADER": REPORT_REVIEW_HEADER,
    "TB_FOOTER": TB_FOOTER,
    "TO_FOOTER": TO_FOOTER,
    "NO_VALUE_LINE_TEMPLATE": NO_VALUE_LINE_TEMPLATE,
    "NO_VALUE_DELETED_TEMPLATE": NO_VALUE_DELETED_TEMPLATE,
    "CHANGED_NO_SOURCE_LINE_TEMPLATE": CHANGED_NO_SOURCE_LINE_TEMPLATE,
    "CHANGED_NO_SOURCE_DELETED_TEMPLATE": CHANGED_NO_SOURCE_DELETED_TEMPLATE,
    "ORACLE_WRONG_LINE_TEMPLATE": ORACLE_WRONG_LINE_TEMPLATE,
    "ORACLE_WRONG_DELETED_TEMPLATE": ORACLE_WRONG_DELETED_TEMPLATE,
    "T_FETCHED_HEADER": T_FETCHED_HEADER,
    "T_FETCHED_NONE": T_FETCHED_NONE,
    "GENERIC_REVIEW_PROMPT": GENERIC_REVIEW_PROMPT,
    "T0_FEEDBACK_TEMPLATE": T0_FEEDBACK_TEMPLATE,
    "HAIKU_ESCALATION_SYSTEM_PROMPT": HAIKU_ESCALATION_SYSTEM_PROMPT,
    "HAIKU_ESCALATION_USER_TEMPLATE": HAIKU_ESCALATION_USER_TEMPLATE,
    "HAIKU_LINE_WITH_VALUE_TEMPLATE": HAIKU_LINE_WITH_VALUE_TEMPLATE,
    "HAIKU_LINE_NO_VALUE_TEMPLATE": HAIKU_LINE_NO_VALUE_TEMPLATE,
}


def assert_ks1_clean(text: str, actor_tokens: set[str] | None = None) -> str:
    """Run BOTH `vacant_network.memory.assert_ks1_clean` AND `vacant_network.trace.feedback.feedback_ks1_clean`."""
    mem_assert_ks1_clean(text)
    feedback_ks1_clean(text, actor_tokens or set())
    return text


def verify_all_templates_ks1(actor_tokens: set[str] | None = None) -> list[dict[str, Any]]:
    """Verify every registered template through `assert_ks1_clean` and `feedback_ks1_clean`."""
    toks = set(actor_tokens or ())
    results: list[dict[str, Any]] = []
    for name, tpl in STATIC_TEMPLATES.items():
        mem_assert_ks1_clean(tpl)
        feedback_ks1_clean(tpl, toks)
        results.append({"name": name, "ok": True, "chars": len(tpl)})
    # Also verify review.render on a representative unsourced finding
    rendered, withheld = REV.render(
        [{"kind": "unsourced", "path": "report.md", "line": 1, "value": "999"}],
        actor_tokens=toks,
    )
    assert withheld == 0
    mem_assert_ks1_clean(rendered)
    feedback_ks1_clean(rendered, toks)
    results.append({"name": "review.render(unsourced)", "ok": True, "chars": len(rendered)})
    return results


def format_ks1_check_report(actor_tokens: set[str] | None = None) -> str:
    """Return executable KS-1 verification output suitable for embedding verbatim in prereg."""
    rows = verify_all_templates_ks1(actor_tokens=actor_tokens)
    lines = [
        "所有提示與回饋模板已通過 KS-1 可執行檢查 "
        "(vacant_network.memory.assert_ks1_clean + vacant_network.trace.feedback.feedback_ks1_clean):",
    ]
    for r in rows:
        lines.append(f"  PASS {r['name']} ({r['chars']} chars)")
    lines.append(f"TOTAL: {len(rows)}/{len(rows)} PASS")
    return "\n".join(lines)


# Enforce KS-1 on all static templates at module import time.
verify_all_templates_ks1()


def _sanitize_line(line: str, actor_tokens: set[str]) -> tuple[str, int]:
    """Check one agent-facing line via `feedback_ks1_clean`; replace with `review.WITHHELD` on failure."""
    try:
        mem_assert_ks1_clean(line)
        feedback_ks1_clean(line, actor_tokens)
        return line, 0
    except (KS1FeedbackError, KS1Violation, ValueError):
        return REV.WITHHELD, 1


def _atomic_write_text(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}.{threading.get_ident()}")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


# =============================================================================
# Report Parsing & Strict Canonicalization
# =============================================================================

_NO_VALUE_MARKERS: frozenset[str] = frozenset({
    "",
    "unknown",
    "not found in sources",
    "not found in source",
    "n/a",
    "none",
})


def canon_strict(v: str | None) -> str | None:
    """Exact `score_d2 --strict` canonicalization without mutating global state."""
    if v is None:
        return None
    s = v.strip().strip("`*").strip()
    toks = [
        ("v" + t[1:].lstrip("v")) if t.lower().startswith("v") else t.replace(",", "")
        for t in re.findall(r"v?\d+(?:\.\d+){2,}|\d[\d,]*(?:\.\d+)?", s)
    ]
    toks = [t[:-2] if t.endswith(".0") else t for t in toks]
    return "|".join(toks) if toks else None


def claim_label(claim: Mapping[str, Any]) -> str:
    """Human-readable label for a claim from its template metadata (never reads truth)."""
    ent = str(claim.get("entity") or "").strip()
    lab = str(claim.get("label") or "").strip()
    if ent and lab:
        return f"{ent} — {lab}"
    tpl = str(claim.get("template_line") or "").strip()
    if tpl.startswith("- "):
        tpl = tpl[2:].strip()
    return tpl.rstrip(":").strip() or str(claim.get("id") or "")


def parse_report_lines(text: str, claims: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Parse each claim's 1-based line number and value from `report.md`.

    Empty values, `____` placeholders, and explicit no-value markers (`unknown`,
    `not found in sources`) normalize to `value=None`.
    """
    lines = text.splitlines()
    out: dict[str, dict[str, Any]] = {}
    for c in claims:
        cid = str(c["id"])
        pref = str(c["template_line"]).rstrip()
        key = pref.rstrip(":").rstrip()
        hit_idx: int | None = None
        hit_line: str | None = None
        for idx, ln in enumerate(lines, start=1):
            if ln.strip().startswith(key):
                hit_idx = idx
                hit_line = ln
                break
        if hit_line is None:
            out[cid] = {"line": None, "raw_value": None, "value": None, "present": False}
            continue
        raw_val = hit_line.split(":", 1)[1] if ":" in hit_line else ""
        val_s = raw_val.strip()
        if not val_s or "____" in val_s or val_s.lower().strip(" .`*") in _NO_VALUE_MARKERS:
            val_norm: str | None = None
        else:
            val_norm = val_s
        out[cid] = {"line": hit_idx, "raw_value": val_s, "value": val_norm, "present": True}
    return out


def parse_report_values(text: str, claims: Sequence[Mapping[str, Any]]) -> dict[str, str | None]:
    """Parse claim values from report.md (empty/placeholder/unknown normalized to None)."""
    parsed = parse_report_lines(text, claims)
    return {cid: info["value"] for cid, info in parsed.items()}


# =============================================================================
# Recorder Access & Flag Computation (Record-Only / Blank-Only / Oracle)
# =============================================================================


def open_recorder(vh: pathlib.Path, ws: pathlib.Path | None = None) -> Recorder | None:
    """Open an existing Vacant trace Recorder under `vh` (without mutating project hash)."""
    proj = vh / "trace" / "projects"
    dirs = sorted(d for d in proj.iterdir() if d.is_dir()) if proj.exists() else []
    if dirs:
        target = ws.resolve() if ws is not None else pathlib.Path("/nonexistent-d2-replay")
        rec = Recorder(target, root=vh / "trace")
        if not rec.dir.exists() or len(dirs) == 1:
            rec.dir = dirs[0]
            rec.chain_path = rec.dir / "chain.ndjson"
            rec.state_path = rec.dir / "state.json"
        return rec
    if ws is not None:
        return Recorder(ws.resolve(), root=vh / "trace")
    return None


def recorder_actor_tokens(rec: Recorder | None) -> set[str]:
    """Extract actor identifiers recorded in a trace so they are never leaked in feedback."""
    toks: set[str] = set()
    if rec is None:
        return toks
    try:
        for e in rec.events():
            a = e.get("actor")
            if isinstance(a, dict):
                for k in ("agent", "agent_type", "model"):
                    if a.get(k):
                        toks.add(str(a[k]))
    except Exception:  # noqa: BLE001
        pass
    return toks


def fetch_universe(rec: Recorder) -> list[dict[str, Any]]:
    """All fetched content recorded in the trace chain: product-recognized fetch steps,
    steps whose input mentions a URL, and egress `source_fetch` events (identical to exp1_flags).
    """
    trace = B.Trace(rec)
    out: list[dict[str, Any]] = []
    try:
        for r in S._fetch_records(trace, B.Blamer(trace)):
            out.append({"seq": int(r["seq"]), "url": r["url"], "text": r["text"], "source": "fetch_record"})
    except Exception:  # noqa: BLE001
        pass
    for st in trace.steps:
        us = S._urls_in(trace.input_text(st))
        if us:
            t = trace.output_text(st) or ""
            for u in us:
                out.append({"seq": int(st.seq), "url": u, "text": t, "source": "step_url"})
    for e in rec.events():
        if e.get("type") == "source_fetch" and e.get("url") and not e.get("tls"):
            t = _blob(rec, e.get("sha256"))
            if t is not None:
                out.append({"seq": int(e["seq"]), "url": e["url"], "text": t, "source": "egress"})
    return out


# ---------------------------------------------------------------------------------------------
# 2026-11-28 量具修正（附錄 B 補充；診斷 ~/dev/ops/diag_c0_flags_20261128/DIAG.md）。預設 "literal"＝舊行為（探索批次可重現）。
# "n2db"：(a) 出口紀錄的頁面內容被自動 gc 刪掉時，按 sha256 從這一格 revision 0 的凍結頁補回（sha256 必須相同）；
#         (b) 值與頁面純文字兩邊都去掉空白、`*`、反引號、`_` 後做子字串比對（長度 ≥2），且命中處前後不能緊接數字（數字邊界）。
# 規則在跑回歸之前凍結；不參考答案鍵或任何臂的結果。
FLAG_MATCHING = "literal"
FROZEN_FALLBACK: dict[str, str] = {}
_N2 = re.compile(r"[\s*`_]+")


def set_flag_matching(mode: str) -> None:
    global FLAG_MATCHING
    if mode not in ("literal", "n2db"):
        raise ValueError(f"unknown flag_matching {mode!r}")
    FLAG_MATCHING = mode


def add_frozen_fallback(site_frozen_dir: pathlib.Path, sha_json: pathlib.Path) -> dict[str, int]:
    """把一格 revision 0 凍結頁（sha256 與 site_snapshot_sha256.json 相同者）加進補回表；回傳 {pages, mismatched}。"""
    import hashlib as _h
    pinned = json.loads(pathlib.Path(sha_json).read_text(encoding="utf-8"))
    ok = bad = 0
    for name, sha in pinned.items():
        f = pathlib.Path(site_frozen_dir) / name
        try:
            b = f.read_bytes()
        except OSError:
            bad += 1; continue
        if _h.sha256(b).hexdigest() != sha:
            bad += 1; continue
        FROZEN_FALLBACK[sha] = b.decode("utf-8", "replace"); ok += 1
    return {"pages": ok, "mismatched": bad}


def _blob(rec: Recorder, sha: str | None) -> str | None:
    t = S._blob_text(rec, sha)
    if t is None and FLAG_MATCHING == "n2db" and sha:
        return FROZEN_FALLBACK.get(sha)
    return t


def _n2(s: str) -> str:
    return _N2.sub("", s or "")


def n2db_contains(plain_n2: str, value: str) -> bool:
    k = _n2(value)
    if len(k) < 2:
        return False
    start = 0
    while True:
        i = plain_n2.find(k, start)
        if i < 0:
            return False
        before = plain_n2[i - 1] if i > 0 else ""
        after = plain_n2[i + len(k)] if i + len(k) < len(plain_n2) else ""
        if not ((k[0].isdigit() and before.isdigit()) or (k[-1].isdigit() and after.isdigit())):
            return True
        start = i + 1


def egress_fetched_urls(rec: Recorder, *, bound_seq: int | None = None) -> list[str]:
    """Sorted unique HTTP URLs actually fetched by the agent according to its own egress log."""
    urls: set[str] = set()
    for e in rec.events():
        if e.get("type") != "source_fetch":
            continue
        if bound_seq is not None and int(e.get("seq") or 0) > bound_seq:
            continue
        url = e.get("url")
        if url and not e.get("tls") and _blob(rec, e.get("sha256")) is not None:
            urls.add(str(url))
    return sorted(urls)


def compute_line_flags(
    report_text: str,
    claims: Sequence[Mapping[str, Any]],
    universe: Sequence[Mapping[str, Any]],
    *,
    round_idx: int = 0,
    prev_values: Mapping[str, str | None] | None = None,
    prev_bound_seq: int = 0,
    cur_bound_seq: int | None = None,
    fetched_urls: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Compute per-line F1/F3 flags strictly from records (no ground truth, no model judge).

    Definitions (matching exp1_flags amend1 + Experiment T spec):
      - F1: no value (`missing value`), OR value not found in any fetched content up to
            `cur_bound_seq` using `vacant_network.trace.sources.plain_contains`
            (`value not in any fetched page`).
      - F3: in revision rounds (`round_idx >= 1`), line value changed from `prev_values`
            (`pv is not None and v is not None and pv != v`) in a round that fetched NO
            source (`len(round_fetches) == 0`) (`changed without reading a source`).
    """
    if cur_bound_seq is None:
        uk = list(universe)
    else:
        uk = [u for u in universe if int(u["seq"]) <= cur_bound_seq]

    if round_idx >= 1:
        round_fetches = [u for u in uk if int(u["seq"]) > prev_bound_seq]
    else:
        round_fetches = list(uk)

    parsed = parse_report_lines(report_text, claims)
    values = {cid: info["value"] for cid, info in parsed.items()}
    flags_by_claim: dict[str, dict[str, Any]] = {}
    flagged: list[dict[str, Any]] = []

    for c in claims:
        cid = str(c["id"])
        lab = claim_label(c)
        info = parsed[cid]
        v = info["value"]
        line_no = info["line"]
        pv = prev_values.get(cid) if prev_values is not None else None

        f1 = False
        f3 = False
        reasons: list[str] = []

        if v is None:
            f1 = True
            reasons.append(PROBLEM_MISSING)
        else:
            carriers = [u for u in uk if S.plain_contains(str(u.get("text") or ""), v)]
            if not carriers and FLAG_MATCHING == "n2db":
                for u in uk:
                    if "_n2plain" not in u:
                        u["_n2plain"] = _n2(S._plain(str(u.get("text") or "")))
                    if n2db_contains(u["_n2plain"], v):
                        carriers.append(u)
            if not carriers:
                f1 = True
                reasons.append(PROBLEM_NOT_IN_FETCHED)
            if round_idx >= 1 and prev_values is not None and pv is not None and pv != v:
                if not round_fetches:
                    f3 = True
                    reasons.append(PROBLEM_CHANGED_NO_SOURCE)

        is_flagged = f1 or f3
        problem_kind = "; ".join(reasons) if reasons else None
        entry = {
            "claim_id": cid,
            "label": lab,
            "line": line_no,
            "value": v,
            "prev_value": pv,
            "is_blank": v is None,
            "F1": f1,
            "F3": f3,
            "flagged": is_flagged,
            "reasons": reasons,
            "problem_kind": problem_kind,
        }
        flags_by_claim[cid] = entry
        if is_flagged:
            flagged.append(entry)

    if fetched_urls is None:
        egress_only = sorted({str(u["url"]) for u in uk if u.get("source") == "egress" and u.get("url")})
        all_urls = egress_only if egress_only else sorted({str(u["url"]) for u in uk if u.get("url")})
    else:
        all_urls = sorted(dict.fromkeys(str(u) for u in fetched_urls if u))

    return {
        "round": int(round_idx),
        "values": values,
        "flags_by_claim": flags_by_claim,
        "flagged": flagged,
        "flagged_ids": [item["claim_id"] for item in flagged],
        "flagged_count": len(flagged),
        "blank_count": sum(1 for item in flags_by_claim.values() if item["is_blank"]),
        "supported_count": sum(1 for item in flags_by_claim.values() if not item["flagged"]),
        "fetched_urls": all_urls,
        "round_fetch_count": len(round_fetches),
        "prev_bound_seq": int(prev_bound_seq),
        "cur_bound_seq": int(cur_bound_seq) if cur_bound_seq is not None else None,
    }


def compute_flags_from_recorder(
    rec: Recorder,
    report_text: str,
    claims: Sequence[Mapping[str, Any]],
    *,
    round_idx: int = 0,
    prev_values: Mapping[str, str | None] | None = None,
    prev_bound_seq: int = 0,
    cur_bound_seq: int | None = None,
    ingest_egress: bool = True,
) -> dict[str, Any]:
    """Ingest egress log into `rec` (if requested) and compute record-only F1/F3 flags."""
    if ingest_egress:
        S.ingest_egress(rec)
    universe = fetch_universe(rec)
    evts = rec.events()
    if cur_bound_seq is None:
        cur_bound_seq = max((int(e.get("seq") or 0) for e in evts), default=0)
    urls = egress_fetched_urls(rec, bound_seq=cur_bound_seq)
    return compute_line_flags(
        report_text,
        claims,
        universe,
        round_idx=round_idx,
        prev_values=prev_values,
        prev_bound_seq=prev_bound_seq,
        cur_bound_seq=cur_bound_seq,
        fetched_urls=urls,
    )


def compute_blank_flags(
    report_text: str,
    claims: Sequence[Mapping[str, Any]],
    *,
    round_idx: int = 0,
) -> dict[str, Any]:
    """Arm TB flagger: ONLY lines with no value (zero record access, zero truth access)."""
    parsed = parse_report_lines(report_text, claims)
    values = {cid: info["value"] for cid, info in parsed.items()}
    flags_by_claim: dict[str, dict[str, Any]] = {}
    flagged: list[dict[str, Any]] = []
    for c in claims:
        cid = str(c["id"])
        lab = claim_label(c)
        info = parsed[cid]
        v = info["value"]
        is_blank = v is None
        reasons = [PROBLEM_MISSING] if is_blank else []
        entry = {
            "claim_id": cid,
            "label": lab,
            "line": info["line"],
            "value": v,
            "is_blank": is_blank,
            "F1": is_blank,
            "F3": False,
            "flagged": is_blank,
            "reasons": reasons,
            "problem_kind": PROBLEM_MISSING if is_blank else None,
        }
        flags_by_claim[cid] = entry
        if is_blank:
            flagged.append(entry)
    return {
        "round": int(round_idx),
        "values": values,
        "flags_by_claim": flags_by_claim,
        "flagged": flagged,
        "flagged_ids": [item["claim_id"] for item in flagged],
        "flagged_count": len(flagged),
        "fetched_urls": [],
    }


def compute_oracle_flags(
    report_text: str,
    claims: Sequence[Mapping[str, Any]],
    truth_c0: Mapping[str, str],
    *,
    round_idx: int = 0,
) -> dict[str, Any]:
    """Arm TO (oracle upper bound) flagger: lines that are actually wrong per audited cycle-0 truth
    (strict canonical comparison — catches missing, fabricated, wrong_read, stale).

    NEVER stores or returns any truth value in the flag report.
    """
    parsed = parse_report_lines(report_text, claims)
    values = {cid: info["value"] for cid, info in parsed.items()}
    flags_by_claim: dict[str, dict[str, Any]] = {}
    flagged: list[dict[str, Any]] = []
    for c in claims:
        cid = str(c["id"])
        lab = claim_label(c)
        info = parsed[cid]
        v = info["value"]
        cv = canon_strict(v)
        ct = canon_strict(truth_c0.get(cid))
        is_wrong = (cv is None) or (cv != ct)
        reasons = [PROBLEM_ORACLE_WRONG] if is_wrong else []
        entry = {
            "claim_id": cid,
            "label": lab,
            "line": info["line"],
            "value": v,
            "is_blank": v is None,
            "F1": False,
            "F3": False,
            "flagged": is_wrong,
            "reasons": reasons,
            "problem_kind": PROBLEM_ORACLE_WRONG if is_wrong else None,
        }
        flags_by_claim[cid] = entry
        if is_wrong:
            flagged.append(entry)
    return {
        "round": int(round_idx),
        "values": values,
        "flags_by_claim": flags_by_claim,
        "flagged": flagged,
        "flagged_ids": [item["claim_id"] for item in flagged],
        "flagged_count": len(flagged),
        "fetched_urls": [],
        "oracle": True,
    }


# =============================================================================
# Agent-Facing Feedback Renderers (Reusing `vacant_network.trace.review`)
# =============================================================================


def _render_T_item_lines(item: Mapping[str, Any], report_path: str) -> list[str]:
    """Render one flagged item for arm T using `review.line_for` for unsourced and KS-1 templates for (a)/(b)."""
    line_no = item.get("line")
    label = str(item.get("label") or item.get("claim_id") or "")
    reasons = list(item.get("reasons") or [])
    if not reasons and item.get("problem_kind"):
        reasons = [x.strip() for x in str(item["problem_kind"]).split(";") if x.strip()]

    out: list[str] = []
    for r in reasons:
        if r == PROBLEM_MISSING:
            if line_no is not None:
                out.append(NO_VALUE_LINE_TEMPLATE.format(path=report_path, n=int(line_no)))
            else:
                out.append(NO_VALUE_DELETED_TEMPLATE.format(path=report_path, label=label))
        elif r == PROBLEM_NOT_IN_FETCHED:
            # Reuse `vacant_network.trace.review.line_for` verbatim for unsourced values!
            finding = {
                "kind": "unsourced",
                "path": report_path,
                "line": int(line_no) if line_no is not None else 1,
                "value": str(item.get("value") or ""),
            }
            out.append(REV.line_for(finding))
        elif r == PROBLEM_CHANGED_NO_SOURCE:
            if line_no is not None:
                out.append(CHANGED_NO_SOURCE_LINE_TEMPLATE.format(path=report_path, n=int(line_no)))
            else:
                out.append(CHANGED_NO_SOURCE_DELETED_TEMPLATE.format(path=report_path, label=label))
    return out


def render_T_feedback(
    flagged: Sequence[Mapping[str, Any]],
    fetched_urls: Sequence[str],
    *,
    report_path: str = "report.md",
    actor_tokens: set[str] | None = None,
) -> tuple[str | None, int]:
    """Render arm T feedback reusing `vacant_network.trace.review` wording.

    Returns `(message, withheld_count)`. Returns `(None, 0)` when `flagged` is empty.
    Lines failing `feedback_ks1_clean` are replaced with `review.WITHHELD` and counted.
    """
    if not flagged:
        return None, 0
    toks = set(actor_tokens or ())
    body: list[str] = []
    withheld = 0
    for item in flagged:
        for raw_ln in _render_T_item_lines(item, report_path):
            clean_ln, w = _sanitize_line(raw_ln, toks)
            body.append(clean_ln)
            withheld += w

    uniq_urls = sorted(dict.fromkeys(str(u) for u in fetched_urls if u))
    tail: list[str] = [""]
    if uniq_urls:
        tail.append(T_FETCHED_HEADER)
        for u in uniq_urls:
            clean_ln, w = _sanitize_line(f"- {u}", toks)
            tail.append(clean_ln)
            withheld += w
    else:
        tail.append(T_FETCHED_NONE)

    msg = "\n".join([REV.REVIEW_HEADER, REV.PERSONA, *body, *tail, REV.FOOTER])
    return msg, withheld


def render_TB_feedback(
    flagged: Sequence[Mapping[str, Any]],
    *,
    report_path: str = "report.md",
    actor_tokens: set[str] | None = None,
) -> tuple[str | None, int]:
    """Render arm TB (blank-only) feedback using template (a), no record info, no fetched URLs."""
    if not flagged:
        return None, 0
    toks = set(actor_tokens or ())
    body: list[str] = []
    withheld = 0
    for item in flagged:
        line_no = item.get("line")
        label = str(item.get("label") or item.get("claim_id") or "")
        if line_no is not None:
            raw_ln = NO_VALUE_LINE_TEMPLATE.format(path=report_path, n=int(line_no))
        else:
            raw_ln = NO_VALUE_DELETED_TEMPLATE.format(path=report_path, label=label)
        clean_ln, w = _sanitize_line(raw_ln, toks)
        body.append(clean_ln)
        withheld += w
    msg = "\n".join([REPORT_REVIEW_HEADER, REV.PERSONA, *body, TB_FOOTER])
    return msg, withheld


def render_TO_feedback(
    flagged: Sequence[Mapping[str, Any]],
    *,
    report_path: str = "report.md",
    actor_tokens: set[str] | None = None,
) -> tuple[str | None, int]:
    """Render arm TO (oracle upper bound) feedback: line ids + neutral wording, NEVER the correct value."""
    if not flagged:
        return None, 0
    toks = set(actor_tokens or ())
    body: list[str] = []
    withheld = 0
    for item in flagged:
        line_no = item.get("line")
        label = str(item.get("label") or item.get("claim_id") or "")
        if line_no is not None:
            raw_ln = ORACLE_WRONG_LINE_TEMPLATE.format(path=report_path, n=int(line_no))
        else:
            raw_ln = ORACLE_WRONG_DELETED_TEMPLATE.format(path=report_path, label=label)
        clean_ln, w = _sanitize_line(raw_ln, toks)
        body.append(clean_ln)
        withheld += w
    msg = "\n".join([REPORT_REVIEW_HEADER, REV.PERSONA, *body, TO_FOOTER])
    return msg, withheld


def render_G_feedback(*, actor_tokens: set[str] | None = None) -> tuple[str, int]:
    """Render yoked arm G fixed generic review prompt (KS-1 clean, zero record info)."""
    clean_ln, w = _sanitize_line(GENERIC_REVIEW_PROMPT, set(actor_tokens or ()))
    return clean_ln, w


def render_T0_feedback(
    flagged: Sequence[Mapping[str, Any]],
    *,
    actor_tokens: set[str] | None = None,
) -> tuple[str | None, int]:
    """Legacy unused T0 count-only feedback (kept trivial/unused, KS-1 checked)."""
    n = len(flagged)
    if n == 0:
        return None, 0
    raw = T0_FEEDBACK_TEMPLATE.format(n=n)
    clean_ln, w = _sanitize_line(raw, set(actor_tokens or ()))
    return clean_ln, w


def render_arm_feedback(
    arm: str,
    flag_report: Mapping[str, Any] | None = None,
    *,
    report_path: str = "report.md",
    actor_tokens: set[str] | None = None,
) -> tuple[str | None, int]:
    """Dispatch feedback rendering by arm ('A', 'G', 'T', 'TB', 'TO'; legacy 'T0')."""
    if arm == "A":
        return None, 0
    if arm == "G":
        return render_G_feedback(actor_tokens=actor_tokens)
    if arm == "T":
        assert flag_report is not None
        return render_T_feedback(
            flag_report["flagged"],
            flag_report.get("fetched_urls") or [],
            report_path=report_path,
            actor_tokens=actor_tokens,
        )
    if arm == "TB":
        assert flag_report is not None
        return render_TB_feedback(
            flag_report["flagged"],
            report_path=report_path,
            actor_tokens=actor_tokens,
        )
    if arm == "TO":
        assert flag_report is not None
        return render_TO_feedback(
            flag_report["flagged"],
            report_path=report_path,
            actor_tokens=actor_tokens,
        )
    if arm == "T0":
        assert flag_report is not None
        return render_T0_feedback(flag_report["flagged"], actor_tokens=actor_tokens)
    raise ValueError(f"unsupported feedback arm: {arm!r}")


# Convenience string-only wrappers
def build_G_feedback(*, actor_tokens: set[str] | None = None) -> str:
    return render_G_feedback(actor_tokens=actor_tokens)[0]


def build_T_feedback(
    flagged: Sequence[Mapping[str, Any]],
    fetched_urls: Sequence[str],
    *,
    report_path: str = "report.md",
    actor_tokens: set[str] | None = None,
) -> str | None:
    return render_T_feedback(flagged, fetched_urls, report_path=report_path, actor_tokens=actor_tokens)[0]


def build_TB_feedback(
    flagged: Sequence[Mapping[str, Any]],
    *,
    report_path: str = "report.md",
    actor_tokens: set[str] | None = None,
) -> str | None:
    return render_TB_feedback(flagged, report_path=report_path, actor_tokens=actor_tokens)[0]


def build_TO_feedback(
    flagged: Sequence[Mapping[str, Any]],
    *,
    report_path: str = "report.md",
    actor_tokens: set[str] | None = None,
) -> str | None:
    return render_TO_feedback(flagged, report_path=report_path, actor_tokens=actor_tokens)[0]


def build_T0_feedback(
    flagged: Sequence[Mapping[str, Any]],
    *,
    actor_tokens: set[str] | None = None,
) -> str | None:
    return render_T0_feedback(flagged, actor_tokens=actor_tokens)[0]


def build_arm_feedback(
    arm: str,
    flag_report: Mapping[str, Any] | None = None,
    *,
    report_path: str = "report.md",
    actor_tokens: set[str] | None = None,
) -> str | None:
    return render_arm_feedback(arm, flag_report, report_path=report_path, actor_tokens=actor_tokens)[0]


# =============================================================================
# Host-Side Claude Haiku Escalation (Arms TE & TER)
# =============================================================================


def select_TER_claims(
    claims: Sequence[Mapping[str, Any]],
    k: int,
    *,
    seed: int,
    set_id: str,
    rep: int,
) -> tuple[list[dict[str, Any]], int]:
    """Deterministically sample `k` claims uniformly at random for arm TER (preserving claim order)."""
    n = len(claims)
    k_clamped = max(0, min(int(k), n))
    digest = hashlib.sha256(f"{seed}:{set_id}:r{rep}:TER".encode("utf-8")).hexdigest()
    derived_seed = int(digest[:16], 16)
    if k_clamped == 0:
        return [], derived_seed
    rng = random.Random(derived_seed)
    chosen_idxs = set(rng.sample(range(n), k_clamped))
    return [dict(claims[i]) for i in range(n) if i in chosen_idxs], derived_seed


def html_to_clean_text(raw: str, *, max_chars: int = 80_000) -> str:
    """Convert a frozen HTML page to compact, readable plain text preserving rows & values."""
    t = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw or "")
    t = re.sub(r"(?is)</(?:tr|p|div|li|h[1-6]|section|article|table|blockquote)>|<br\s*/?>", "\n", t)
    t = re.sub(r"(?is)</(?:td|th)>", " | ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = _html.unescape(t)
    out_lines: list[str] = []
    for ln in t.splitlines():
        s = " ".join(ln.split()).strip(" |")
        if s:
            out_lines.append(s)
    res = "\n".join(out_lines)
    if len(res) > max_chars:
        res = res[:max_chars] + "\n...[truncated]"
    return res


def load_frozen_fetched_pages(
    fetched_urls: Sequence[str],
    frozen_site_dir: pathlib.Path,
    *,
    rec: Recorder | None = None,
) -> list[dict[str, Any]]:
    """Load texts of ONLY the pages actually fetched in this cell's egress log, from the frozen
    revision-0 snapshot directory (falling back to egress blob text only if path not in site dir).
    """
    uniq_urls = sorted(dict.fromkeys(str(u) for u in fetched_urls if u))
    egress_by_url: dict[str, str] = {}
    if rec is not None:
        for e in rec.events():
            if e.get("type") == "source_fetch" and e.get("url") and not e.get("tls"):
                txt = S._blob_text(rec, e.get("sha256"))
                if txt is not None:
                    egress_by_url[str(e["url"])] = txt

    pages: list[dict[str, Any]] = []
    root_res = frozen_site_dir.resolve()
    for url in uniq_urls:
        # Extract path from http://host/path
        parts = url.split("/", 3)
        rel = (parts[3].split("?", 1)[0] if len(parts) >= 4 else "").lstrip("/") or "index.html"
        fpath = (root_res / rel).resolve()
        raw_bytes: bytes | None = None
        source = "frozen_snapshot"
        if str(fpath).startswith(str(root_res) + os.sep) and fpath.is_file():
            raw_bytes = fpath.read_bytes()
        elif url in egress_by_url:
            raw_bytes = egress_by_url[url].encode("utf-8", errors="replace")
            source = "egress_blob"
        if raw_bytes is None:
            continue
        raw_text = raw_bytes.decode("utf-8", errors="replace")
        pages.append({
            "url": url,
            "path": rel,
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "source": source,
            "text": html_to_clean_text(raw_text),
        })
    return pages


def build_haiku_escalation_prompt(
    target_claims: Sequence[Mapping[str, Any]],
    values: Mapping[str, str | None],
    fetched_pages: Sequence[Mapping[str, Any]],
    *,
    actor_tokens: set[str] | None = None,
) -> tuple[str, str, int]:
    """Construct `(system_prompt, user_prompt, withheld)` for TE/TER host-side Haiku escalation.

    All template text is KS-1 clean; target lines are also checked through `feedback_ks1_clean`.
    """
    toks = set(actor_tokens or ())
    withheld = 0
    item_lines: list[str] = []
    for c in target_claims:
        cid = str(c.get("claim_id") or c.get("id"))
        lab = str(c.get("label") or claim_label(c))
        if c.get("entity") and c.get("label") and "—" not in lab:
            lab = claim_label(c)
        val = values.get(cid)
        if val is not None and str(val).strip():
            raw_ln = HAIKU_LINE_WITH_VALUE_TEMPLATE.format(claim_id=cid, label=lab, value=str(val).strip())
        else:
            raw_ln = HAIKU_LINE_NO_VALUE_TEMPLATE.format(claim_id=cid, label=lab)
        clean_ln, w = _sanitize_line(raw_ln, toks)
        item_lines.append(clean_ln)
        withheld += w
    lines_block = "\n".join(item_lines)

    if fetched_pages:
        page_blocks: list[str] = []
        for pg in fetched_pages:
            page_blocks.append(f"=== PAGE: {pg['url']} ===\n{pg['text']}")
        pages_block = "\n\n".join(page_blocks)
    else:
        pages_block = "(none — no pages were fetched in this task)"

    system_prompt = assert_ks1_clean(HAIKU_ESCALATION_SYSTEM_PROMPT, toks)
    user_prompt = HAIKU_ESCALATION_USER_TEMPLATE.format(lines_block=lines_block, pages_block=pages_block)
    return system_prompt, user_prompt, withheld


_HAIKU_RESP_LINE_RE = re.compile(r"^\s*(?:[-*]\s*)?\[([A-Za-z0-9_-]+)\]\s*:\s*(.*)$")


def parse_haiku_escalation_response(
    response_text: str,
    target_claim_ids: Sequence[str],
) -> dict[str, str | None]:
    """Parse `[CLAIM_ID]: <value>` lines strictly for `target_claim_ids`.

    Returns dict mapping each target `claim_id` to extracted value string or `None`
    when marked `not found in sources` / empty / omitted.
    """
    allowed = set(str(cid) for cid in target_claim_ids)
    out: dict[str, str | None] = {str(cid): None for cid in target_claim_ids}
    for ln in (response_text or "").splitlines():
        m = _HAIKU_RESP_LINE_RE.match(ln)
        if not m:
            continue
        cid = m.group(1).strip()
        if cid not in allowed:
            continue
        val = m.group(2).strip().strip("`")
        low = val.lower().strip(" .")
        if not low or low in _NO_VALUE_MARKERS or "not found in source" in low:
            out[cid] = None
        else:
            out[cid] = val
    return out


def apply_haiku_replacements(
    report_text: str,
    claims: Sequence[Mapping[str, Any]],
    target_claim_ids: Sequence[str],
    extracted: Mapping[str, str | None],
) -> str:
    """Replace ONLY the escalated claim lines in `report_text`; leave all other lines untouched."""
    target_set = set(str(cid) for cid in target_claim_ids)
    if not target_set:
        return report_text

    by_prefix: list[tuple[str, str, str]] = []
    for c in claims:
        cid = str(c["id"])
        if cid not in target_set:
            continue
        tpl = str(c["template_line"])
        prefix = tpl if tpl.endswith(" ") else (tpl.rstrip() + " ")
        key = tpl.rstrip().rstrip(":").rstrip()
        by_prefix.append((cid, key, prefix))

    lines = report_text.splitlines()
    seen: set[str] = set()
    out_lines: list[str] = []
    for ln in lines:
        replaced = False
        stripped = ln.strip()
        for cid, key, prefix in by_prefix:
            if cid not in seen and stripped.startswith(key):
                val = extracted.get(cid)
                rendered_val = val if (val is not None and str(val).strip()) else "not found in sources"
                out_lines.append(f"{prefix}{rendered_val}")
                seen.add(cid)
                replaced = True
                break
        if not replaced:
            out_lines.append(ln)

    # Restore any escalated claim line that had been deleted from report.md
    for cid, _key, prefix in by_prefix:
        if cid not in seen:
            val = extracted.get(cid)
            rendered_val = val if (val is not None and str(val).strip()) else "not found in sources"
            out_lines.append(f"{prefix}{rendered_val}")

    trailing = "\n" if report_text.endswith("\n") or not report_text else ""
    return "\n".join(out_lines) + trailing


def estimate_haiku_cost_usd(
    input_tokens: int,
    output_tokens: int,
    *,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    price_per_mtok_in: float = DEFAULT_HAIKU_PRICE_PER_MTOK_IN,
    price_per_mtok_out: float = DEFAULT_HAIKU_PRICE_PER_MTOK_OUT,
    price_per_mtok_cache_write: float = DEFAULT_HAIKU_PRICE_PER_MTOK_CACHE_WRITE,
    price_per_mtok_cache_read: float = DEFAULT_HAIKU_PRICE_PER_MTOK_CACHE_READ,
) -> float:
    usd = (
        (max(0, int(input_tokens)) / 1_000_000.0) * float(price_per_mtok_in)
        + (max(0, int(output_tokens)) / 1_000_000.0) * float(price_per_mtok_out)
        + (max(0, int(cache_creation_input_tokens)) / 1_000_000.0) * float(price_per_mtok_cache_write)
        + (max(0, int(cache_read_input_tokens)) / 1_000_000.0) * float(price_per_mtok_cache_read)
    )
    return round(usd, 6)


def call_haiku_messages_api(
    *,
    system_prompt: str,
    user_prompt: str,
    model: str = DEFAULT_HAIKU_MODEL,
    api_url: str = DEFAULT_ANTHROPIC_API_URL,
    max_tokens: int = 1024,
    timeout_s: float = 120.0,
    price_per_mtok_in: float = DEFAULT_HAIKU_PRICE_PER_MTOK_IN,
    price_per_mtok_out: float = DEFAULT_HAIKU_PRICE_PER_MTOK_OUT,
) -> dict[str, Any]:
    """Host-side Anthropic Messages API call for TE/TER.

    Reads `ANTHROPIC_API_KEY` ONLY from `os.environ` at call time. Never writes, returns,
    or logs the key anywhere. Uses direct `urllib.request` with empty `ProxyHandler({})` so
    it bypasses local agent proxies.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")

    body_obj = {
        "model": str(model),
        "max_tokens": int(max_tokens),
        # 不送 temperature：claude-haiku-5-5 的 API 回 400「`temperature` is deprecated」（11-27 實跑）。
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    req_bytes = json.dumps(body_obj, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        str(api_url),
        data=req_bytes,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    t0 = time.time()
    try:
        with opener.open(req, timeout=float(timeout_s)) as resp:
            raw_resp = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        err_snippet = ""
        try:
            err_snippet = exc.read(400).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
        raise RuntimeError(f"Anthropic API HTTP {exc.code}: {err_snippet}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Anthropic API connection error: {exc.reason}") from None
    wall_s = round(time.time() - t0, 3)

    data = json.loads(raw_resp)
    blocks = data.get("content") or []
    text_parts = [
        str(b.get("text") or "")
        for b in blocks
        if isinstance(b, dict) and b.get("type") == "text"
    ]
    response_text = "\n".join(text_parts).strip()

    usage = data.get("usage") or {}
    in_tok = int(usage.get("input_tokens") or 0)
    out_tok = int(usage.get("output_tokens") or 0)
    cache_create = int(usage.get("cache_creation_input_tokens") or 0)
    cache_read = int(usage.get("cache_read_input_tokens") or 0)
    cost_usd = estimate_haiku_cost_usd(
        in_tok,
        out_tok,
        cache_creation_input_tokens=cache_create,
        cache_read_input_tokens=cache_read,
        price_per_mtok_in=price_per_mtok_in,
        price_per_mtok_out=price_per_mtok_out,
    )

    full_prompt_text = f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{user_prompt}\n"
    return {
        "model": str(data.get("model") or model),
        "stop_reason": data.get("stop_reason"),
        "text": response_text,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cache_creation_input_tokens": cache_create,
        "cache_read_input_tokens": cache_read,
        "cost_usd": cost_usd,
        "wall_s": wall_s,
        "prompt_text": full_prompt_text,
        "prompt_sha256": hashlib.sha256(full_prompt_text.encode("utf-8")).hexdigest(),
        "response_sha256": hashlib.sha256(response_text.encode("utf-8")).hexdigest(),
    }


def default_credit_ledger_path() -> pathlib.Path:
    """Default `$HOME/dev/ops/ctl/api_credit_ledger.jsonl` without hardcoding any username."""
    return pathlib.Path.home() / "dev" / "ops" / "ctl" / "api_credit_ledger.jsonl"


def append_credit_ledger(
    ledger_path: pathlib.Path | str | None,
    *,
    purpose: str = "expT TE/TER",
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    cell: str,
    ts: str | None = None,
) -> dict[str, Any]:
    """Append one credit-ledger JSONL entry under an exclusive file lock (never includes API key)."""
    path = pathlib.Path(os.path.expandvars(os.path.expanduser(str(ledger_path)))) if ledger_path else default_credit_ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": ts or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": str(purpose),
        "model": str(model),
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "cost_usd": round(float(cost_usd), 6),
        "cell": str(cell),
    }
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    return entry


# =============================================================================
# Signed Logbook Chain & Reconstruct Helper
# =============================================================================


def make_trigger_evidence(
    arm: str,
    round_idx: int,
    flag_report: Mapping[str, Any] | None = None,
    *,
    yoked_info: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build compact, deterministic triggering-evidence dict for the signed logbook event."""
    if arm == "G":
        out: dict[str, Any] = {
            "round": int(round_idx),
            "flag_set": [],
            "flagged_ids": [],
            "flagged_count": 0,
            "fetched_urls": [],
            "record_based": False,
        }
        if yoked_info:
            out["yoked"] = dict(yoked_info)
        return out
    fr = flag_report or {}
    flagged = [
        {
            "claim_id": str(item["claim_id"]),
            "label": str(item["label"]),
            "line": item.get("line"),
            "F1": bool(item.get("F1")),
            "F3": bool(item.get("F3")),
            "reasons": list(item.get("reasons") or []),
            "problem_kind": item.get("problem_kind"),
        }
        for item in (fr.get("flagged") or [])
    ]
    return {
        "round": int(round_idx),
        "flag_set": flagged,
        "flagged_ids": [x["claim_id"] for x in flagged],
        "flagged_count": len(flagged),
        "fetched_urls": list(fr.get("fetched_urls") or []),
        "round_fetch_count": fr.get("round_fetch_count"),
        "prev_bound_seq": fr.get("prev_bound_seq"),
        "cur_bound_seq": fr.get("cur_bound_seq"),
        "record_based": arm in ("T", "TE"),
        "oracle": arm == "TO",
    }


def feedback_event(
    logbook: Any,
    identity: Any,
    *,
    arm: str,
    round_idx: int,
    decision: str,
    feedback_text: str | None,
    evidence: Mapping[str, Any],
    withheld: int = 0,
    ts_ms: int | None = None,
    extra: Mapping[str, Any] | None = None,
) -> Any:
    """Append a signed EXPT_FEEDBACK event to a `vacant_network.logbook.Logbook`."""
    from vacant_network import crypto

    ts = int(ts_ms) if ts_ms is not None else (time.time_ns() // 1_000_000)
    payload: dict[str, Any] = {
        "schema": "vacant.d2.expT.feedback/2",
        "arm": str(arm),
        "round": int(round_idx),
        "decision": str(decision),
        "feedback_text": feedback_text,
        "withheld": int(withheld),
        "evidence": dict(evidence),
        "signer": {
            "vacant_id": identity.vacant_id,
            "pub_hex": crypto.pub_to_hex(identity.pub),
        },
    }
    if extra:
        payload["extra"] = dict(extra)
    return logbook.append(EXPT_EVENT_TYPE, payload, identity, ts_ms=ts)


def escalation_event(
    logbook: Any,
    identity: Any,
    *,
    arm: str,
    decision: str,
    model: str,
    escalated_claim_ids: Sequence[str],
    fetched_urls: Sequence[str],
    prompt_sha256: str | None,
    response_sha256: str | None,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    withheld: int = 0,
    ts_ms: int | None = None,
    extra: Mapping[str, Any] | None = None,
) -> Any:
    """Append a signed EXPT_ESCALATION event (TE/TER) to a `vacant_network.logbook.Logbook`."""
    from vacant_network import crypto

    ts = int(ts_ms) if ts_ms is not None else (time.time_ns() // 1_000_000)
    payload: dict[str, Any] = {
        "schema": "vacant.d2.expT.escalation/1",
        "arm": str(arm),
        "round": 1,
        "decision": str(decision),
        "model": str(model),
        "escalated_claim_ids": [str(x) for x in escalated_claim_ids],
        "fetched_urls": [str(u) for u in fetched_urls],
        "prompt_sha256": prompt_sha256,
        "response_sha256": response_sha256,
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "cost_usd": round(float(cost_usd), 6),
        "withheld": int(withheld),
        "signer": {
            "vacant_id": identity.vacant_id,
            "pub_hex": crypto.pub_to_hex(identity.pub),
        },
    }
    if extra:
        payload["extra"] = dict(extra)
    return logbook.append(EXPT_ESCALATION_EVENT_TYPE, payload, identity, ts_ms=ts)


def save_feedback_chain(logbook: Any, identity: Any, chain_path: str | pathlib.Path) -> pathlib.Path:
    """Atomically persist an Experiment T Logbook chain and its sidecar public key JSON."""
    from vacant_network import crypto

    path = pathlib.Path(chain_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    logbook.save(path)
    pub_path = path.with_suffix(".pub.json")
    pub_doc = {
        "vacant_id": identity.vacant_id,
        "pub_hex": crypto.pub_to_hex(identity.pub),
    }
    _atomic_write_text(pub_path, json.dumps(pub_doc, ensure_ascii=False, indent=2) + "\n")
    return path


def reconstruct(
    chain_path: str | pathlib.Path,
    *,
    pub: Any = None,
    stream: Any = None,
    emit: bool = True,
) -> list[dict[str, Any]]:
    """Verify a signed Experiment T feedback/escalation chain and return/print its history.

    Raises `vacant_network.logbook.ChainError` if missing, empty, or fails Ed25519 verification.
    """
    from vacant_network.identity import PublicIdentity
    from vacant_network.logbook import ChainError, Logbook

    path = pathlib.Path(chain_path)
    if not path.is_file():
        raise ChainError(f"feedback chain not found: {path}")
    try:
        book = Logbook.load(path)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ChainError(f"failed to load feedback chain {path}: {exc}") from exc
    if not book.entries:
        raise ChainError(f"feedback chain is empty: {path}")

    who = pub
    if who is None:
        pub_path = path.with_suffix(".pub.json")
        if pub_path.is_file():
            try:
                pub_doc = json.loads(pub_path.read_text(encoding="utf-8"))
                who = PublicIdentity.from_hex(pub_doc["vacant_id"], pub_doc["pub_hex"])
            except Exception as exc:
                raise ChainError(f"invalid sidecar public key {pub_path}: {exc}") from exc
        else:
            genesis_signer = (
                book.entries[0].payload.get("signer")
                if isinstance(book.entries[0].payload, dict)
                else None
            )
            if (
                not isinstance(genesis_signer, dict)
                or "vacant_id" not in genesis_signer
                or "pub_hex" not in genesis_signer
            ):
                raise ChainError("no PublicIdentity provided and no signer metadata in chain")
            who = PublicIdentity.from_hex(genesis_signer["vacant_id"], genesis_signer["pub_hex"])

    if not book.verify_chain(who):
        raise ChainError(f"feedback chain verification failed (tampered or bad signature): {path}")

    history: list[dict[str, Any]] = []
    out_stream = stream if stream is not None else sys.stdout
    for entry in book.entries:
        if entry.type not in (EXPT_EVENT_TYPE, EXPT_ESCALATION_EVENT_TYPE) or not isinstance(entry.payload, dict):
            continue
        p = entry.payload
        if entry.type == EXPT_ESCALATION_EVENT_TYPE:
            rec = {
                "seq": entry.seq,
                "ts_ms": entry.ts_ms,
                "type": entry.type,
                "arm": p.get("arm"),
                "round": p.get("round"),
                "decision": p.get("decision"),
                "model": p.get("model"),
                "escalated_claim_ids": p.get("escalated_claim_ids") or [],
                "fetched_urls": p.get("fetched_urls") or [],
                "prompt_sha256": p.get("prompt_sha256"),
                "response_sha256": p.get("response_sha256"),
                "input_tokens": p.get("input_tokens"),
                "output_tokens": p.get("output_tokens"),
                "cost_usd": p.get("cost_usd"),
                "withheld": p.get("withheld", 0),
                "extra": p.get("extra"),
            }
            history.append(rec)
            if emit:
                print(
                    f"seq={entry.seq} arm={rec['arm']} decision={rec['decision']} "
                    f"model={rec['model']} escalated={rec['escalated_claim_ids']} "
                    f"in={rec['input_tokens']} out={rec['output_tokens']} cost_usd={rec['cost_usd']}",
                    file=out_stream,
                )
            continue

        ev = p.get("evidence") or {}
        rec = {
            "seq": entry.seq,
            "ts_ms": entry.ts_ms,
            "type": entry.type,
            "arm": p.get("arm"),
            "round": p.get("round"),
            "decision": p.get("decision"),
            "feedback_text": p.get("feedback_text"),
            "withheld": p.get("withheld", 0),
            "evidence": ev,
            "extra": p.get("extra"),
        }
        history.append(rec)
        if emit:
            fids = ev.get("flagged_ids") or [x.get("claim_id") for x in (ev.get("flag_set") or [])]
            n_urls = len(ev.get("fetched_urls") or [])
            fb_len = len(rec["feedback_text"]) if rec["feedback_text"] else 0
            print(
                f"seq={entry.seq} arm={rec['arm']} round={rec['round']} "
                f"decision={rec['decision']} flagged={fids} "
                f"fetched_urls={n_urls} feedback_chars={fb_len} withheld={rec['withheld']}",
                file=out_stream,
            )
    return history


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify Experiment T KS-1 templates or reconstruct a feedback chain.")
    sp = ap.add_subparsers(dest="cmd", required=True)
    rc = sp.add_parser("reconstruct", help="Verify and print events from a feedback_chain.ndjson")
    rc.add_argument("chain", help="Path to feedback_chain.ndjson")
    rc.add_argument("--json", action="store_true", help="Print reconstructed events as JSON")
    sp.add_parser("check-ks1", help="Run executable KS-1 check on all Experiment T templates")
    a = ap.parse_args()
    if a.cmd == "reconstruct":
        hist = reconstruct(a.chain, emit=not a.json)
        if a.json:
            print(json.dumps(hist, ensure_ascii=False, indent=2))
    elif a.cmd == "check-ks1":
        print(format_ks1_check_report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
