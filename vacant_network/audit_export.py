"""audit_export — Normalized, versioned audit record export across all Vacant sources.

Schema: `vacant-audit-record/1` (full specification in `docs/AUDIT_RECORD_V1.md`).

Sources (read-only; this module never writes to `$VACANT_HOME`, `work_root`, or run dirs):
  1. `trace`         — `$VACANT_HOME/trace/projects/*/chain.ndjson` (+ sealed volumes)
  2. `intake_ledger` — `$VACANT_HOME/intake/ledger/*.ndjson`
  3. `vrun`          — `<vrun_root>/*/receipts_*.ndjson` (+ `run_*.json`, `possess.json`,
                       `NOT_CERTIFIED.json`, `rows.jsonl`)
  4. `restart`       — signed `restart_receipt` entries in `$VACANT_HOME/trace/projects/*/chain.ndjson`
                       joined by `run_id` with `work_root()/restart-*/result.json`
                       (unsigned `result.json` is fallback only when no receipt / chain exists)
  5. `possess_wire`  — `$VACANT_POSSESS_HOME/proxyd/wire/index.jsonl` (if present)

Honest boundaries:
  - Signed records are **tamper-evident** and **re-verifiable** offline; they are never
    guaranteed to be complete.
  - Missing or unmeasured fields are always `None` (`null` in JSON) or `"unknown"` /
    `"unchecked"` — never filled with `0` or `False`.
  - Truncated, edited, unreadable, or untrusted chains are never dropped: they are emitted
    with `signature.verified = False` and the concrete failure reason.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import json
import os
import pathlib
import re
import sys
import time
import zlib
from typing import Any

from .identity import PublicIdentity
from .intake import keys as _intake_keys
from .intake.ledger import Ledger, state_of as _ledger_state_of
from .intake.statepaths import state_dir as _default_state_dir
from .intake.statepaths import work_dir as _default_work_dir
from .logbook import LogEntry, Logbook
from .trace.recorder import Recorder, _volume_bytes, _volume_num
from .vrun import verify_receipts as _vr

AUDIT_RECORD_SCHEMA = "vacant-audit-record/1"

KINDS = ("trace", "intake_ledger", "vrun", "restart", "possess_wire")

RESULTS = (
    "accepted",
    "released",
    "rejected",
    "held",
    "escalated",
    "void",
    "unchecked",
    "open",
    "withdrawn",
    "release_unconfirmed",
    "unreadable",
    "unknown",
)

_RESULT_PASSED: dict[str, bool | None] = {
    "accepted": True,
    "released": True,
    "rejected": False,
    "held": None,
    "escalated": None,
    "void": None,
    "unchecked": None,
    "open": None,
    "withdrawn": None,
    "release_unconfirmed": None,
    "unreadable": None,
    "unknown": None,
}

_RESTART_TS_RE = re.compile(r"^restart-(\d{8}T\d{6})(?:-|$)")
_DURATION_RE = re.compile(r"^(\d+(?:\.\d+)?)([smhdw])$", re.IGNORECASE)

WORDING_BOUNDARY = (
    "Records are tamper-evident and re-verifiable where signed; "
    "they are not guaranteed to be complete (unsigned sources, omitted runs, "
    "or unanchored tail truncation cannot be ruled out)."
)


# ── Helpers (type-strict: never confuse bool with int or missing with 0) ──────

def _safe_utf8_str(val: str | os.PathLike[str]) -> str:
    s = os.fspath(val)
    if not any(0xD800 <= ord(ch) <= 0xDFFF for ch in s):
        return s
    try:
        raw = os.fsencode(s)
    except UnicodeEncodeError:
        raw = s.encode("utf-8", errors="surrogatepass")
    return raw.decode("utf-8", errors="backslashreplace")


def _sanitize_utf8_obj(obj: Any) -> Any:
    if isinstance(obj, str):
        return _safe_utf8_str(obj)
    if isinstance(obj, list):
        return [_sanitize_utf8_obj(x) for x in obj]
    if isinstance(obj, tuple):
        return [_sanitize_utf8_obj(x) for x in obj]
    if isinstance(obj, dict):
        return {
            (_safe_utf8_str(k) if isinstance(k, str) else k): _sanitize_utf8_obj(v)
            for k, v in obj.items()
        }
    return obj


def _as_int(v: Any) -> int | None:
    if isinstance(v, bool) or not isinstance(v, int):
        return None
    return v


def _as_bool(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    return None


def _as_str(v: Any) -> str | None:
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None


def _read_json_file(p: pathlib.Path) -> tuple[Any, str | None]:
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"read error: {type(exc).__name__}: {exc}"
    try:
        return json.loads(raw), None
    except ValueError as exc:
        return None, f"invalid JSON: {exc}"


def _gap(code: str, severity: str, detail: str, count: int | None = None) -> dict[str, Any]:
    return {"code": code, "severity": severity, "detail": detail, "count": count}


def _send_back_item(
    *,
    action: str,
    summary: str,
    round_n: int | None = None,
    channel: str | None = None,
    details: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "round": _as_int(round_n),
        "action": action,
        "channel": channel,
        "summary": summary[:300],
        "details": [str(x)[:200] for x in (details or [])[:12]],
    }


def _agents_fields(names: set[str]) -> tuple[str | None, list[str] | None]:
    cleaned = sorted({n.strip() for n in names if isinstance(n, str) and n.strip()})
    if not cleaned:
        return None, None
    primary = cleaned[0] if len(cleaned) == 1 else ",".join(cleaned)
    return primary, cleaned


def _inspect_ndjson_entries(
    path: pathlib.Path,
) -> tuple[list[LogEntry], int, list[str]]:
    """Inspect a Logbook NDJSON file (plain or .gz) without swallowing corruption.

    Returns `(valid_entries, torn_tail_bytes, problems)`.
    """
    problems: list[str] = []
    entries: list[LogEntry] = []
    try:
        data = _volume_bytes(path)
    except (OSError, EOFError, zlib.error) as exc:
        return [], 0, [f"unreadable chain file {path.name}: {type(exc).__name__}: {exc}"]

    if not data:
        return [], 0, []

    torn = 0
    if not data.endswith(b"\n"):
        cut = data.rfind(b"\n") + 1
        torn = len(data) - cut
        problems.append(f"truncated tail in {path.name} ({torn} torn bytes without newline)")
        data = data[:cut]

    for lineno, raw_line in enumerate(data.split(b"\n"), start=1):
        if not raw_line.strip():
            continue
        try:
            obj = json.loads(raw_line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            problems.append(f"malformed JSON in {path.name} line {lineno}: {exc}")
            continue
        if not isinstance(obj, dict):
            problems.append(f"non-object JSON entry in {path.name} line {lineno}")
            continue
        try:
            entries.append(LogEntry.from_json(obj))
        except (ValueError, KeyError, TypeError) as exc:
            problems.append(f"malformed logbook entry in {path.name} line {lineno}: {exc}")
    return entries, torn, problems


def _ts_bounds_from_entries(entries: list[LogEntry]) -> tuple[int | None, int | None]:
    ts = [e.ts_ms for e in entries if _as_int(e.ts_ms) is not None]
    if not ts:
        return None, None
    return min(ts), max(ts)


def _base_record(
    *,
    record_id: str,
    kind: str,
    source_path: pathlib.Path,
    auxiliary_paths: list[pathlib.Path],
    started_at_ms: int | None,
    ended_at_ms: int | None,
    timestamp_ms: int | None,
    project: str | None,
    project_key: str | None,
    agent: str | None,
    agents: list[str] | None,
    task: str | None,
    attempts_count: int | None,
    attempts_max: int | None,
    attempts_delivered: int | None,
    result: str,
    raw_status: str | None,
    acceptance_kind: str | None,
    checks_passed: int | None,
    checks_total: int | None,
    sent_back_count: int | None,
    sent_back_items: list[dict[str, Any]] | None,
    gaps: list[dict[str, Any]],
    signature: dict[str, Any],
    details: dict[str, Any],
) -> dict[str, Any]:
    if result not in _RESULT_PASSED:
        result = "unknown"
    return _sanitize_utf8_obj({
        "schema": AUDIT_RECORD_SCHEMA,
        "record_id": record_id,
        "kind": kind,
        "source": {
            "path": _safe_utf8_str(source_path),
            "kind": kind,
            "auxiliary_paths": [_safe_utf8_str(p) for p in auxiliary_paths],
        },
        "timestamp_ms": _as_int(timestamp_ms),
        "started_at_ms": _as_int(started_at_ms),
        "ended_at_ms": _as_int(ended_at_ms),
        "project": project,
        "project_key": project_key,
        "agent": agent,
        "agents": agents,
        "task": task,
        "attempts": {
            "count": _as_int(attempts_count),
            "max": _as_int(attempts_max),
            "delivered": _as_int(attempts_delivered),
        },
        "acceptance": {
            "result": result,
            "raw_status": raw_status,
            "passed": _RESULT_PASSED[result],
            "kind": acceptance_kind,
            "checks_passed": _as_int(checks_passed),
            "checks_total": _as_int(checks_total),
        },
        "sent_back": {
            "count": _as_int(sent_back_count),
            "items": sent_back_items,
        },
        "gaps": gaps,
        "signature": signature,
        "details": details,
    })


# ── Path Resolution ───────────────────────────────────────────────────────────

def resolve_paths(
    *,
    vacant_home: pathlib.Path | str | None = None,
    work_root: pathlib.Path | str | None = None,
    vrun_dirs: list[pathlib.Path | str] | None = None,
    possess_home: pathlib.Path | str | None = None,
) -> dict[str, Any]:
    """Resolve source roots without creating any directories or files."""
    if vacant_home is not None:
        vh = pathlib.Path(vacant_home).expanduser()
    else:
        vh = _default_state_dir()

    if work_root is not None:
        wr = pathlib.Path(work_root).expanduser()
    elif vacant_home is not None and not os.environ.get("VACANT_WORK"):
        wr = vh.parent / (vh.name + "-work")
    else:
        wr = _default_work_dir()

    if possess_home is not None:
        ph = pathlib.Path(possess_home).expanduser()
    elif os.environ.get("VACANT_POSSESS_HOME"):
        ph = pathlib.Path(os.environ["VACANT_POSSESS_HOME"]).expanduser()
    else:
        ph = vh / "possess"

    vdirs: list[pathlib.Path] = []
    if vrun_dirs:
        vdirs = [pathlib.Path(d).expanduser() for d in vrun_dirs]
    elif os.environ.get("VACANT_RUN_DIR"):
        vdirs = [
            pathlib.Path(part).expanduser()
            for part in os.environ["VACANT_RUN_DIR"].split(os.pathsep)
            if part.strip()
        ]
    else:
        vdirs = [vh.parent / (vh.name + "-run")]

    return {
        "vacant_home": vh,
        "work_root": wr,
        "vrun_dirs": vdirs,
        "possess_home": ph,
    }


def _load_trust_readonly(intake_root: pathlib.Path) -> tuple[_intake_keys.Trust, str | None]:
    p = intake_root / "trust.json"
    if not p.is_file():
        return _intake_keys.Trust(p, {}), None
    try:
        return _intake_keys.Trust.load(p), None
    except (OSError, ValueError) as exc:
        return _intake_keys.Trust(p, {}), f"trust.json unreadable: {exc}"


# ── Source 2: Intake Ledger (read first so trace can cross-check anchors) ─────

def _project_from_contract_path(cpath: str | None) -> str | None:
    if not cpath:
        return None
    p = pathlib.Path(cpath)
    if p.parent.name == ".vacant":
        return str(p.parent.parent)
    return str(p.parent)


def _collect_intake_ledgers(
    vacant_home: pathlib.Path,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Read and verify all `$VACANT_HOME/intake/ledger/*.ndjson` chains.

    Also returns `{project_key: anchor_info}` for cross-checking trace chains.
    """
    intake_root = vacant_home / "intake"
    ldir = intake_root / "ledger"
    records: list[dict[str, Any]] = []
    trace_anchors: dict[str, dict[str, Any]] = {}
    if not ldir.is_dir():
        return records, trace_anchors

    trust, trust_err = _load_trust_readonly(intake_root)
    trust_path = intake_root / "trust.json"

    for p in sorted(ldir.glob("*.ndjson")):
        if not p.is_file():
            continue
        task_id = p.stem
        aux: list[pathlib.Path] = [trust_path] if trust_path.is_file() else []
        entries, torn, raw_problems = _inspect_ndjson_entries(p)
        started_ms, ended_ms = _ts_bounds_from_entries(entries)
        events = [
            {"seq": e.seq, "type": e.type, "ts_ms": e.ts_ms, **(e.payload or {})}
            for e in entries
        ]

        signer: str | None = None
        if entries and isinstance(entries[0].payload, dict):
            signer = _as_str(entries[0].payload.get("signer"))
        chain_head = entries[-1].hash() if entries else None

        gaps: list[dict[str, Any]] = []
        if trust_err:
            gaps.append(_gap("chain_unverifiable", "error", trust_err))

        # Verify signature chain
        led = Ledger(task_id, root=intake_root)
        sig_verified: bool
        sig_status: str
        sig_reason: str

        if raw_problems:
            sig_verified = False
            sig_status = "failed"
            sig_reason = "; ".join(raw_problems)
            is_trunc = torn > 0 or any("truncated" in x for x in raw_problems)
            gaps.append(
                _gap(
                    "chain_truncated" if is_trunc else "signature_failed",
                    "error",
                    sig_reason,
                )
            )
        else:
            ok, why = led.verify(trust)
            sig_verified = ok
            sig_status = "verified" if ok else "failed"
            sig_reason = why
            if not ok:
                gaps.append(_gap("signature_failed", "error", why))

        # Record external anchors for trace cross-checks
        for ev in events:
            proj_k = _as_str(ev.get("project"))
            if not proj_k:
                continue
            if ev.get("type") == "trace_head":
                cur = trace_anchors.setdefault(
                    proj_k, {"task_id": task_id, "ledger_ok": sig_verified, "ledger_reason": sig_reason}
                )
                cur["anchor"] = {"seq": ev.get("seq"), "hash": ev.get("hash")}
                cur["task_id"] = task_id
                cur["ledger_ok"] = sig_verified
                cur["ledger_reason"] = sig_reason
            elif ev.get("type") == "trace_broken":
                cur = trace_anchors.setdefault(
                    proj_k, {"task_id": task_id, "ledger_ok": sig_verified, "ledger_reason": sig_reason}
                )
                cur.setdefault("broken", []).append(
                    {"seq": ev.get("seq"), "why": ev.get("why"), "task_id": task_id}
                )

        # Extract normalized fields from whatever valid events exist
        unreadable_entirely = bool(raw_problems) and not events
        project: str | None = None
        linked_project_key: str | None = None
        agent_names: set[str] = set()
        sent_back_items: list[dict[str, Any]] | None = None if unreadable_entirely else []
        n_attempt_started = 0
        n_frozen = 0
        n_decisions = 0
        n_escapes = 0
        n_voids = 0
        n_trace_broken = 0
        n_trace_errors = 0
        has_contract_lock = False
        latest_results: list[dict[str, Any]] | None = None
        decision_round = 0

        for ev in events:
            et = ev.get("type")
            if et == "task_opened":
                cp = _as_str(ev.get("contract_path"))
                if cp:
                    project = _project_from_contract_path(cp)
            elif et == "contract_locked":
                has_contract_lock = True
            elif et == "attempt_started":
                n_attempt_started += 1
                ag = _as_str(ev.get("agent"))
                if ag:
                    agent_names.add(ag)
                ws = _as_str(ev.get("workspace"))
                if ws and project is None:
                    project = ws
            elif et == "attempt_ended":
                if ev.get("workspace_escape") is True:
                    n_escapes += 1
            elif et == "candidate_frozen":
                n_frozen += 1
                src = _as_str(ev.get("source"))
                if src and ":vacant-do:" in src:
                    agent_names.add(src.split(":vacant-do:", 1)[0])
            elif et == "decision":
                n_decisions += 1
                decision_round += 1
                oc = _as_str(ev.get("outcome"))
                res_list = ev.get("results")
                if isinstance(res_list, list):
                    latest_results = [r for r in res_list if isinstance(r, dict)]
                if oc in ("reject", "hold", "escalate") and sent_back_items is not None:
                    reasons = [str(r) for r in (ev.get("reasons") or []) if r]
                    failed_claims = [
                        f"{r.get('id')}:{r.get('status')}"
                        for r in (latest_results or [])
                        if r.get("status") != "PASS"
                    ]
                    sent_back_items.append(
                        _send_back_item(
                            action=oc,
                            round_n=decision_round,
                            channel="intake_decision",
                            summary=reasons[0] if reasons else f"decision outcome: {oc}",
                            details=reasons + failed_claims,
                        )
                    )
            elif et == "release_refused" and sent_back_items is not None:
                reasons = [str(r) for r in (ev.get("reasons") or []) if r]
                sent_back_items.append(
                    _send_back_item(
                        action="release_refused",
                        channel="release_gate",
                        summary=reasons[0] if reasons else "release refused",
                        details=reasons,
                    )
                )
            elif et == "infra_void":
                n_voids += 1
            elif et == "trace_head":
                pk = _as_str(ev.get("project"))
                if pk:
                    linked_project_key = pk
            elif et == "trace_broken":
                n_trace_broken += 1
                pk = _as_str(ev.get("project"))
                if pk:
                    linked_project_key = pk
            elif et == "trace_error":
                n_trace_errors += 1

        if unreadable_entirely:
            result = "unreadable"
            raw_status = "unreadable"
            attempts_count: int | None = None
            checks_passed: int | None = None
            checks_total: int | None = None
            gaps.append(_gap("unreadable_source", "error", sig_reason))
            st_summary: dict[str, Any] = {}
        else:
            st = _ledger_state_of(events)
            st_summary = {
                "state": st.get("state"),
                "contract_sha256": st.get("contract_sha256"),
                "latest_artifact": st.get("latest_artifact"),
                "latest_outcome": st.get("latest_outcome"),
                "decisions": st.get("decisions"),
                "void": st.get("void"),
                "released": st.get("released"),
                "destination_live": st.get("destination_live"),
                "last_event": st.get("last_event"),
            }
            raw_state = _as_str(st.get("state"))
            result = raw_state if raw_state in _RESULT_PASSED else "unknown"
            raw_status = raw_state
            if n_attempt_started > 0:
                attempts_count = n_attempt_started
            elif n_frozen > 0 or n_decisions > 0:
                attempts_count = max(n_frozen, n_decisions)
            else:
                attempts_count = 0

            if latest_results is not None and len(latest_results) > 0:
                checks_total = len(latest_results)
                checks_passed = sum(1 for r in latest_results if r.get("status") == "PASS")
            else:
                checks_passed = None
                checks_total = None

            if raw_problems:
                gaps.append(
                    _gap(
                        "unreadable_source",
                        "warning",
                        f"partially parsed ledger ({len(raw_problems)} unreadable line(s))",
                        count=len(raw_problems),
                    )
                )

        if n_escapes:
            gaps.append(
                _gap(
                    "workspace_escape",
                    "error",
                    f"agent modified original project outside workspace in {n_escapes} attempt(s)",
                    count=n_escapes,
                )
            )
        if n_voids:
            gaps.append(
                _gap(
                    "infra_void",
                    "error",
                    f"{n_voids} infra_void event(s) recorded in task ledger",
                    count=n_voids,
                )
            )
        if n_trace_broken:
            gaps.append(
                _gap(
                    "trace_broken",
                    "error",
                    f"ledger recorded {n_trace_broken} trace_broken event(s)",
                    count=n_trace_broken,
                )
            )
        if n_trace_errors:
            gaps.append(
                _gap(
                    "trace_error",
                    "warning",
                    f"ledger recorded {n_trace_errors} trace_error event(s)",
                    count=n_trace_errors,
                )
            )
        if result == "release_unconfirmed":
            gaps.append(
                _gap(
                    "release_unconfirmed",
                    "error",
                    "release was attempted but destination readback failed",
                )
            )
        if not unreadable_entirely and not has_contract_lock:
            gaps.append(
                _gap(
                    "contract_unlocked",
                    "info",
                    "no owner-signed contract_locked event in task ledger",
                )
            )
        if sig_verified:
            gaps.append(
                _gap(
                    "unanchored_chain",
                    "info",
                    "ledger verified internally without external recipient head check; "
                    "clean tail truncation cannot be detected from the ledger alone",
                )
            )

        agent, agents = _agents_fields(agent_names)
        signature = {
            "verified": sig_verified,
            "status": sig_status,
            "scheme": "ed25519_trusted_chain",
            "reason": sig_reason,
            "signer": signer,
            "entries_checked": len(entries) if entries or not raw_problems else None,
            "chain_head": chain_head,
            "anchor_checked": False,
        }

        records.append(
            _base_record(
                record_id=f"intake_ledger:{task_id}",
                kind="intake_ledger",
                source_path=p,
                auxiliary_paths=aux,
                started_at_ms=started_ms,
                ended_at_ms=ended_ms,
                timestamp_ms=ended_ms if ended_ms is not None else started_ms,
                project=project,
                project_key=linked_project_key,
                agent=agent,
                agents=agents,
                task=task_id,
                attempts_count=attempts_count,
                attempts_max=None,
                attempts_delivered=None,
                result=result,
                raw_status=raw_status,
                acceptance_kind="contract" if not unreadable_entirely else None,
                checks_passed=checks_passed,
                checks_total=checks_total,
                sent_back_count=len(sent_back_items) if sent_back_items is not None else None,
                sent_back_items=sent_back_items,
                gaps=gaps,
                signature=signature,
                details=st_summary,
            )
        )

    return records, trace_anchors


# ── Source 1: Trace Chains ────────────────────────────────────────────────────

def _sealed_volumes_in(project_dir: pathlib.Path) -> list[pathlib.Path]:
    best: dict[int, pathlib.Path] = {}
    for p in project_dir.iterdir():
        if not p.is_file():
            continue
        num = _volume_num(p.name)
        if num is None:
            continue
        cur = best.get(num)
        if cur is not None and p.name.endswith(".gz") and not cur.name.endswith(".gz"):
            continue
        best[num] = p
    return [best[k] for k in sorted(best)]


def _recorder_for_dir(
    project_dir: pathlib.Path, trace_root: pathlib.Path, workspace: str | None
) -> Recorder:
    """Build a read-only Recorder bound directly to `project_dir`."""
    rec = Recorder(workspace or str(project_dir), root=trace_root)
    rec.dir = project_dir
    rec.chain_path = project_dir / "chain.ndjson"
    rec.state_path = project_dir / "state.json"
    return rec


def _platform_from_session_key(sk: str | None) -> str | None:
    if not sk or ":" not in sk:
        return None
    plat = sk.split(":", 1)[0].strip()
    if not plat or plat in ("do", "*"):
        return None
    return plat


def _last_scan_disabled(events: list[dict[str, Any]], state: dict[str, Any]) -> str | None:
    last: str | None = None
    saw_coverage = False
    for ev in events:
        if ev.get("type") != "coverage":
            continue
        saw_coverage = True
        if ev.get("scan_disabled"):
            last = str(ev.get("scan_disabled"))
        elif ev.get("rescanned") or ev.get("baseline"):
            last = None
    if saw_coverage:
        return last
    sd = state.get("scan_disabled")
    return str(sd) if sd else None


_STRUCTURAL_TRACE_TYPES = frozenset({
    "trace_genesis",
    "restart_receipt",
    "volume_seal",
    "volume_reclaimed",
})


def _inspect_trace_projects(
    vacant_home: pathlib.Path,
    trace_anchors: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Inspect and verify all `$VACANT_HOME/trace/projects/*` chains (read-only).

    Returns `{project_key: proj_info}` shared by both `trace` and signed `restart`
    record builders so each chain is read and verified once.
    """
    trace_root = vacant_home / "trace"
    pdir = trace_root / "projects"
    intake_root = vacant_home / "intake"
    out: dict[str, dict[str, Any]] = {}
    if not pdir.is_dir():
        return out

    trust, trust_err = _load_trust_readonly(intake_root)
    trust_path = intake_root / "trust.json"

    for d in sorted(pdir.iterdir()):
        if not d.is_dir():
            continue
        key = d.name
        chain_p = d / "chain.ndjson"
        vols = _sealed_volumes_in(d)
        head_p = d / "head.json"
        state_p = d / "state.json"
        delivery_p = d / "delivery.json"
        anchor_info = trace_anchors.get(key)

        has_chain_files = chain_p.is_file() or bool(vols)
        if not has_chain_files and not head_p.is_file() and anchor_info is None:
            continue

        aux: list[pathlib.Path] = [*vols]
        for cand in (head_p, state_p, delivery_p, trust_path):
            if cand.is_file():
                aux.append(cand)

        state_obj: dict[str, Any] = {}
        if state_p.is_file():
            loaded, _err = _read_json_file(state_p)
            if isinstance(loaded, dict):
                state_obj = loaded

        delivery_obj: dict[str, Any] | None = None
        if delivery_p.is_file():
            loaded, _err = _read_json_file(delivery_p)
            if isinstance(loaded, dict):
                delivery_obj = loaded

        # Raw inspection across all volume files + active chain.ndjson
        all_chain_files = list(vols) + ([chain_p] if chain_p.is_file() else [])
        entries: list[LogEntry] = []
        total_torn = 0
        raw_problems: list[str] = []
        for fp in all_chain_files:
            file_entries, torn, probs = _inspect_ndjson_entries(fp)
            entries.extend(file_entries)
            total_torn += torn
            raw_problems.extend(probs)

        started_ms, ended_ms = _ts_bounds_from_entries(entries)
        events = [
            {"seq": e.seq, "type": e.type, "ts_ms": e.ts_ms, "hash": e.hash(), **(e.payload or {})}
            for e in entries
        ]

        workspace = _as_str(state_obj.get("workspace"))
        if workspace is None and entries and isinstance(entries[0].payload, dict):
            workspace = _as_str(entries[0].payload.get("workspace"))

        signer: str | None = None
        if entries and isinstance(entries[0].payload, dict):
            signer = _as_str(entries[0].payload.get("signer"))
        chain_head = entries[-1].hash() if entries else None

        chain_gaps: list[dict[str, Any]] = []
        if trust_err:
            chain_gaps.append(_gap("chain_unverifiable", "error", trust_err))

        # Verify chain using Recorder.verify + raw torn-line/malformed check + ledger anchor
        anchor = anchor_info.get("anchor") if anchor_info else None
        anchor_checked = bool(anchor is not None or (anchor_info and anchor_info.get("broken")))
        sig_verified: bool
        sig_status: str
        sig_reason: str
        rec = _recorder_for_dir(d, trace_root, workspace)

        if not has_chain_files:
            sig_verified = False
            sig_status = "failed"
            if anchor is not None:
                sig_reason = (
                    f"trace chain missing, but task ledger anchored entry {anchor.get('seq')} "
                    "(deleted or moved)"
                )
            else:
                sig_reason = "trace chain.ndjson missing despite head.json / anchor metadata"
            chain_gaps.append(_gap("chain_truncated", "error", sig_reason))
        elif raw_problems:
            sig_verified = False
            sig_status = "failed"
            sig_reason = "; ".join(raw_problems)
            is_trunc = total_torn > 0 or any("truncated" in x for x in raw_problems)
            chain_gaps.append(
                _gap(
                    "chain_truncated" if is_trunc else "signature_failed",
                    "error",
                    sig_reason,
                )
            )
        else:
            if anchor_info and anchor_info.get("broken"):
                b = anchor_info["broken"][0]
                sig_verified = False
                sig_status = "failed"
                sig_reason = (
                    f"task ledger recorded trace_broken at entry {b.get('seq')} ({b.get('why')})"
                )
                chain_gaps.append(_gap("trace_broken", "error", sig_reason))
            elif anchor_info and not anchor_info.get("ledger_ok"):
                sig_verified = False
                sig_status = "failed"
                sig_reason = (
                    f"anchoring task ledger does not verify ({anchor_info.get('ledger_reason')})"
                )
                chain_gaps.append(_gap("signature_failed", "error", sig_reason))
            else:
                ok, why = rec.verify(trust=trust, anchor=anchor)
                sig_verified = ok
                sig_status = "verified" if ok else "failed"
                sig_reason = why
                if not ok:
                    low = why.lower()
                    is_trunc = (
                        "truncated" in low
                        or "recorded head" in low
                        or "anchored entry" in low
                        or "missing volume" in low
                        or "initial volume missing" in low
                    )
                    chain_gaps.append(
                        _gap(
                            "chain_truncated" if is_trunc else "signature_failed",
                            "error",
                            why,
                        )
                    )

        restart_entries = [e for e in entries if e.type == "restart_receipt"]
        has_non_restart_events = any(e.type not in _STRUCTURAL_TRACE_TYPES for e in entries)
        has_state_activity = bool(
            (state_obj.get("sessions") or {})
            or (_as_int(state_obj.get("n_steps")) or 0) > 0
            or state_obj.get("scan_disabled")
        )
        has_non_restart_trace_activity = bool(
            has_non_restart_events
            or has_state_activity
            or delivery_obj is not None
            or anchor_info is not None
        )
        primary_path = chain_p if chain_p.is_file() else (vols[-1] if vols else chain_p)

        out[key] = {
            "key": key,
            "dir": d,
            "chain_path": chain_p,
            "primary_path": primary_path,
            "vols": vols,
            "aux": aux,
            "has_chain_files": has_chain_files,
            "state_obj": state_obj,
            "delivery_obj": delivery_obj,
            "anchor_info": anchor_info,
            "entries": entries,
            "events": events,
            "restart_entries": restart_entries,
            "has_non_restart_trace_activity": has_non_restart_trace_activity,
            "started_ms": started_ms,
            "ended_ms": ended_ms,
            "workspace": workspace,
            "signer": signer,
            "chain_head": chain_head,
            "raw_problems": raw_problems,
            "total_torn": total_torn,
            "chain_gaps": chain_gaps,
            "sig_verified": sig_verified,
            "sig_status": sig_status,
            "sig_reason": sig_reason,
            "anchor_checked": anchor_checked,
            "recorder": rec,
            "trust": trust,
        }

    return out


def _build_trace_record(info: dict[str, Any]) -> dict[str, Any]:
    key = info["key"]
    vols = info["vols"]
    aux = list(info["aux"])
    has_chain_files = info["has_chain_files"]
    state_obj = info["state_obj"]
    delivery_obj = info["delivery_obj"]
    anchor_info = info["anchor_info"]
    entries = info["entries"]
    events = info["events"]
    started_ms = info["started_ms"]
    ended_ms = info["ended_ms"]
    workspace = info["workspace"]
    signer = info["signer"]
    chain_head = info["chain_head"]
    raw_problems = info["raw_problems"]
    sig_verified = info["sig_verified"]
    sig_status = info["sig_status"]
    sig_reason = info["sig_reason"]
    anchor_checked = info["anchor_checked"]
    primary_path = info["primary_path"]

    gaps: list[dict[str, Any]] = [dict(g) for g in info["chain_gaps"]]
    if sig_verified and not anchor_checked:
        gaps.append(
            _gap(
                "unanchored_chain",
                "info",
                "verified against local chain/head.json without a signed intake ledger anchor; "
                "tail truncation cannot be ruled out if head.json was also modified",
            )
        )

    # Extract agents, task, steps, reviews, findings, gaps
    agent_names: set[str] = set()
    for sk in (state_obj.get("sessions") or {}):
        plat = _platform_from_session_key(sk)
        if plat:
            agent_names.add(plat)

    task_id: str | None = anchor_info.get("task_id") if anchor_info else None
    unreadable_entirely = bool(raw_problems) and not events
    sent_back_items: list[dict[str, Any]] | None = None if unreadable_entirely else []

    n_steps = 0
    n_reviews = 0
    n_gaps = 0
    n_gap_paths = 0
    n_post_missing = 0
    n_pre_missing = 0
    n_writes_unknown = 0
    n_ended = 0
    flags_open: dict[str, dict[str, Any]] = {}
    flags_dismissed: set[str] = set()
    last_review: dict[str, Any] | None = None
    last_consequence_outcome: str | None = None

    for ev in events:
        et = ev.get("type")
        if et == "step":
            n_steps += 1
            a = ev.get("actor") or {}
            if isinstance(a, dict) and _as_str(a.get("platform")):
                agent_names.add(str(a["platform"]))
            if ev.get("post_missing"):
                n_post_missing += 1
            if ev.get("pre_missing"):
                n_pre_missing += 1
            if ev.get("writes_unknown"):
                n_writes_unknown += 1
        elif et in ("session_seen", "session_closed"):
            a = ev.get("actor") or {}
            if isinstance(a, dict) and _as_str(a.get("platform")):
                agent_names.add(str(a["platform"]))
        elif et == "unrecorded_change":
            n_gaps += 1
            ch = ev.get("changes")
            n_gap_paths += len(ch) if isinstance(ch, list) else (_as_int(ev.get("n")) or 1)
        elif et == "review":
            n_reviews += 1
            last_review = ev
            plat = _platform_from_session_key(_as_str(ev.get("session")))
            if plat:
                agent_names.add(plat)
            if ev.get("action") == "continue" and sent_back_items is not None:
                findings = ev.get("findings") or []
                f_details = [
                    str(f.get("kind") or f.get("finding_id") or f)
                    for f in findings
                    if isinstance(f, dict)
                ]
                sent_back_items.append(
                    _send_back_item(
                        action="continue",
                        round_n=_as_int(ev.get("round")),
                        channel="hook_review",
                        summary=(
                            f"review round {ev.get('round') or '?'}: "
                            f"sent back {len(ev.get('sent') or f_details)} finding(s)"
                        ),
                        details=f_details or [str(x) for x in (ev.get("sent") or [])],
                    )
                )
        elif et == "nudge":
            plat = _platform_from_session_key(_as_str(ev.get("session")))
            if plat:
                agent_names.add(plat)
            if sent_back_items is not None:
                paths = [str(x) for x in (ev.get("paths") or [])]
                sent_back_items.append(
                    _send_back_item(
                        action="nudge",
                        round_n=_as_int(ev.get("turn")),
                        channel="hook_review",
                        summary="turn-budget nudge sent back to agent",
                        details=paths,
                    )
                )
        elif et == "prompt" and ev.get("source") == "vacant_feedback":
            if sent_back_items is not None:
                sent_back_items.append(
                    _send_back_item(
                        action="retry_feedback",
                        channel="prompt_feedback",
                        summary="localized failure feedback appended to retry prompt",
                        details=[],
                    )
                )
        elif et == "ended":
            n_ended += 1
            plat = _platform_from_session_key(_as_str(ev.get("session")))
            if plat:
                agent_names.add(plat)
        elif et == "flag":
            if ev.get("dismisses"):
                flags_dismissed.add(str(ev["dismisses"]))
            elif ev.get("flag_id"):
                flags_open[str(ev["flag_id"])] = ev
        elif et == "consequence":
            a = ev.get("actor") or {}
            if isinstance(a, dict) and _as_str(a.get("platform")):
                agent_names.add(str(a["platform"]))
            if _as_str(ev.get("task_id")) and task_id is None:
                task_id = _as_str(ev.get("task_id"))
            oc = _as_str(ev.get("outcome"))
            if oc:
                last_consequence_outcome = oc

    active_flags = [fid for fid in flags_open if fid not in flags_dismissed]
    scan_disabled = _last_scan_disabled(events, state_obj)

    if n_gaps:
        gaps.append(
            _gap(
                "unrecorded_change",
                "warning",
                f"{n_gaps} unrecorded workspace change event(s) ({n_gap_paths} path(s))",
                count=n_gaps,
            )
        )
    if scan_disabled:
        gaps.append(
            _gap(
                "scan_disabled",
                "warning",
                f"file-change observation disabled: {scan_disabled}",
            )
        )
    if n_post_missing:
        gaps.append(
            _gap(
                "post_missing",
                "warning",
                f"{n_post_missing} step(s) missing post-tool hook event",
                count=n_post_missing,
            )
        )
    if n_pre_missing:
        gaps.append(
            _gap(
                "pre_missing",
                "warning",
                f"{n_pre_missing} step(s) missing pre-tool hook event",
                count=n_pre_missing,
            )
        )
    if n_writes_unknown:
        gaps.append(
            _gap(
                "writes_unknown",
                "warning",
                f"{n_writes_unknown} step(s) had unobserved workspace writes",
                count=n_writes_unknown,
            )
        )
    if active_flags:
        gaps.append(
            _gap(
                "open_flags",
                "warning",
                f"{len(active_flags)} unresolved human flag(s): {', '.join(sorted(active_flags)[:6])}",
                count=len(active_flags),
            )
        )

    # Acceptance mapping for trace
    acceptance_kind: str | None = None
    if unreadable_entirely or not has_chain_files:
        result = "unreadable"
        raw_status = "unreadable"
        gaps.append(_gap("unreadable_source", "error", sig_reason))
    elif last_consequence_outcome is not None:
        oc_map = {
            "accept": "accepted",
            "reject": "rejected",
            "hold": "held",
            "escalate": "escalated",
        }
        result = oc_map.get(last_consequence_outcome, "unknown")
        raw_status = last_consequence_outcome
        acceptance_kind = "contract"
    elif last_review is not None:
        mode = _as_str(last_review.get("mode"))
        acceptance_kind = f"zero_config_{mode}" if mode else "zero_config_review"
        action = _as_str(last_review.get("action"))
        left_open = last_review.get("left_open") or []
        if action == "allow" and not left_open:
            result = "accepted"
            raw_status = "allow"
        elif action == "allow" and left_open:
            result = "rejected"
            raw_status = "allow_with_open_findings"
        elif action == "continue":
            result = "rejected"
            raw_status = "continue"
        else:
            result = "unknown"
            raw_status = action
    elif n_steps > 0 or bool(state_obj.get("sessions")):
        result = "unchecked"
        raw_status = "no_review"
        gaps.append(
            _gap(
                "unchecked",
                "info",
                "trace recorded activity without a stop-check review or contract outcome",
            )
        )
    else:
        result = "unknown"
        raw_status = None

    attempts_count = n_reviews if n_reviews > 0 else None
    agent, agents = _agents_fields(agent_names)

    signature = {
        "verified": sig_verified,
        "status": sig_status,
        "scheme": "ed25519_trusted_chain",
        "reason": sig_reason,
        "signer": signer,
        "entries_checked": len(entries) if entries or not raw_problems else None,
        "chain_head": chain_head,
        "anchor_checked": anchor_checked,
    }

    details: dict[str, Any] = {
        "n_steps": n_steps if not unreadable_entirely else None,
        "n_reviews": n_reviews if not unreadable_entirely else None,
        "n_ended_early": n_ended if not unreadable_entirely else None,
        "n_sealed_volumes": len(vols),
        "n_sessions": len(state_obj.get("sessions") or {}) if state_obj else None,
        "scan_disabled": scan_disabled,
        "delivery": (
            {
                "at": delivery_obj.get("at"),
                "mode": delivery_obj.get("mode"),
                "broken": delivery_obj.get("broken"),
            }
            if delivery_obj
            else None
        ),
    }
    if info["restart_entries"]:
        details["n_restart_receipts"] = len(info["restart_entries"])

    return _base_record(
        record_id=f"trace:{key}",
        kind="trace",
        source_path=primary_path,
        auxiliary_paths=aux,
        started_at_ms=started_ms,
        ended_at_ms=ended_ms,
        timestamp_ms=ended_ms if ended_ms is not None else started_ms,
        project=workspace,
        project_key=key,
        agent=agent,
        agents=agents,
        task=task_id,
        attempts_count=attempts_count,
        attempts_max=None,
        attempts_delivered=None,
        result=result,
        raw_status=raw_status,
        acceptance_kind=acceptance_kind,
        checks_passed=None,
        checks_total=None,
        sent_back_count=len(sent_back_items) if sent_back_items is not None else None,
        sent_back_items=sent_back_items,
        gaps=gaps,
        signature=signature,
        details=details,
    )


def _collect_trace(
    vacant_home: pathlib.Path,
    trace_anchors: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    infos = _inspect_trace_projects(vacant_home, trace_anchors)
    records: list[dict[str, Any]] = []
    for info in infos.values():
        if info["restart_entries"] and not info["has_non_restart_trace_activity"]:
            continue
        records.append(_build_trace_record(info))
    return records


# ── Source 3: vrun Receipts ───────────────────────────────────────────────────

def _is_vrun_run_dir(d: pathlib.Path) -> bool:
    if not d.is_dir():
        return False
    if (d / "possess.json").is_file() or (d / "NOT_CERTIFIED.json").is_file():
        return True
    if any(d.glob("receipts_*.ndjson")) or any(d.glob("run_*.json")):
        return True
    return False


def _discover_vrun_run_dirs(vrun_dirs: list[pathlib.Path]) -> list[pathlib.Path]:
    seen: set[pathlib.Path] = set()
    out: list[pathlib.Path] = []
    for base in vrun_dirs:
        if not base.is_dir():
            continue
        if _is_vrun_run_dir(base):
            resolved = base.resolve()
            if resolved not in seen:
                seen.add(resolved)
                out.append(base)
            continue
        for child in sorted(base.iterdir()):
            if _is_vrun_run_dir(child):
                resolved = child.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    out.append(child)
    return out


def _agent_from_vrun(
    run_obj: dict[str, Any] | None,
    possess_obj: dict[str, Any] | None,
    not_cert_obj: dict[str, Any] | None,
) -> set[str]:
    names: set[str] = set()
    if possess_obj and _as_str(possess_obj.get("possess_agent")):
        names.add(str(possess_obj["possess_agent"]))
    if not_cert_obj:
        diag = not_cert_obj.get("diagnostics") or {}
        if isinstance(diag, dict) and _as_str(diag.get("possess_agent")):
            names.add(str(diag["possess_agent"]))
    if run_obj:
        att = run_obj.get("attestation") or {}
        if isinstance(att, dict):
            if _as_str(att.get("agent")):
                names.add(str(att["agent"]))
            fh = att.get("framework_hook") or {}
            if isinstance(fh, dict) and _as_str(fh.get("agent")):
                names.add(str(fh["agent"]))
        argv = run_obj.get("argv")
        if isinstance(argv, list):
            for i, tok in enumerate(argv):
                if tok == "--exec" and i + 1 < len(argv) and _as_str(argv[i + 1]):
                    names.add(str(argv[i + 1]))
                elif tok == "vacant_network.vrun.agentwrap" and i + 1 < len(argv) and _as_str(argv[i + 1]):
                    names.add(str(argv[i + 1]))
    return names


def _attestation_digest(att: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(att, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _collect_vrun(vrun_dirs: list[pathlib.Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for run_dir in _discover_vrun_run_dirs(vrun_dirs):
        rows_p = run_dir / "rows.jsonl"
        rows: list[dict[str, Any]] = []
        rows_malformed = 0
        if rows_p.is_file():
            try:
                for line in rows_p.read_text(encoding="utf-8", errors="replace").splitlines():
                    if not line.strip():
                        continue
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict):
                            rows.append(obj)
                        else:
                            rows_malformed += 1
                    except ValueError:
                        rows_malformed += 1
            except OSError:
                rows_malformed += 1

        possess_p = run_dir / "possess.json"
        possess_obj: dict[str, Any] | None = None
        if possess_p.is_file():
            loaded, _ = _read_json_file(possess_p)
            if isinstance(loaded, dict):
                possess_obj = loaded

        not_cert_p = run_dir / "NOT_CERTIFIED.json"
        not_cert_obj: dict[str, Any] | None = None
        if not_cert_p.is_file():
            loaded, _ = _read_json_file(not_cert_p)
            if isinstance(loaded, dict):
                not_cert_obj = loaded

        arms_from_receipts = {
            p.name[len("receipts_"):-len(".ndjson")] for p in run_dir.glob("receipts_*.ndjson")
        }
        arms_from_runs = {
            p.name[len("run_"):-len(".json")] for p in run_dir.glob("run_*.json")
        }
        arms = sorted(arms_from_receipts | arms_from_runs)
        if not arms:
            arms = ["default"]

        for arm in arms:
            chain_p = run_dir / f"receipts_{arm}.ndjson"
            pub_p = run_dir / f"receipts_{arm}.pub.json"
            run_p = run_dir / f"run_{arm}.json"

            aux: list[pathlib.Path] = []
            for cand in (pub_p, run_p, rows_p, possess_p, not_cert_p):
                if cand.is_file():
                    aux.append(cand)

            run_obj: dict[str, Any] | None = None
            run_err: str | None = None
            if run_p.is_file():
                loaded, run_err = _read_json_file(run_p)
                if isinstance(loaded, dict):
                    run_obj = loaded
                elif run_err is None:
                    run_err = f"{run_p.name} is not a JSON object"

            gaps: list[dict[str, Any]] = []
            if rows_malformed:
                gaps.append(
                    _gap(
                        "malformed_entries",
                        "warning",
                        f"{rows_malformed} malformed line(s) in rows.jsonl",
                        count=rows_malformed,
                    )
                )
            if run_err:
                gaps.append(_gap("unreadable_source", "warning", f"{run_p.name}: {run_err}"))

            entries: list[LogEntry] = []
            torn = 0
            raw_problems: list[str] = []
            verdicts: list[LogEntry] = []
            attempt_entries: list[LogEntry] = []
            signer: str | None = None
            chain_head: str | None = None
            anchor_checked: bool | None = None

            if chain_p.is_file():
                primary_path = chain_p
                entries, torn, raw_problems = _inspect_ndjson_entries(chain_p)
                verdicts = [e for e in entries if e.type in _vr.VERDICT_TYPES]
                attempt_entries = [e for e in entries if e.type in _vr.ATTEMPT_TYPES]
                chain_head = entries[-1].hash() if entries else None

                pub_obj: dict[str, Any] | None = None
                pub_err: str | None = None
                if pub_p.is_file():
                    loaded, pub_err = _read_json_file(pub_p)
                    if isinstance(loaded, dict) and loaded.get("vacant_id") and loaded.get("pub_hex"):
                        pub_obj = loaded
                        signer = str(loaded["vacant_id"])
                    elif pub_err is None:
                        pub_err = "pub.json missing vacant_id or pub_hex"
                else:
                    pub_err = "pubkey_file_missing"

                arm_rows = [r for r in rows if r.get("arm") == arm]
                has_reconcile_anchor = bool(arm_rows) or bool(
                    run_obj and _as_str(run_obj.get("verdict_hash"))
                )
                anchor_checked = has_reconcile_anchor

                if pub_obj is None:
                    sig_verified: bool | None = False
                    sig_status = "unverifiable"
                    sig_reason = pub_err or "pubkey_file_missing"
                    gaps.append(_gap("chain_unverifiable", "error", sig_reason))
                elif raw_problems:
                    sig_verified = False
                    sig_status = "failed"
                    sig_reason = "; ".join(raw_problems)
                    is_trunc = torn > 0 or any("truncated" in x for x in raw_problems)
                    gaps.append(
                        _gap(
                            "chain_truncated" if is_trunc else "signature_failed",
                            "error",
                            sig_reason,
                        )
                    )
                elif not entries:
                    sig_verified = False
                    sig_status = "failed"
                    sig_reason = "empty_chain"
                    gaps.append(_gap("chain_truncated", "error", "empty_chain"))
                else:
                    try:
                        who = PublicIdentity.from_hex(
                            str(pub_obj["vacant_id"]), str(pub_obj["pub_hex"])
                        )
                    except (ValueError, TypeError) as exc:
                        sig_verified = False
                        sig_status = "unverifiable"
                        sig_reason = f"invalid pubkey: {exc}"
                        gaps.append(_gap("chain_unverifiable", "error", sig_reason))
                    else:
                        book = Logbook(entries)
                        fails = _vr.verify_chain_detailed(book, who)
                        lb_ok = bool(book.verify_chain(who))
                        if (not fails) != lb_ok:
                            fails.append({"reason": "detailed_vs_logbook_disagree"})

                        # Reconcile against rows.jsonl when rows for this arm exist
                        trunc_reasons: list[str] = []
                        if arm_rows:
                            if len(verdicts) != len(arm_rows):
                                trunc_reasons.append(
                                    f"verdict_count_ne_rows (verdicts={len(verdicts)}, rows={len(arm_rows)})"
                                )
                            v_ids = {(e.payload or {}).get("task_id") for e in verdicts}
                            r_ids = {r.get("task_id") for r in arm_rows}
                            if v_ids != r_ids:
                                trunc_reasons.append("verdict_task_ids_ne_rows")
                        if len(attempt_entries) < len(verdicts):
                            trunc_reasons.append(
                                f"attempt_fewer_than_verdict (attempts={len(attempt_entries)}, verdicts={len(verdicts)})"
                            )
                        if attempt_entries and not verdicts:
                            trunc_reasons.append("verdict_missing_after_attempts")

                        # Reconcile verdict_hash against run_<ARM>.json if present
                        expected_vh = _as_str((run_obj or {}).get("verdict_hash"))
                        if expected_vh:
                            actual_vhs = {e.hash() for e in verdicts}
                            if expected_vh not in actual_vhs:
                                trunc_reasons.append("verdict_hash_mismatch_or_truncated")

                        # Reconcile attestation_sha256 if both present
                        if verdicts and isinstance((run_obj or {}).get("attestation"), dict):
                            last_vp = verdicts[-1].payload if isinstance(verdicts[-1].payload, dict) else {}
                            chain_att_sha = _as_str(last_vp.get("attestation_sha256"))
                            if chain_att_sha:
                                got_sha = _attestation_digest(run_obj["attestation"])  # type: ignore[index]
                                if got_sha != chain_att_sha:
                                    fails.append(
                                        {
                                            "reason": "attestation_sha256_mismatch",
                                            "want": chain_att_sha,
                                            "got": got_sha,
                                        }
                                    )

                        if fails:
                            sig_verified = False
                            sig_status = "failed"
                            sig_reason = "; ".join(
                                f"{f.get('reason')}" + (f" (seq={f.get('seq')})" if f.get("seq") else "")
                                for f in fails[:5]
                            )
                            gaps.append(_gap("signature_failed", "error", sig_reason))
                        elif trunc_reasons:
                            sig_verified = False
                            sig_status = "failed"
                            sig_reason = "; ".join(trunc_reasons)
                            gaps.append(_gap("chain_truncated", "error", sig_reason))
                        else:
                            sig_verified = True
                            sig_status = "verified"
                            sig_reason = f"{len(entries)} entries verified against ephemeral pubkey"
                            gaps.append(
                                _gap(
                                    "ephemeral_signer",
                                    "info",
                                    "vrun receipts use per-run ephemeral keys; proves post-write "
                                    "tamper-evidence, not signer identity",
                                )
                            )
                            if not anchor_checked:
                                gaps.append(
                                    _gap(
                                        "unanchored_chain",
                                        "info",
                                        "no rows.jsonl or verdict_hash reconciliation available",
                                    )
                                )
                sig_scheme = "ed25519_ephemeral_chain"
            else:
                primary_path = run_p if run_p.is_file() else (not_cert_p if not_cert_p.is_file() else possess_p)
                sig_verified = None
                sig_status = "unsigned"
                sig_scheme = "none"
                if not_cert_obj is not None:
                    sig_reason = "no receipt chain (NOT_CERTIFIED / tier C)"
                elif run_obj and run_obj.get("infra_void"):
                    sig_reason = "no receipt chain written (infra_void)"
                elif run_obj and run_obj.get("vacant") == 0:
                    sig_reason = "no receipt chain (VACANT=0 / tee-only arm)"
                else:
                    sig_reason = "no receipt chain present in run directory"
                gaps.append(_gap("unsigned_source", "warning", sig_reason))

            # Timestamps
            started_ms, ended_ms = _ts_bounds_from_entries(entries)
            if ended_ms is None and run_obj:
                att = run_obj.get("attestation")
                if isinstance(att, dict) and isinstance(att.get("assembled_at"), (int, float)):
                    ended_ms = int(float(att["assembled_at"]) * 1000)
                    started_ms = started_ms or ended_ms

            # Payload extraction (prefer verified/parsed verdict + run_obj)
            last_vp: dict[str, Any] = {}
            if verdicts and isinstance(verdicts[-1].payload, dict):
                last_vp = verdicts[-1].payload
            first_ap: dict[str, Any] = {}
            if attempt_entries and isinstance(attempt_entries[0].payload, dict):
                first_ap = attempt_entries[0].payload

            task_id = (
                _as_str(last_vp.get("task_id"))
                or _as_str(first_ap.get("task_id"))
                or _as_str((run_obj or {}).get("task_id"))
            )
            project = (
                _as_str((run_obj or {}).get("workspace"))
                or _as_str((possess_obj or {}).get("cwd"))
                or _as_str(((not_cert_obj or {}).get("diagnostics") or {}).get("cwd"))
            )
            agent_names = _agent_from_vrun(run_obj, possess_obj, not_cert_obj)
            agent, agents = _agents_fields(agent_names)

            # Attempts
            attempts_count = _as_int((run_obj or {}).get("attempts_used"))
            if attempts_count is None:
                attempts_count = _as_int(last_vp.get("attempts_used"))
            if attempts_count is None and attempt_entries:
                attempts_count = len(attempt_entries)
            attempts_max = _as_int((run_obj or {}).get("max_attempts"))
            if attempts_max is None:
                attempts_max = _as_int(last_vp.get("max_attempts"))

            # Acceptance
            infra_void_val = (run_obj or {}).get("infra_void")
            stop_reason = (
                _as_str((run_obj or {}).get("stop_reason"))
                or _as_str(last_vp.get("stop_reason"))
                or _as_str((possess_obj or {}).get("stop_reason"))
                or _as_str(((not_cert_obj or {}).get("diagnostics") or {}).get("stop_reason"))
            )
            accepted_raw = (run_obj or {}).get("accepted")
            if accepted_raw is None and "accepted" in last_vp:
                accepted_raw = None if last_vp.get("accepted_is_null") is True else _as_bool(last_vp.get("accepted"))
            refused_raw = _as_bool((run_obj or {}).get("refused"))

            unreadable_all = (
                chain_p.is_file() and bool(raw_problems) and not entries and run_obj is None
            ) or (not chain_p.is_file() and run_obj is None and possess_obj is None and not_cert_obj is None)

            if unreadable_all:
                result = "unreadable"
                raw_status = "unreadable"
            elif infra_void_val:
                result = "void"
                raw_status = stop_reason or str(infra_void_val)
                gaps.append(_gap("infra_void", "error", f"vrun infra_void: {infra_void_val}"))
            elif last_vp.get("accepted_is_null") is True or stop_reason == "ungated" or (
                accepted_raw is None and refused_raw is not True and stop_reason in ("ungated", None)
                and (run_obj or {}).get("vacant") == 0
            ):
                result = "unchecked"
                raw_status = stop_reason or "ungated"
                gaps.append(_gap("unchecked", "warning", f"vrun ran without acceptance gate ({raw_status})"))
            elif accepted_raw is True:
                result = "accepted"
                raw_status = stop_reason or "visible_pass"
            elif refused_raw is True or accepted_raw is False:
                result = "rejected"
                raw_status = stop_reason or "visible_fail"
            elif accepted_raw is None and (run_obj is not None or possess_obj is not None):
                result = "unchecked" if stop_reason == "ungated" else "unknown"
                raw_status = stop_reason
            else:
                result = "unknown"
                raw_status = stop_reason

            attempts_delivered = attempts_count if result == "accepted" else None
            checks_passed = _as_int((run_obj or {}).get("visible_passed"))
            checks_total = _as_int((run_obj or {}).get("visible_total"))

            # Sent back
            sent_back_items: list[dict[str, Any]] | None = None if unreadable_all else []
            if sent_back_items is not None:
                run_attempts = (run_obj or {}).get("attempts")
                if isinstance(run_attempts, list):
                    for a in run_attempts:
                        if not isinstance(a, dict):
                            continue
                        fb_deliv = _as_str(a.get("feedback_delivery"))
                        fail_txt = _as_str(a.get("failures"))
                        if fb_deliv and a.get("attempt", 1) > 1:
                            ch_map = {
                                "file": "file_feedback",
                                "prompt": "prompt_feedback",
                                "both": "file_and_prompt",
                            }
                            sent_back_items.append(
                                _send_back_item(
                                    action="retry_feedback",
                                    round_n=_as_int(a.get("attempt")),
                                    channel=ch_map.get(fb_deliv, fb_deliv),
                                    summary=f"attempt {a.get('attempt')} received {fb_deliv} feedback",
                                    details=[fail_txt] if fail_txt else [],
                                )
                            )
                elif attempt_entries:
                    for ae in attempt_entries:
                        ap = ae.payload if isinstance(ae.payload, dict) else {}
                        fb_deliv = _as_str(ap.get("feedback_delivery"))
                        att_n = _as_int(ap.get("attempt"))
                        if fb_deliv and att_n and att_n > 1:
                            sent_back_items.append(
                                _send_back_item(
                                    action="retry_feedback",
                                    round_n=att_n,
                                    channel=fb_deliv,
                                    summary=f"attempt {att_n} received {fb_deliv} feedback",
                                    details=[],
                                )
                            )
                if result == "rejected":
                    fail_summary = _as_str((run_obj or {}).get("failures")) or (
                        f"refused ({raw_status})" if raw_status else "refused"
                    )
                    sent_back_items.append(
                        _send_back_item(
                            action="refuse",
                            round_n=attempts_count,
                            channel="vrun_gate",
                            summary=fail_summary,
                            details=[raw_status] if raw_status else [],
                        )
                    )

            # Orthogonal mediation & attestation gaps (never overwrite signature.verified)
            med = _vr.mediation_of(verdicts) if verdicts else {
                "mediated": None, "void_reason": None, "requests_seen_total": None
            }
            att_dim = _vr.attestation_of(verdicts) if verdicts else {
                "attested": None, "tier": None
            }
            requests_seen = _as_int(med.get("requests_seen_total"))
            if requests_seen is None and run_obj is not None:
                requests_seen = _as_int(run_obj.get("requests_seen"))
            if med.get("mediated") is False or (med.get("mediated") is None and requests_seen == 0 and run_obj is not None):
                gaps.append(
                    _gap(
                        "unmediated",
                        "error",
                        "requests_seen == 0: no model traffic observed through proxy",
                        count=0,
                    )
                )

            tier = _as_str(att_dim.get("tier")) or _as_str(((run_obj or {}).get("attestation") or {}).get("tier"))
            if tier is None and not_cert_obj is not None:
                tier = _as_str(not_cert_obj.get("tier")) or "C"
            attested_val = _as_bool(att_dim.get("attested"))
            if attested_val is None and isinstance((run_obj or {}).get("attestation"), dict):
                attested_val = _as_bool(run_obj["attestation"].get("attested"))
            if not_cert_obj is not None or (tier is not None and tier != "A") or attested_val is False:
                gaps.append(
                    _gap(
                        "unattested",
                        "warning",
                        f"attestation tier={tier or 'unknown'} (not tier A)",
                    )
                )

            unexplained = _as_int(last_vp.get("unexplained"))
            if unexplained is None and isinstance((run_obj or {}).get("attestation"), dict):
                rec_block = run_obj["attestation"].get("reconciled")
                if isinstance(rec_block, dict):
                    unexplained = _as_int(rec_block.get("unexplained"))
            if unexplained is not None and unexplained > 0:
                gaps.append(
                    _gap(
                        "unexplained_calls",
                        "warning",
                        f"{unexplained} unexplained model relay call(s) without matching hook event",
                        count=unexplained,
                    )
                )

            wire_quiesced = _as_bool(last_vp.get("wire_quiesced"))
            if wire_quiesced is None and isinstance((run_obj or {}).get("model_wire"), dict):
                wire_quiesced = _as_bool(run_obj["model_wire"].get("wire_quiesced"))
            if wire_quiesced is False:
                gaps.append(
                    _gap(
                        "wire_not_quiesced",
                        "warning",
                        "proxy timed out draining in-flight calls; requests_seen is a lower bound",
                    )
                )
            wire_blocked = _as_int((run_obj or {}).get("wire_blocked"))
            if wire_blocked is not None and wire_blocked > 0:
                gaps.append(
                    _gap(
                        "wire_blocked",
                        "warning",
                        f"{wire_blocked} request(s) blocked by fail-closed sink",
                        count=wire_blocked,
                    )
                )

            signature = {
                "verified": sig_verified,
                "status": sig_status,
                "scheme": sig_scheme,
                "reason": sig_reason,
                "signer": signer,
                "entries_checked": len(entries) if chain_p.is_file() and (entries or not raw_problems) else None,
                "chain_head": chain_head,
                "anchor_checked": anchor_checked,
            }

            records.append(
                _base_record(
                    record_id=f"vrun:{run_dir.name}:{arm}",
                    kind="vrun",
                    source_path=primary_path,
                    auxiliary_paths=aux,
                    started_at_ms=started_ms,
                    ended_at_ms=ended_ms,
                    timestamp_ms=ended_ms if ended_ms is not None else started_ms,
                    project=project,
                    project_key=None,
                    agent=agent,
                    agents=agents,
                    task=task_id,
                    attempts_count=attempts_count,
                    attempts_max=attempts_max,
                    attempts_delivered=attempts_delivered,
                    result=result,
                    raw_status=raw_status,
                    acceptance_kind="vrun_suite" if result not in ("unchecked", "unreadable", "unknown") else None,
                    checks_passed=checks_passed,
                    checks_total=checks_total,
                    sent_back_count=len(sent_back_items) if sent_back_items is not None else None,
                    sent_back_items=sent_back_items,
                    gaps=gaps,
                    signature=signature,
                    details={
                        "arm": arm,
                        "run_dir": str(run_dir),
                        "requests_seen": requests_seen,
                        "mediated": med.get("mediated"),
                        "tier": tier,
                        "attested": attested_val,
                        "unexplained": unexplained,
                        "wire_quiesced": wire_quiesced,
                        "retry": _as_str((run_obj or {}).get("retry")) or _as_str(last_vp.get("retry")),
                        "feedback_into": _as_str((run_obj or {}).get("feedback_into")),
                        "not_certified": not_cert_obj is not None,
                    },
                )
            )

    return records


# ── Source 4: Restart Mode (signed `restart_receipt` + `result.json` fallback) ─

def _parse_restart_dir_ts_ms(dirname: str) -> int | None:
    m = _RESTART_TS_RE.match(dirname)
    if not m:
        return None
    try:
        tm = time.strptime(m.group(1), "%Y%m%dT%H%M%S")
        return int(time.mktime(tm) * 1000)
    except (ValueError, OverflowError):
        return None


def _strict_eq(a: Any, b: Any) -> bool:
    """Equality that never conflates Python `bool` with `int`."""
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    return a == b


def _scan_restart_result_files(work_root: pathlib.Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not work_root.is_dir():
        return items
    for res_p in sorted(work_root.glob("restart-*/result.json")):
        if not res_p.is_file():
            continue
        run_dir = res_p.parent
        loaded, err = _read_json_file(res_p)
        data = loaded if (err is None and isinstance(loaded, dict)) else None
        if err is None and data is None:
            err = "result.json is not a JSON object"
        items.append(
            {
                "path": res_p,
                "run_dir": run_dir,
                "run_id": run_dir.name,
                "data": data,
                "err": err,
            }
        )
    return items


def _changed_from_receipt(payload: dict[str, Any]) -> dict[str, list[str]]:
    added: list[str] = []
    modified: list[str] = []
    wb = payload.get("written_back")
    if isinstance(wb, list):
        for item in wb:
            if not isinstance(item, dict):
                continue
            rel = _as_str(item.get("path"))
            op = _as_str(item.get("op"))
            if not rel:
                continue
            if op == "added":
                added.append(rel)
            elif op == "modified":
                modified.append(rel)
    deleted = [str(x) for x in (payload.get("deleted") or []) if isinstance(x, str)]
    skipped = [str(x) for x in (payload.get("skipped") or []) if isinstance(x, str)]
    return {
        "added": sorted(added),
        "modified": sorted(modified),
        "deleted": sorted(deleted),
        "skipped": sorted(skipped),
    }


def _compare_receipt_and_result_json(
    entry: LogEntry,
    payload: dict[str, Any],
    pkey: str,
    rj: dict[str, Any],
) -> tuple[list[str], bool]:
    """Compare a signed `restart_receipt` against companion unsigned `result.json`.

    Returns `(mismatches, companion_anchor_ok)`.
    """
    mismatches: list[str] = []
    companion_anchor_ok = False

    rj_rcpt = rj.get("receipt")
    if isinstance(rj_rcpt, dict):
        if rj_rcpt.get("recorded") is True:
            r_seq = _as_int(rj_rcpt.get("seq"))
            r_hash = _as_str(rj_rcpt.get("hash"))
            r_pk = _as_str(rj_rcpt.get("project_key"))
            ref_ok = True
            if r_seq != entry.seq:
                mismatches.append(f"receipt.seq (receipt={entry.seq}, result.json={r_seq})")
                ref_ok = False
            if r_hash != entry.hash():
                mismatches.append(
                    f"receipt.hash (receipt={entry.hash()[:12]}, result.json={(r_hash or 'none')[:12]})"
                )
                ref_ok = False
            if r_pk is not None and r_pk != pkey:
                mismatches.append(f"receipt.project_key (receipt={pkey}, result.json={r_pk})")
                ref_ok = False
            companion_anchor_ok = ref_ok
        elif rj_rcpt.get("recorded") is False:
            mismatches.append("receipt.recorded (signed receipt exists in chain, result.json says recorded=false)")

    if "accepted" in payload and "accepted" in rj:
        if not _strict_eq(payload.get("accepted"), rj.get("accepted")):
            mismatches.append(
                f"accepted (receipt={payload.get('accepted')!r}, result.json={rj.get('accepted')!r})"
            )

    if "delivered_attempt" in payload and "delivered_attempt" in rj:
        if not _strict_eq(_as_int(payload.get("delivered_attempt")), _as_int(rj.get("delivered_attempt"))):
            mismatches.append(
                f"delivered_attempt (receipt={payload.get('delivered_attempt')!r}, "
                f"result.json={rj.get('delivered_attempt')!r})"
            )

    if "max_attempts" in payload and "max_attempts" in rj:
        if not _strict_eq(_as_int(payload.get("max_attempts")), _as_int(rj.get("max_attempts"))):
            mismatches.append(
                f"max_attempts (receipt={payload.get('max_attempts')!r}, "
                f"result.json={rj.get('max_attempts')!r})"
            )

    rj_agent = _as_str(rj.get("agent"))
    rcpt_agent = _as_str(payload.get("agent"))
    if rj_agent is not None and rcpt_agent is not None and rj_agent != rcpt_agent:
        mismatches.append(f"agent (receipt={rcpt_agent!r}, result.json={rj_agent!r})")

    rj_proj = _as_str(rj.get("project"))
    rcpt_proj_sha = _as_str(payload.get("project_path_sha256"))
    if rj_proj is not None and rcpt_proj_sha is not None:
        rj_sha = hashlib.sha256(rj_proj.encode("utf-8")).hexdigest()
        if rj_sha != rcpt_proj_sha:
            mismatches.append("project_path_sha256 (result.json project path differs from signed receipt)")

    rcpt_acc = payload.get("acceptance") if isinstance(payload.get("acceptance"), dict) else None
    rj_acc = rj.get("acceptance") if isinstance(rj.get("acceptance"), dict) else None
    if rcpt_acc is not None and rj_acc is not None:
        if _as_str(rcpt_acc.get("kind")) != _as_str(rj_acc.get("kind")):
            mismatches.append(
                f"acceptance.kind (receipt={rcpt_acc.get('kind')!r}, result.json={rj_acc.get('kind')!r})"
            )
        if _as_str(rcpt_acc.get("command")) != _as_str(rj_acc.get("command")):
            mismatches.append("acceptance.command differs")
    rcpt_integ = _as_str(payload.get("acceptance_integrity")) or _as_str((rcpt_acc or {}).get("integrity"))
    rj_integ = _as_str(rj.get("acceptance_integrity")) or _as_str((rj_acc or {}).get("integrity"))
    if rcpt_integ is not None and rj_integ is not None and rcpt_integ != rj_integ:
        mismatches.append(
            f"acceptance_integrity (receipt={rcpt_integ!r}, result.json={rj_integ!r})"
        )

    rcpt_atts = (
        [a for a in payload["attempts"] if isinstance(a, dict)]
        if isinstance(payload.get("attempts"), list)
        else None
    )
    rj_atts = (
        [a for a in rj["attempts"] if isinstance(a, dict)]
        if isinstance(rj.get("attempts"), list)
        else None
    )
    if rcpt_atts is not None and rj_atts is not None:
        if len(rcpt_atts) != len(rj_atts):
            mismatches.append(f"attempts.count (receipt={len(rcpt_atts)}, result.json={len(rj_atts)})")
        else:
            for idx, (ra, ja) in enumerate(zip(rcpt_atts, rj_atts), start=1):
                for field in ("attempt", "accept", "passed", "run", "status", "rc", "timed_out"):
                    if field in ra and field in ja and not _strict_eq(ra.get(field), ja.get(field)):
                        mismatches.append(
                            f"attempts[{idx}].{field} (receipt={ra.get(field)!r}, result.json={ja.get(field)!r})"
                        )
                rtam = sorted(str(x) for x in (ra.get("tests_tampered") or []) if isinstance(x, str))
                jtam = sorted(str(x) for x in (ja.get("tests_tampered") or []) if isinstance(x, str))
                if rtam != jtam:
                    mismatches.append(f"attempts[{idx}].tests_tampered differs")

    rj_changed = rj.get("changed") if isinstance(rj.get("changed"), dict) else None
    if rj_changed is not None:
        rcpt_changed = _changed_from_receipt(payload)
        if not payload.get("written_back_truncated"):
            for k in ("added", "modified"):
                if isinstance(rj_changed.get(k), list):
                    jvals = sorted(str(x) for x in rj_changed[k] if isinstance(x, str))
                    if rcpt_changed[k] != jvals:
                        mismatches.append(f"changed.{k} differs")
        if not payload.get("deleted_truncated") and isinstance(rj_changed.get("deleted"), list):
            jdel = sorted(str(x) for x in rj_changed["deleted"] if isinstance(x, str))
            if rcpt_changed["deleted"] != jdel:
                mismatches.append("changed.deleted differs")
        if not payload.get("skipped_truncated") and isinstance(rj_changed.get("skipped"), list):
            jskip = sorted(str(x) for x in rj_changed["skipped"] if isinstance(x, str))
            if rcpt_changed["skipped"] != jskip:
                mismatches.append("changed.skipped differs")

    return mismatches, companion_anchor_ok


def _build_restart_record_from_receipt(
    entry: LogEntry,
    proj_info: dict[str, Any],
    companion: dict[str, Any] | None,
    *,
    seen_record_ids: set[str],
) -> dict[str, Any]:
    payload = entry.payload if isinstance(entry.payload, dict) else {}
    pkey = proj_info["key"]
    run_id = _as_str(payload.get("run_id"))
    if run_id is None and companion is not None:
        run_id = companion["run_id"]
    if run_id is None:
        run_id = f"{pkey}:seq{entry.seq}"

    record_id = f"restart:{run_id}"
    if record_id in seen_record_ids:
        record_id = f"restart:{run_id}:seq{entry.seq}"
    seen_record_ids.add(record_id)

    aux: list[pathlib.Path] = list(proj_info["aux"])
    if companion is not None and companion["path"] not in aux:
        aux.append(companion["path"])

    gaps: list[dict[str, Any]] = [dict(g) for g in proj_info["chain_gaps"]]

    sig_verified: bool = proj_info["sig_verified"]
    sig_status: str = proj_info["sig_status"]
    sig_reason: str = proj_info["sig_reason"]
    anchor_checked: bool = bool(proj_info["anchor_checked"])

    mismatches: list[str] = []
    if companion is not None:
        if companion["data"] is None:
            gaps.append(
                _gap(
                    "unreadable_source",
                    "warning",
                    f"companion result.json unreadable (using signed receipt): {companion['err']}",
                )
            )
        else:
            mismatches, companion_anchor_ok = _compare_receipt_and_result_json(
                entry, payload, pkey, companion["data"]
            )
            if companion_anchor_ok:
                anchor_checked = True
            if mismatches:
                gaps.append(
                    _gap(
                        "result_json_mismatch",
                        "warning",
                        "companion result.json disagrees with signed receipt (preferring signed receipt): "
                        + "; ".join(mismatches[:6]),
                        count=len(mismatches),
                    )
                )

    if sig_verified and not anchor_checked:
        gaps.append(
            _gap(
                "unanchored_chain",
                "info",
                "verified against local chain/head.json without companion result.json or signed "
                "intake ledger anchor; tail truncation cannot be ruled out if head.json was also modified",
            )
        )

    # Project path: prefer trace_genesis/state workspace; fall back to companion only if hash matches
    project: str | None = proj_info["workspace"]
    if project is None and companion is not None and companion["data"] is not None:
        cand_proj = _as_str(companion["data"].get("project"))
        rcpt_proj_sha = _as_str(payload.get("project_path_sha256"))
        if cand_proj is not None and (
            rcpt_proj_sha is None
            or hashlib.sha256(cand_proj.encode("utf-8")).hexdigest() == rcpt_proj_sha
        ):
            project = cand_proj

    agent_raw = _as_str(payload.get("agent"))
    agent, agents = _agents_fields({agent_raw} if agent_raw else set())
    task_id = _as_str(payload.get("task_id")) or _as_str(payload.get("task"))
    if task_id is None:
        _req = _as_str(payload.get("request_sha256"))
        if _req:
            task_id = f"request:{_req[:12]}"  # 簽章收據裡的要求雜湊：對得上「這是哪個任務」，不洩漏內容
    if agent is None:
        gaps.append(
            _gap(
                "unattributed_source",
                "info",
                "restart_receipt does not record agent",
            )
        )

    raw_attempts = payload.get("attempts")
    attempts_list = [a for a in raw_attempts if isinstance(a, dict)] if isinstance(raw_attempts, list) else None
    attempts_count = len(attempts_list) if attempts_list is not None else None
    attempts_max = _as_int(payload.get("max_attempts"))
    attempts_delivered = _as_int(payload.get("delivered_attempt"))

    if "accepted" not in payload:
        result = "unknown"
        gaps.append(_gap("missing_fields", "warning", "restart_receipt missing 'accepted' field"))
    else:
        acc_val = payload.get("accepted")
        if acc_val is True:
            result = "accepted"
        elif acc_val is False:
            result = "rejected"
        elif acc_val is None:
            result = "unchecked"
        else:
            result = "unknown"
            gaps.append(
                _gap(
                    "missing_fields",
                    "warning",
                    f"unexpected type for 'accepted' in restart_receipt: {type(acc_val).__name__}",
                )
            )

    acc_meta = payload.get("acceptance") if isinstance(payload.get("acceptance"), dict) else {}
    acc_kind = _as_str(acc_meta.get("kind"))

    delivered_entry: dict[str, Any] | None = None
    if attempts_list:
        if attempts_delivered is not None and 1 <= attempts_delivered <= len(attempts_list):
            delivered_entry = attempts_list[attempts_delivered - 1]
        else:
            delivered_entry = attempts_list[-1]

    raw_status = _as_str((delivered_entry or {}).get("status"))
    checks_passed = _as_int((delivered_entry or {}).get("passed"))
    checks_total = _as_int((delivered_entry or {}).get("run"))

    if result == "unchecked":
        why_un = _as_str(acc_meta.get("reason")) or raw_status or "no_tests"
        gaps.append(_gap("unchecked", "warning", f"restart ran without executable acceptance ({why_un})"))

    tampered: set[str] = set()
    n_timeouts = 0
    n_acc_err = 0
    norm_attempts: list[dict[str, Any]] | None = None
    snapshot_hashes: list[dict[str, Any]] | None = None
    if attempts_list is not None:
        norm_attempts = []
        snapshot_hashes = []
        for a in attempts_list:
            tlist = [t for t in (a.get("tests_tampered") or []) if isinstance(t, str) and t]
            tampered.update(tlist)
            if a.get("timed_out") is True:
                n_timeouts += 1
            if a.get("status") == "acceptance_error":
                n_acc_err += 1
            snap_sha = _as_str(a.get("snapshot_tree_sha256"))
            att_n = _as_int(a.get("attempt"))
            norm_attempts.append(
                {
                    "attempt": att_n,
                    "accept": _as_bool(a.get("accept")),
                    "passed": _as_int(a.get("passed")),
                    "run": _as_int(a.get("run")),
                    "status": _as_str(a.get("status")),
                    "rc": _as_int(a.get("rc")),
                    "timed_out": _as_bool(a.get("timed_out")),
                    "wall_s": a.get("wall_s") if not isinstance(a.get("wall_s"), bool) else None,
                    "tests_tampered": tlist,
                    "snapshot_tree_sha256": snap_sha,
                }
            )
            snapshot_hashes.append({"attempt": att_n, "snapshot_tree_sha256": snap_sha})

    if tampered:
        gaps.append(
            _gap(
                "tests_tampered",
                "warning",
                f"agent modified protected test file(s) (restored before check): {', '.join(sorted(tampered))}",
                count=len(tampered),
            )
        )

    skipped_list = payload.get("skipped") if isinstance(payload.get("skipped"), list) else []
    skipped_count = _as_int(payload.get("skipped_count"))
    eff_skipped_n = skipped_count if skipped_count is not None else len(skipped_list)
    if eff_skipped_n > 0:
        gaps.append(
            _gap(
                "skipped_writeback",
                "warning",
                f"{eff_skipped_n} unsafe path(s) skipped during write-back",
                count=eff_skipped_n,
            )
        )

    wbc_raw = payload.get("write_back_conflicts")
    wb_conflicts = [str(p) for p in wbc_raw if isinstance(p, str) and p] if isinstance(wbc_raw, list) else []
    wbc_count = _as_int(payload.get("write_back_conflicts_count"))
    eff_wbc_n = wbc_count if wbc_count is not None else len(wb_conflicts)
    if eff_wbc_n > 0:
        shown_wbc = ", ".join(wb_conflicts[:5]) + (f" … (+{eff_wbc_n - 5} more)" if eff_wbc_n > 5 else "")
        gaps.append(
            _gap(
                "write_back_conflict",
                "warning",
                f"write-back stopped due to {eff_wbc_n} conflicting path(s): {shown_wbc}",
                count=eff_wbc_n,
            )
        )

    if n_timeouts or n_acc_err:
        parts = []
        if n_timeouts:
            parts.append(f"{n_timeouts} timeout(s)")
        if n_acc_err:
            parts.append(f"{n_acc_err} acceptance error(s)")
        gaps.append(_gap("infra_void", "warning", "restart attempt issues: " + ", ".join(parts)))

    entry_ts = _as_int(entry.ts_ms)
    ts_ms = entry_ts if entry_ts is not None else _parse_restart_dir_ts_ms(run_id)
    argv_list = (
        [str(tok) for tok in payload["argv"]]
        if isinstance(payload.get("argv"), list)
        else None
    )
    changed_summary = _changed_from_receipt(payload)

    signature = {
        "verified": sig_verified,
        "status": sig_status,
        "scheme": "ed25519_trusted_chain",
        "reason": sig_reason,
        "signer": proj_info["signer"],
        "entries_checked": (
            len(proj_info["entries"])
            if proj_info["entries"] or not proj_info["raw_problems"]
            else None
        ),
        "chain_head": proj_info["chain_head"],
        "anchor_checked": anchor_checked,
    }

    details: dict[str, Any] = {
        "source_type": "signed_receipt",
        "run_id": run_id,
        "run_dir": str(companion["run_dir"]) if companion is not None else None,
        "receipt_schema": _as_str(payload.get("receipt_schema")),
        "receipt_seq": entry.seq,
        "receipt_hash": entry.hash(),
        "request_sha256": _as_str(payload.get("request_sha256")),
        "project_path_sha256": _as_str(payload.get("project_path_sha256")),
        "argv": argv_list,
        "acceptance_command": _as_str(acc_meta.get("command")),
        "protected": acc_meta.get("protected") if isinstance(acc_meta.get("protected"), list) else None,
        "attempts": norm_attempts,
        "snapshot_hashes": snapshot_hashes,
        "delivered_snapshot_sha256": _as_str((delivered_entry or {}).get("snapshot_tree_sha256")),
        "tests_tampered": sorted(tampered) if tampered else [],
        "written_back": payload.get("written_back") if isinstance(payload.get("written_back"), list) else None,
        "deleted": payload.get("deleted") if isinstance(payload.get("deleted"), list) else None,
        "skipped": skipped_list,
        "changed": changed_summary,
        "agent_wall_s": payload.get("agent_wall_s"),
        "total_wall_s": payload.get("total_wall_s"),
    }
    acc_integ = _as_str(payload.get("acceptance_integrity")) or _as_str(acc_meta.get("integrity"))
    raw_ir = payload.get("acceptance_integrity_reasons")
    if not isinstance(raw_ir, list):
        raw_ir = acc_meta.get("integrity_reasons") if isinstance(acc_meta.get("integrity_reasons"), list) else []
    acc_integ_reasons = [str(x) for x in raw_ir if isinstance(x, str) and x]
    if acc_integ is not None:
        details["acceptance_integrity"] = acc_integ
        details["acceptance_integrity_reasons"] = acc_integ_reasons
    if payload.get("non_utf8_paths"):
        details["non_utf8_paths"] = True
        if _as_str(payload.get("path_encoding")):
            details["path_encoding"] = _as_str(payload.get("path_encoding"))
    if mismatches:
        details["mismatches"] = mismatches
    if eff_wbc_n > 0:
        details["write_back_conflicts"] = wb_conflicts
        details["write_back_conflicts_count"] = eff_wbc_n

    return _base_record(
        record_id=record_id,
        kind="restart",
        source_path=proj_info["primary_path"],
        auxiliary_paths=aux,
        started_at_ms=entry_ts,
        ended_at_ms=entry_ts,
        timestamp_ms=ts_ms,
        project=project,
        project_key=pkey,
        agent=agent,
        agents=agents,
        task=task_id,
        attempts_count=attempts_count,
        attempts_max=attempts_max,
        attempts_delivered=attempts_delivered,
        result=result,
        raw_status=raw_status,
        acceptance_kind=acc_kind,
        checks_passed=checks_passed,
        checks_total=checks_total,
        sent_back_count=0 if attempts_list is not None else None,
        sent_back_items=[] if attempts_list is not None else None,
        gaps=gaps,
        signature=signature,
        details=details,
    )


def _build_restart_record_from_result_json(
    rj_item: dict[str, Any],
    *,
    broken_trace_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a `restart` record from `result.json` (fallback when unsigned or chain truncated)."""
    res_p: pathlib.Path = rj_item["path"]
    run_dir: pathlib.Path = rj_item["run_dir"]
    loaded: dict[str, Any] | None = rj_item["data"]
    err: str | None = rj_item["err"]
    dir_ts_ms = _parse_restart_dir_ts_ms(run_dir.name)

    gaps: list[dict[str, Any]] = []
    aux: list[pathlib.Path] = []
    source_path: pathlib.Path = res_p
    project_key: str | None = None

    rj_rcpt = loaded.get("receipt") if isinstance(loaded, dict) and isinstance(loaded.get("receipt"), dict) else None

    if broken_trace_info is not None:
        # Chain directory exists on disk and result.json claimed a signed receipt there,
        # yet the receipt is missing/unparseable in the chain -> truncation / corruption!
        project_key = broken_trace_info["key"]
        source_path = broken_trace_info["primary_path"]
        aux = [*broken_trace_info["aux"], res_p]
        anchor_checked = bool(broken_trace_info["anchor_checked"])
        if not broken_trace_info["sig_verified"]:
            sig_reason = broken_trace_info["sig_reason"]
            gaps.extend(dict(g) for g in broken_trace_info["chain_gaps"])
        else:
            ref_anchor = {
                "seq": _as_int((rj_rcpt or {}).get("seq")),
                "hash": _as_str((rj_rcpt or {}).get("hash")),
            }
            anchor_checked = True
            ok, why = broken_trace_info["recorder"].verify(
                trust=broken_trace_info["trust"],
                anchor=ref_anchor,
            )
            sig_reason = (
                why
                if not ok
                else f"restart_receipt for {run_dir.name} not found in trace chain"
            )
            low = sig_reason.lower()
            is_trunc = (
                "truncated" in low
                or "anchored entry" in low
                or "recorded head" in low
                or "not found" in low
            )
            gaps.append(
                _gap(
                    "chain_truncated" if is_trunc else "signature_failed",
                    "error",
                    sig_reason,
                )
            )
        signature = {
            "verified": False,
            "status": "failed",
            "scheme": "ed25519_trusted_chain",
            "reason": sig_reason,
            "signer": broken_trace_info["signer"],
            "entries_checked": (
                len(broken_trace_info["entries"])
                if broken_trace_info["entries"] or not broken_trace_info["raw_problems"]
                else None
            ),
            "chain_head": broken_trace_info["chain_head"],
            "anchor_checked": anchor_checked,
        }
        source_type = "result_json_chain_failed"
    else:
        if rj_rcpt is not None and rj_rcpt.get("recorded") is True:
            sig_reason = "referenced trace chain is missing; fell back to unsigned restart result.json"
            project_key = _as_str(rj_rcpt.get("project_key"))
        elif rj_rcpt is not None and rj_rcpt.get("recorded") is False:
            rec_err = _as_str(rj_rcpt.get("error"))
            sig_reason = (
                f"restart receipt was not recorded ({rec_err}); fell back to unsigned result.json"
                if rec_err
                else "restart receipt was not recorded; fell back to unsigned result.json"
            )
        else:
            sig_reason = "restart result.json is unsigned"
        gaps.append(_gap("unsigned_source", "warning", sig_reason))
        signature = {
            "verified": None,
            "status": "unsigned",
            "scheme": "none",
            "reason": sig_reason,
            "signer": None,
            "entries_checked": None,
            "chain_head": None,
            "anchor_checked": None,
        }
        source_type = "result_json_fallback"

    if err or loaded is None:
        reason = err or "result.json is not a JSON object"
        gaps.append(_gap("unreadable_source", "error", reason))
        return _base_record(
            record_id=f"restart:{run_dir.name}",
            kind="restart",
            source_path=source_path,
            auxiliary_paths=aux,
            started_at_ms=None,
            ended_at_ms=None,
            timestamp_ms=dir_ts_ms,
            project=None,
            project_key=project_key,
            agent=None,
            agents=None,
            task=None,
            attempts_count=None,
            attempts_max=None,
            attempts_delivered=None,
            result="unreadable",
            raw_status="unreadable",
            acceptance_kind=None,
            checks_passed=None,
            checks_total=None,
            sent_back_count=None,
            sent_back_items=None,
            gaps=gaps,
            signature=signature,
            details={"source_type": source_type, "run_dir": str(run_dir), "error": reason},
        )

    project = _as_str(loaded.get("project"))
    agent_raw = _as_str(loaded.get("agent"))
    agent, agents = _agents_fields({agent_raw} if agent_raw else set())
    task_id = _as_str(loaded.get("task_id")) or _as_str(loaded.get("task"))

    if agent is None or task_id is None:
        missing_id = [k for k, v in (("agent", agent), ("task", task_id)) if v is None]
        gaps.append(
            _gap(
                "unattributed_source",
                "info",
                f"restart result.json does not record {', '.join(missing_id)}",
            )
        )

    raw_attempts = loaded.get("attempts")
    attempts_list = [a for a in raw_attempts if isinstance(a, dict)] if isinstance(raw_attempts, list) else None
    attempts_count = len(attempts_list) if attempts_list is not None else None
    attempts_max = _as_int(loaded.get("max_attempts"))
    attempts_delivered = _as_int(loaded.get("delivered_attempt"))

    if "accepted" not in loaded:
        result = "unknown"
        gaps.append(_gap("missing_fields", "warning", "restart result.json missing 'accepted' field"))
    else:
        acc_val = loaded.get("accepted")
        if acc_val is True:
            result = "accepted"
        elif acc_val is False:
            result = "rejected"
        elif acc_val is None:
            result = "unchecked"
        else:
            result = "unknown"
            gaps.append(
                _gap(
                    "missing_fields",
                    "warning",
                    f"unexpected type for 'accepted': {type(acc_val).__name__}",
                )
            )

    acc_meta = loaded.get("acceptance") if isinstance(loaded.get("acceptance"), dict) else {}
    acc_kind = _as_str(acc_meta.get("kind"))

    delivered_entry: dict[str, Any] | None = None
    if attempts_list:
        if attempts_delivered is not None and 1 <= attempts_delivered <= len(attempts_list):
            delivered_entry = attempts_list[attempts_delivered - 1]
        else:
            delivered_entry = attempts_list[-1]

    raw_status = _as_str((delivered_entry or {}).get("status"))
    checks_passed = _as_int((delivered_entry or {}).get("passed"))
    checks_total = _as_int((delivered_entry or {}).get("run"))

    if result == "unchecked":
        why_un = (
            _as_str(acc_meta.get("reason"))
            or _as_str((delivered_entry or {}).get("first_problem"))
            or raw_status
            or "no_tests"
        )
        gaps.append(_gap("unchecked", "warning", f"restart ran without executable acceptance ({why_un})"))

    tampered: set[str] = set()
    n_timeouts = 0
    n_spawn_err = 0
    n_acc_err = 0
    for a in attempts_list or []:
        for t in a.get("tests_tampered") or []:
            if isinstance(t, str) and t:
                tampered.add(t)
        if a.get("timed_out") is True:
            n_timeouts += 1
        if _as_str(a.get("spawn_error")):
            n_spawn_err += 1
        if a.get("status") == "acceptance_error":
            n_acc_err += 1

    if tampered:
        gaps.append(
            _gap(
                "tests_tampered",
                "warning",
                f"agent modified protected test file(s) (restored before check): {', '.join(sorted(tampered))}",
                count=len(tampered),
            )
        )
    changed = loaded.get("changed") if isinstance(loaded.get("changed"), dict) else {}
    skipped = changed.get("skipped") if isinstance(changed.get("skipped"), list) else []
    if skipped:
        gaps.append(
            _gap(
                "skipped_writeback",
                "warning",
                f"{len(skipped)} unsafe path(s) skipped during write-back",
                count=len(skipped),
            )
        )
    wbc_raw = loaded.get("write_back_conflicts")
    wb_conflicts = [str(p) for p in wbc_raw if isinstance(p, str) and p] if isinstance(wbc_raw, list) else []
    if wb_conflicts:
        shown_wbc = ", ".join(wb_conflicts[:5]) + (f" … (+{len(wb_conflicts) - 5} more)" if len(wb_conflicts) > 5 else "")
        gaps.append(
            _gap(
                "write_back_conflict",
                "warning",
                f"write-back stopped due to {len(wb_conflicts)} conflicting path(s): {shown_wbc}",
                count=len(wb_conflicts),
            )
        )
    if n_timeouts or n_spawn_err or n_acc_err:
        parts = []
        if n_timeouts:
            parts.append(f"{n_timeouts} timeout(s)")
        if n_spawn_err:
            parts.append(f"{n_spawn_err} spawn error(s)")
        if n_acc_err:
            parts.append(f"{n_acc_err} acceptance error(s)")
        gaps.append(_gap("infra_void", "warning", "restart attempt issues: " + ", ".join(parts)))

    recorded_ts = _as_int(loaded.get("timestamp_ms"))
    ts_ms = recorded_ts if recorded_ts is not None else dir_ts_ms
    ts_source = "recorded" if recorded_ts is not None else ("run_dir_name" if dir_ts_ms is not None else None)

    details: dict[str, Any] = {
        "source_type": source_type,
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "timestamp_source": ts_source,
        "acceptance_command": _as_str(acc_meta.get("command")),
        "protected": loaded.get("protected"),
        "tests_tampered": sorted(tampered) if tampered else [],
        "changed": changed or None,
        "agent_wall_s": loaded.get("agent_wall_s"),
        "total_wall_s": loaded.get("total_wall_s"),
        "first_problem": _as_str((delivered_entry or {}).get("first_problem")),
    }
    acc_integ = _as_str(loaded.get("acceptance_integrity")) or _as_str(acc_meta.get("integrity"))
    raw_ir = loaded.get("acceptance_integrity_reasons")
    if not isinstance(raw_ir, list):
        raw_ir = acc_meta.get("integrity_reasons") if isinstance(acc_meta.get("integrity_reasons"), list) else []
    acc_integ_reasons = [str(x) for x in raw_ir if isinstance(x, str) and x]
    if acc_integ is not None:
        details["acceptance_integrity"] = acc_integ
        details["acceptance_integrity_reasons"] = acc_integ_reasons
    if rj_rcpt is not None and rj_rcpt.get("recorded") is False and _as_str(rj_rcpt.get("error")):
        details["receipt_error"] = _as_str(rj_rcpt.get("error"))
    if wb_conflicts:
        details["write_back_conflicts"] = wb_conflicts
        details["write_back_conflicts_count"] = len(wb_conflicts)

    return _base_record(
        record_id=f"restart:{run_dir.name}",
        kind="restart",
        source_path=source_path,
        auxiliary_paths=aux,
        started_at_ms=recorded_ts,
        ended_at_ms=recorded_ts,
        timestamp_ms=ts_ms,
        project=project,
        project_key=project_key,
        agent=agent,
        agents=agents,
        task=task_id,
        attempts_count=attempts_count,
        attempts_max=attempts_max,
        attempts_delivered=attempts_delivered,
        result=result,
        raw_status=raw_status,
        acceptance_kind=acc_kind,
        checks_passed=checks_passed,
        checks_total=checks_total,
        sent_back_count=0 if attempts_list is not None else None,
        sent_back_items=[] if attempts_list is not None else None,
        gaps=gaps,
        signature=signature,
        details=details,
    )


def _collect_trace_and_restart(
    vacant_home: pathlib.Path,
    work_root: pathlib.Path,
    trace_anchors: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Collect `trace` and `restart` records together, joining signed restart receipts
    from trace chains with companion `result.json` files by `run_id` (or `(project_key, seq, hash)`).

    Guarantees one run = one record:
      - Signed `restart_receipt` entries produce verified `restart:<run_id>` records and
        consume their companion `result.json` (preferring the receipt and flagging any mismatch).
      - Restart-only trace chains (containing only `trace_genesis` + `restart_receipt` /
        volume structural entries) do NOT emit an empty duplicate `trace:<project_key>` record.
      - Unmatched `result.json` files fall back to unsigned `restart:<run_id>` records (or
        failed/truncated records if the referenced trace chain exists on disk without that receipt).
    """
    trace_infos = _inspect_trace_projects(vacant_home, trace_anchors)
    result_items = _scan_restart_result_files(work_root)

    by_run_id: dict[str, dict[str, Any]] = {}
    by_receipt_ref: dict[tuple[str, int, str], dict[str, Any]] = {}
    for item in result_items:
        by_run_id[item["run_id"]] = item
        data = item["data"]
        if isinstance(data, dict):
            rcpt_ref = data.get("receipt")
            if isinstance(rcpt_ref, dict) and rcpt_ref.get("recorded") is True:
                r_pk = _as_str(rcpt_ref.get("project_key"))
                r_seq = _as_int(rcpt_ref.get("seq"))
                r_hash = _as_str(rcpt_ref.get("hash"))
                if r_pk and r_seq is not None and r_hash:
                    by_receipt_ref[(r_pk, r_seq, r_hash)] = item

    matched_result_paths: set[pathlib.Path] = set()
    claimed_restart_only_pkeys: set[str] = set()
    seen_restart_ids: set[str] = set()
    restart_records: list[dict[str, Any]] = []

    # 1. Signed restart receipts from trace chains (authoritative)
    for pkey, info in trace_infos.items():
        if not info["restart_entries"]:
            continue
        for entry in info["restart_entries"]:
            payload = entry.payload if isinstance(entry.payload, dict) else {}
            run_id = _as_str(payload.get("run_id"))
            companion: dict[str, Any] | None = None
            if run_id is not None and run_id in by_run_id:
                companion = by_run_id[run_id]
            else:
                ref_key = (pkey, entry.seq, entry.hash())
                if ref_key in by_receipt_ref:
                    companion = by_receipt_ref[ref_key]
            if companion is not None:
                matched_result_paths.add(companion["path"])
            restart_records.append(
                _build_restart_record_from_receipt(
                    entry, info, companion, seen_record_ids=seen_restart_ids
                )
            )
        if not info["has_non_restart_trace_activity"]:
            claimed_restart_only_pkeys.add(pkey)

    # 2. Unmatched result.json files (legacy fallback, missing chain, or truncated chain)
    for item in result_items:
        if item["path"] in matched_result_paths:
            continue
        data = item["data"]
        broken_info: dict[str, Any] | None = None
        if isinstance(data, dict):
            rcpt_ref = data.get("receipt")
            if isinstance(rcpt_ref, dict) and rcpt_ref.get("recorded") is True:
                r_pk = _as_str(rcpt_ref.get("project_key"))
                if r_pk and r_pk in trace_infos:
                    # Referenced chain exists on disk, yet this receipt is missing from it
                    broken_info = trace_infos[r_pk]
                    if not broken_info["has_non_restart_trace_activity"]:
                        claimed_restart_only_pkeys.add(r_pk)
        restart_records.append(
            _build_restart_record_from_result_json(item, broken_trace_info=broken_info)
        )

    # 3. Trace records (skipping restart-only chains already emitted as restart records)
    trace_records: list[dict[str, Any]] = []
    for pkey, info in trace_infos.items():
        if pkey in claimed_restart_only_pkeys:
            continue
        trace_records.append(_build_trace_record(info))

    return trace_records, restart_records


def _collect_restart(
    work_root: pathlib.Path,
    *,
    vacant_home: pathlib.Path | None = None,
    trace_anchors: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if vacant_home is not None:
        _, restart_records = _collect_trace_and_restart(
            vacant_home, work_root, trace_anchors or {}
        )
        return restart_records
    return [_build_restart_record_from_result_json(item) for item in _scan_restart_result_files(work_root)]


# ── Source 5: Possess Wire Logs ───────────────────────────────────────────────

def _collect_possess_wire(possess_home: pathlib.Path) -> list[dict[str, Any]]:
    idx_p = possess_home / "proxyd" / "wire" / "index.jsonl"
    if not idx_p.is_file():
        return []

    state_p = possess_home / "state.json"
    aux = [state_p] if state_p.is_file() else []
    wired_agents: list[str] | None = None
    if state_p.is_file():
        st_obj, _ = _read_json_file(state_p)
        if isinstance(st_obj, dict) and isinstance(st_obj.get("channel"), dict):
            wired_agents = sorted(
                k for k, v in st_obj["channel"].items() if isinstance(v, dict) and v.get("ok")
            )

    gaps: list[dict[str, Any]] = [
        _gap("unsigned_source", "warning", "possess wire index.jsonl has no cryptographic signature"),
        _gap(
            "unattributed_source",
            "info",
            "resident proxy wire log is machine-level and cannot attribute calls to a specific agent, project, or task",
        ),
        _gap(
            "unchecked",
            "info",
            "wire proxy records model traffic only; it performs no acceptance check",
        ),
    ]
    signature = {
        "verified": None,
        "status": "unsigned",
        "scheme": "none",
        "reason": "possess wire index.jsonl is unsigned",
        "signer": None,
        "entries_checked": None,
        "chain_head": None,
        "anchor_checked": None,
    }

    try:
        raw_lines = idx_p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        gaps.append(_gap("unreadable_source", "error", f"cannot read {idx_p}: {exc}"))
        return [
            _base_record(
                record_id="possess_wire:proxyd",
                kind="possess_wire",
                source_path=idx_p,
                auxiliary_paths=aux,
                started_at_ms=None,
                ended_at_ms=None,
                timestamp_ms=None,
                project=None,
                project_key=None,
                agent=None,
                agents=None,
                task=None,
                attempts_count=None,
                attempts_max=None,
                attempts_delivered=None,
                result="unreadable",
                raw_status="unreadable",
                acceptance_kind=None,
                checks_passed=None,
                checks_total=None,
                sent_back_count=None,
                sent_back_items=None,
                gaps=gaps,
                signature=signature,
                details={"error": str(exc)},
            )
        ]

    valid_n = 0
    malformed_n = 0
    blocked_n = 0
    refused_path_n = 0
    errors_n = 0
    by_wire: collections.Counter[str] = collections.Counter()
    by_path: collections.Counter[str] = collections.Counter()
    ts_list: list[int] = []

    for ln in raw_lines:
        if not ln.strip():
            continue
        try:
            rec = json.loads(ln)
        except ValueError:
            malformed_n += 1
            continue
        if not isinstance(rec, dict):
            malformed_n += 1
            continue
        valid_n += 1
        ts_val = rec.get("ts")
        if isinstance(ts_val, (int, float)) and not isinstance(ts_val, bool):
            ts_list.append(int(float(ts_val) * 1000))
        wire = _as_str(rec.get("wire")) or "unknown"
        by_wire[wire] += 1
        method = _as_str(rec.get("method")) or "?"
        path = _as_str(rec.get("path")) or "?"
        by_path[f"{method} {path} [{wire}]"] += 1
        if rec.get("blocked") is True:
            blocked_n += 1
        if rec.get("refused_path") is True:
            refused_path_n += 1
        if rec.get("error"):
            errors_n += 1

    if malformed_n:
        gaps.append(
            _gap(
                "malformed_entries",
                "warning",
                f"{malformed_n} malformed line(s) in {idx_p.name}",
                count=malformed_n,
            )
        )
    if blocked_n:
        gaps.append(
            _gap(
                "wire_blocked",
                "warning",
                f"{blocked_n} call(s) blocked by fail-closed sink",
                count=blocked_n,
            )
        )
    if refused_path_n:
        gaps.append(
            _gap(
                "wire_refused_path",
                "warning",
                f"{refused_path_n} call(s) refused by model path policy",
                count=refused_path_n,
            )
        )

    started_ms = min(ts_list) if ts_list else None
    ended_ms = max(ts_list) if ts_list else None
    unreadable_all = malformed_n > 0 and valid_n == 0
    result = "unreadable" if unreadable_all else "unchecked"

    return [
        _base_record(
            record_id="possess_wire:proxyd",
            kind="possess_wire",
            source_path=idx_p,
            auxiliary_paths=aux,
            started_at_ms=started_ms,
            ended_at_ms=ended_ms,
            timestamp_ms=ended_ms if ended_ms is not None else started_ms,
            project=None,
            project_key=None,
            agent=None,
            agents=None,
            task=None,
            attempts_count=None,
            attempts_max=None,
            attempts_delivered=None,
            result=result,
            raw_status="unreadable" if unreadable_all else "wire_only",
            acceptance_kind=None,
            checks_passed=None,
            checks_total=None,
            sent_back_count=None,
            sent_back_items=None,
            gaps=gaps,
            signature=signature,
            details={
                "requests_total": valid_n if not unreadable_all else None,
                "malformed_n": malformed_n,
                "errors_n": errors_n if not unreadable_all else None,
                "blocked_n": blocked_n if not unreadable_all else None,
                "refused_path_n": refused_path_n if not unreadable_all else None,
                "by_wire": dict(sorted(by_wire.items())),
                "by_path": dict(sorted(by_path.items())),
                "wired_agents": wired_agents,
            },
        )
    ]


# ── Unified Collection & Filtering ────────────────────────────────────────────

def collect_all(
    *,
    vacant_home: pathlib.Path | str | None = None,
    work_root: pathlib.Path | str | None = None,
    vrun_dirs: list[pathlib.Path | str] | None = None,
    possess_home: pathlib.Path | str | None = None,
    kinds: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """Collect normalized `vacant-audit-record/1` records across all configured sources.

    Read-only: never modifies any file on disk.
    Sorted newest-first (`timestamp_ms` descending; `None` timestamps last), with deterministic
    tie-breaking by `record_id`.
    """
    paths = resolve_paths(
        vacant_home=vacant_home,
        work_root=work_root,
        vrun_dirs=vrun_dirs,
        possess_home=possess_home,
    )
    want = set(kinds) if kinds else set(KINDS)
    records: list[dict[str, Any]] = []

    # Always collect ledger anchors if intake_ledger, trace, or restart is requested
    ledger_records: list[dict[str, Any]] = []
    trace_anchors: dict[str, dict[str, Any]] = {}
    if "intake_ledger" in want or "trace" in want or "restart" in want:
        ledger_records, trace_anchors = _collect_intake_ledgers(paths["vacant_home"])

    if "trace" in want or "restart" in want:
        trace_records, restart_records = _collect_trace_and_restart(
            paths["vacant_home"], paths["work_root"], trace_anchors
        )
        if "trace" in want:
            records.extend(trace_records)
        if "restart" in want:
            records.extend(restart_records)
    if "intake_ledger" in want:
        records.extend(ledger_records)
    if "vrun" in want:
        records.extend(_collect_vrun(paths["vrun_dirs"]))
    if "possess_wire" in want:
        records.extend(_collect_possess_wire(paths["possess_home"]))

    records.sort(
        key=lambda r: (
            0 if r["timestamp_ms"] is not None else 1,
            -(r["timestamp_ms"] or 0),
            r["record_id"],
        )
    )
    return records


def parse_since(spec: str, *, now_ms: int | None = None) -> int:
    """Parse `--since` into epoch milliseconds.

    Supports:
      - Relative durations: `30m`, `24h`, `7d`, `2w`, `60s`
      - ISO-8601 date (`2026-11-01`) or datetime (`2026-11-01T12:00:00Z`, `...+08:00`)
      - Unix epoch seconds (`1700000000`) or milliseconds (`1700000000000`)
    """
    s = spec.strip()
    if not s:
        raise ValueError("empty --since value")

    m = _DURATION_RE.match(s)
    if m:
        val = float(m.group(1))
        unit = m.group(2).lower()
        mult = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 7 * 86400}[unit]
        base = now_ms if now_ms is not None else int(time.time() * 1000)
        return int(base - val * mult * 1000)

    if s.isdigit():
        num = int(s)
        return num if num >= 100_000_000_000 else num * 1000

    iso = s[:-1] + "+00:00" if s.endswith(("Z", "z")) else s
    try:
        dt = datetime.datetime.fromisoformat(iso)
    except ValueError as exc:
        raise ValueError(
            f"invalid --since value {spec!r}: expected ISO-8601 date/time, "
            "relative duration (e.g. 24h, 7d), or unix epoch"
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return int(dt.timestamp() * 1000)


def _agent_matches(rec: dict[str, Any], query: str) -> bool:
    q = query.strip().lower()
    if not q:
        return True
    candidates: list[str] = []
    if isinstance(rec.get("agents"), list):
        candidates.extend(str(a) for a in rec["agents"] if a)
    elif rec.get("agent"):
        candidates.append(str(rec["agent"]))
    for cand in candidates:
        low = cand.lower()
        if low == q or low.split(":", 1)[0] == q:
            return True
    return False


def _project_matches(rec: dict[str, Any], query: str) -> bool:
    q = query.strip().lower()
    if not q:
        return True
    proj = rec.get("project")
    pkey = rec.get("project_key")
    if isinstance(proj, str) and q in proj.lower():
        return True
    if isinstance(pkey, str) and pkey.lower().startswith(q):
        return True
    return False


def _expand_csv(values: list[str] | None) -> set[str] | None:
    if not values:
        return None
    out: set[str] = set()
    for v in values:
        for part in v.split(","):
            p = part.strip().lower()
            if p:
                out.add(p)
    return out or None


def filter_records(
    records: list[dict[str, Any]],
    *,
    agent: str | None = None,
    project: str | None = None,
    since: str | int | None = None,
    kind: list[str] | str | None = None,
    result: list[str] | str | None = None,
    now_ms: int | None = None,
) -> list[dict[str, Any]]:
    """Filter normalized audit records by agent, project, since, kind, and result."""
    since_ms: int | None = None
    if since is not None:
        since_ms = since if isinstance(since, int) else parse_since(since, now_ms=now_ms)

    kind_set = _expand_csv([kind] if isinstance(kind, str) else kind)
    if kind_set is not None:
        bad = sorted(kind_set - set(KINDS))
        if bad:
            raise ValueError(f"unknown --kind {bad!r} (valid: {', '.join(KINDS)})")

    result_set = _expand_csv([result] if isinstance(result, str) else result)
    if result_set is not None:
        bad = sorted(result_set - set(RESULTS))
        if bad:
            raise ValueError(f"unknown --result {bad!r} (valid: {', '.join(RESULTS)})")

    out: list[dict[str, Any]] = []
    for rec in records:
        if kind_set is not None and rec.get("kind") not in kind_set:
            continue
        if result_set is not None and (rec.get("acceptance") or {}).get("result") not in result_set:
            continue
        if agent is not None and not _agent_matches(rec, agent):
            continue
        if project is not None and not _project_matches(rec, project):
            continue
        if since_ms is not None:
            ts = rec.get("timestamp_ms")
            if ts is None or ts < since_ms:
                continue
        out.append(rec)
    return out


# ── Rendering & Export ────────────────────────────────────────────────────────

def export_jsonl(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return "\n".join(
        json.dumps(_sanitize_utf8_obj(r), ensure_ascii=False, separators=(",", ":"))
        for r in records
    ) + "\n"


def _fmt_ts(ts_ms: int | None) -> str:
    if ts_ms is None:
        return "unknown"
    try:
        dt = datetime.datetime.fromtimestamp(ts_ms / 1000.0, tz=datetime.timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%SZ")
    except (OSError, OverflowError, ValueError):
        return "unknown"


def _fmt_verified(sig: dict[str, Any]) -> str:
    v = sig.get("verified")
    if v is True:
        return "yes"
    if v is False:
        return "FAIL"
    return "unsigned"


def _fmt_result(rec: dict[str, Any]) -> str:
    res = str((rec.get("acceptance") or {}).get("result") or "unknown")
    details = rec.get("details") or {}
    wbc = details.get("write_back_conflicts")
    wbc_n = details.get("write_back_conflicts_count")
    has_wbc = bool(wbc) or (isinstance(wbc_n, int) and wbc_n > 0)
    if has_wbc:
        return f"{res}, not written back (conflict)"
    return res


def format_list(records: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    if not records:
        lines.append("No matching audit records found.")
        lines.append(f"Note: {WORDING_BOUNDARY}")
        return "\n".join(lines) + "\n"

    res_vals = [_fmt_result(r) for r in records]
    res_w = max(12, max((len(v) for v in res_vals), default=12))
    header = (
        f"{'RECORD_ID':<34} {'KIND':<14} {'AGENT':<10} {'TASK':<18} "
        f"{'ATT':>4} {'RESULT':<{res_w}} {'BACK':>4} {'VERIFIED':<9} {'INTEGRITY':<10} {'GAPS':>4}  TIMESTAMP"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for r, res_s in zip(records, res_vals):
        att_n = (r.get("attempts") or {}).get("count")
        att_s = str(att_n) if att_n is not None else "-"
        back_n = (r.get("sent_back") or {}).get("count")
        back_s = str(back_n) if back_n is not None else "-"
        ver_s = _fmt_verified(r.get("signature") or {})
        integ_s = str((r.get("details") or {}).get("acceptance_integrity") or "-")
        gaps_n = len(r.get("gaps") or [])
        lines.append(
            f"{str(r['record_id'])[:34]:<34} "
            f"{str(r['kind'])[:14]:<14} "
            f"{str(r.get('agent') or '-')[:10]:<10} "
            f"{str(r.get('task') or '-')[:18]:<18} "
            f"{att_s:>4} "
            f"{res_s:<{res_w}} "
            f"{back_s:>4} "
            f"{ver_s:<9} "
            f"{integ_s[:10]:<10} "
            f"{gaps_n:>4}  "
            f"{_fmt_ts(r.get('timestamp_ms'))}"
        )
    lines.append("")
    lines.append(f"Total: {len(records)} record(s). {WORDING_BOUNDARY}")
    return "\n".join(lines) + "\n"


def format_show(rec: dict[str, Any]) -> str:
    sig = rec.get("signature") or {}
    acc = rec.get("acceptance") or {}
    att = rec.get("attempts") or {}
    sb = rec.get("sent_back") or {}
    src = rec.get("source") or {}
    lines = [
        f"record_id  : {rec['record_id']}",
        f"schema     : {rec['schema']}",
        f"kind       : {rec['kind']}",
        f"source     : {src.get('path')}",
        f"timestamp  : {_fmt_ts(rec.get('timestamp_ms'))} "
        f"(start={_fmt_ts(rec.get('started_at_ms'))}, end={_fmt_ts(rec.get('ended_at_ms'))})",
        f"project    : {rec.get('project') or 'unknown'}"
        + (f" (key={rec['project_key']})" if rec.get("project_key") else ""),
        f"agent      : {rec.get('agent') or 'unknown'}",
        f"task       : {rec.get('task') or 'unknown'}",
        f"attempts   : count={att.get('count') if att.get('count') is not None else 'unknown'}"
        f"  max={att.get('max') if att.get('max') is not None else 'unknown'}"
        f"  delivered={att.get('delivered') if att.get('delivered') is not None else 'unknown'}",
        f"acceptance : result={_fmt_result(rec)}  passed={acc.get('passed')}  "
        f"raw={acc.get('raw_status') or 'unknown'}  kind={acc.get('kind') or 'unknown'}",
    ]
    if acc.get("checks_total") is not None:
        lines.append(f"checks     : {acc.get('checks_passed')}/{acc.get('checks_total')}")
    details = rec.get("details") or {}
    wbc = details.get("write_back_conflicts")
    if wbc:
        lines.append(f"write_back : not written back (conflict: {', '.join(str(x) for x in wbc[:10])})")
    acc_integ = details.get("acceptance_integrity")
    if acc_integ is not None:
        ir = details.get("acceptance_integrity_reasons") or []
        ir_s = f" ({'; '.join(str(x) for x in ir)})" if ir else ""
        lines.append(f"integrity  : {acc_integ}{ir_s}")
    lines.append(
        f"signature  : verified={sig.get('verified')}  status={sig.get('status')}  "
        f"scheme={sig.get('scheme')}  anchor_checked={sig.get('anchor_checked')}"
    )
    lines.append(f"sig_reason : {sig.get('reason')}")
    if sig.get("chain_head"):
        lines.append(f"chain_head : {sig['chain_head']}")
    sb_count = sb.get("count")
    lines.append(f"sent_back  : {sb_count if sb_count is not None else 'unknown'}")
    for item in sb.get("items") or []:
        rnd = f"r{item['round']} " if item.get("round") is not None else ""
        ch = f"[{item['channel']}] " if item.get("channel") else ""
        lines.append(f"  - {rnd}{ch}{item.get('action')}: {item.get('summary')}")
    gaps = rec.get("gaps") or []
    lines.append(f"gaps       : {len(gaps)}")
    for g in gaps:
        lines.append(f"  - [{g.get('severity')}] {g.get('code')}: {g.get('detail')}")
    lines.append("")
    lines.append(f"Note: {WORDING_BOUNDARY}")
    return "\n".join(lines) + "\n"


# ── CLI ───────────────────────────────────────────────────────────────────────

def _add_path_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--vacant-home", default=None,
                   help="override $VACANT_HOME (default: $VACANT_HOME or ~/.vacant)")
    p.add_argument("--work-root", default=None,
                   help="override $VACANT_WORK (default: $VACANT_WORK or <vacant-home>-work)")
    p.add_argument("--vrun-dir", action="append", default=None,
                   help="vrun run directory or parent dir (repeatable; default: $VACANT_RUN_DIR or <vacant-home>-run)")
    p.add_argument("--possess-home", default=None,
                   help="override $VACANT_POSSESS_HOME (default: <vacant-home>/possess)")


def _add_filter_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--agent", default=None, help="filter by agent/platform name (case-insensitive)")
    p.add_argument("--project", default=None, help="filter by project path substring or trace project key")
    p.add_argument("--since", default=None,
                   help="filter records at or after timestamp (ISO-8601, duration like 24h/7d, or unix epoch)")
    p.add_argument("--kind", action="append", default=None,
                   help=f"filter by source kind ({', '.join(KINDS)}; repeatable or comma-separated)")
    p.add_argument("--result", action="append", default=None,
                   help=f"filter by acceptance result ({', '.join(RESULTS)}; repeatable or comma-separated)")


def _add_strict_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--strict", action="store_true",
                   help="exit 3 if any listed record fails signature verification or any restart record has no signed receipt (for scripts/CI)")
    p.add_argument("--require-signed", action="store_true",
                   help="like --strict, and also exit 3 if any listed record is unsigned")


def _strict_rc(records: list[dict[str, Any]], args: argparse.Namespace) -> int:
    if not (getattr(args, "strict", False) or getattr(args, "require_signed", False)):
        return 0
    failed = [r for r in records if (r.get("signature") or {}).get("verified") is False]
    unsigned_all = [r for r in records if (r.get("signature") or {}).get("verified") is None]
    unsigned_restart = [
        r for r in unsigned_all
        if r.get("kind") == "restart"
        and any(g.get("code") == "unsigned_source" for g in (r.get("gaps") or []))
    ]
    bad_unsigned = unsigned_all if getattr(args, "require_signed", False) else unsigned_restart
    bad = failed + bad_unsigned
    if bad:
        parts: list[str] = []
        if failed:
            parts.append(f"{len(failed)} record(s) failed verification")
        if bad_unsigned:
            label = "unsigned" if getattr(args, "require_signed", False) else "unsigned restart record(s)"
            parts.append(f"{len(bad_unsigned)} {label}")
        print(
            f"vacant audit: {', '.join(parts)}"
            f": {', '.join(r['record_id'] for r in bad[:5])}{' …' if len(bad) > 5 else ''}",
            file=sys.stderr,
        )
        return 3
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="vacant audit",
        description=(
            "List, inspect, and export normalized audit records (schema vacant-audit-record/1) "
            "across trace chains, intake ledgers, vrun receipts, restart runs, and possess wire logs.\n"
            "\n"
            "Boundary: Signed records are tamper-evident and re-verifiable offline; "
            "records are never guaranteed to be complete. Unsigned sources and unanchored "
            "tail truncation cannot be cryptographically proven absent."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="audit_cmd", required=True)

    plist = sub.add_parser(
        "list",
        help="list normalized audit records across all projects (tamper-evident, re-verifiable; not complete)",
    )
    _add_path_args(plist)
    _add_filter_args(plist)
    plist.add_argument("--limit", type=int, default=None, help="maximum number of records to display")
    _add_strict_args(plist)
    fmt_g = plist.add_mutually_exclusive_group()
    fmt_g.add_argument("--json", dest="as_json", action="store_true", help="output JSON array")
    fmt_g.add_argument("--jsonl", dest="as_jsonl", action="store_true", help="output JSONL")

    pshow = sub.add_parser(
        "show",
        help="show one normalized audit record by record_id (exact or unique prefix)",
    )
    pshow.add_argument("record_id", help="record_id (exact or unique prefix from `vacant audit list`)")
    _add_path_args(pshow)
    pshow.add_argument("--json", dest="as_json", action="store_true", help="output full JSON object")

    pexp = sub.add_parser(
        "export",
        help="export normalized audit records as JSONL (tamper-evident, re-verifiable; not complete)",
    )
    _add_path_args(pexp)
    _add_filter_args(pexp)
    efmt = pexp.add_mutually_exclusive_group()
    efmt.add_argument("--jsonl", dest="as_jsonl", action="store_true",
                      help="export one JSON record per line (default)")
    efmt.add_argument("--json", dest="as_json", action="store_true",
                      help="export a single JSON array")
    pexp.add_argument("--out", default=None, help="write output to FILE instead of stdout")
    _add_strict_args(pexp)

    return ap


def _find_record(records: list[dict[str, Any]], query: str) -> tuple[dict[str, Any] | None, str | None]:
    exact = [r for r in records if r["record_id"] == query]
    if len(exact) == 1:
        return exact[0], None
    pref = [r for r in records if r["record_id"].startswith(query)]
    if len(pref) == 1:
        return pref[0], None
    if len(pref) > 1:
        sample = ", ".join(r["record_id"] for r in pref[:5])
        return None, f"ambiguous record_id prefix {query!r} matched {len(pref)} records ({sample})"
    return None, f"no audit record matching {query!r}"


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw[:1] == ["audit"]:
        raw = raw[1:]
    if not raw:
        build_parser().print_help()
        return 0
    args = build_parser().parse_args(raw)

    try:
        records = collect_all(
            vacant_home=args.vacant_home,
            work_root=args.work_root,
            vrun_dirs=args.vrun_dir,
            possess_home=args.possess_home,
        )
        if args.audit_cmd == "show":
            rec, err = _find_record(records, args.record_id)
            if err or rec is None:
                print(f"vacant audit: {err}", file=sys.stderr)
                return 1
            if args.as_json:
                print(json.dumps(rec, ensure_ascii=False, indent=2))
            else:
                sys.stdout.write(format_show(rec))
            return 0

        filtered = filter_records(
            records,
            agent=args.agent,
            project=args.project,
            since=args.since,
            kind=args.kind,
            result=args.result,
        )
    except ValueError as exc:
        print(f"vacant audit: {exc}", file=sys.stderr)
        return 2

    if args.audit_cmd == "list":
        if args.limit is not None:
            if args.limit < 0:
                print("vacant audit: --limit must be >= 0", file=sys.stderr)
                return 2
            filtered = filtered[: args.limit]
        if args.as_jsonl:
            sys.stdout.write(export_jsonl(filtered))
        elif args.as_json:
            print(json.dumps(filtered, ensure_ascii=False, indent=2))
        else:
            sys.stdout.write(format_list(filtered))
        return _strict_rc(filtered, args)

    if args.audit_cmd == "export":
        payload = (
            json.dumps(filtered, ensure_ascii=False, indent=2) + "\n"
            if args.as_json
            else export_jsonl(filtered)
        )
        if args.out:
            out_p = pathlib.Path(args.out)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(payload, encoding="utf-8")
        else:
            sys.stdout.write(payload)
        return _strict_rc(filtered, args)

    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
