#!/usr/bin/env python3
"""Experiment T feedback builder, record-only flag computation, and signed Logbook chain.

Implements the four cycle-0 arms of Experiment T ("send unsupported claims back for revision"):
  - A  : native c0 draft only (no revision rounds)
  - G  : up to 2 extra rounds with a fixed generic review prompt (no record info)
  - T  : up to 2 extra rounds; recompute F1/F3 flags from RECORDS ONLY after each round;
         send back ONLY flagged lines with line id/label, problem kind, and the list of
         pages the agent actually fetched (from its egress log); stop when none flagged.
  - T0 : same stop rule as T, but feedback only states the count of unsupported lines
         (no line ids, no URLs).

Every feedback message (exact text) and its triggering evidence (flag set, fetched-page
list, round) is appended as an Ed25519-signed event to a per-cell `vacant_network.logbook`
chain, with a `reconstruct` verifier/replayer analogous to `vacant_network.controller`.

No ground truth, answer key, or model judge is ever read by this module.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import tempfile
import threading
import time
from typing import Any, Mapping, Sequence

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from vacant_network.trace import blame as B  # noqa: E402
from vacant_network.trace import sources as S  # noqa: E402
from vacant_network.trace.recorder import Recorder  # noqa: E402

#: Valid Experiment T arms.
EXPT_ARMS: tuple[str, ...] = ("A", "G", "T", "T0")

#: Exact fixed generic review prompt for arm G (KS-1 clean, no record info).
GENERIC_REVIEW_PROMPT: str = (
    "Please re-check your report for completeness and correctness and fix anything that is wrong."
)

#: Exact problem-kind strings for arm T feedback.
PROBLEM_MISSING: str = "missing value"
PROBLEM_NOT_IN_FETCHED: str = "value not in any fetched page"
PROBLEM_CHANGED_NO_SOURCE: str = "changed without reading a source"

#: Fixed template fragments for arm T feedback (KS-1 clean).
T_FEEDBACK_HEADER: str = (
    "The following lines in report.md could not be verified from the pages you fetched. "
    "Please check and fix only these lines, then stop:"
)
T_ITEM_TEMPLATE: str = "- [{claim_id}] {label}: {reason}"
T_FETCHED_HEADER: str = "Pages you fetched:"
T_FETCHED_NONE: str = "Pages you fetched: (none)"

#: Fixed template for arm T0 feedback (count-only, no line ids, KS-1 clean).
T0_FEEDBACK_TEMPLATE: str = (
    "{n} lines in your report have no supporting source in what you fetched; please check and fix them."
)

#: Signed logbook event type.
EXPT_EVENT_TYPE: str = "EXPT_FEEDBACK"

#: KS-1 guard covering both vacant_network.memory.KS1_FORBIDDEN and ops.e1.KS1_BANNED_RE.
_EXPT_KS1_BANNED_RE = re.compile(
    r"你有責任|你會被懲罰|你將被懲罰|你要負責|後果自負|會被懲罰|負責任|"
    r"you are responsible|you will be punished|you will be held accountable|"
    r"responsib|punish|penal|blame|fault of",
    re.I,
)


def assert_ks1_clean(text: str) -> str:
    """Assert text contains no KS-1 banned responsibility/punishment phrasing."""
    m = _EXPT_KS1_BANNED_RE.search(text or "")
    if m:
        raise ValueError(f"KS-1 violation in Experiment T text: {m.group(0)!r}")
    return text


def _assert_static_templates_ks1_clean() -> None:
    for s in (
        GENERIC_REVIEW_PROMPT,
        PROBLEM_MISSING,
        PROBLEM_NOT_IN_FETCHED,
        PROBLEM_CHANGED_NO_SOURCE,
        T_FEEDBACK_HEADER,
        T_ITEM_TEMPLATE,
        T_FETCHED_HEADER,
        T_FETCHED_NONE,
        T0_FEEDBACK_TEMPLATE,
    ):
        assert_ks1_clean(s)


_assert_static_templates_ks1_clean()


def _atomic_write_text(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}.{threading.get_ident()}")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


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


def parse_report_values(text: str, claims: Sequence[Mapping[str, Any]]) -> dict[str, str | None]:
    """Parse claim values from report.md using template prefixes (same logic as score_d2.parse_report,
    normalizing empty/blank/placeholder values to None).
    """
    lines = text.splitlines()
    out: dict[str, str | None] = {}
    for c in claims:
        cid = str(c["id"])
        pref = str(c["template_line"]).rstrip()
        key = pref.rstrip(":").rstrip()
        hit = [ln for ln in lines if ln.strip().startswith(key)]
        if not hit:
            out[cid] = None
            continue
        val = hit[0].split(":", 1)[1] if ":" in hit[0] else ""
        val_s = val.strip()
        if not val_s or "____" in val_s:
            out[cid] = None
        else:
            out[cid] = val_s
    return out


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
            t = S._blob_text(rec, e.get("sha256"))
            if t is not None:
                out.append({"seq": int(e["seq"]), "url": e["url"], "text": t, "source": "egress"})
    return out


def egress_fetched_urls(rec: Recorder, *, bound_seq: int | None = None) -> list[str]:
    """Sorted unique HTTP URLs actually fetched by the agent according to its own egress log."""
    urls: set[str] = set()
    for e in rec.events():
        if e.get("type") != "source_fetch":
            continue
        if bound_seq is not None and int(e.get("seq") or 0) > bound_seq:
            continue
        url = e.get("url")
        if url and not e.get("tls") and S._blob_text(rec, e.get("sha256")) is not None:
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

    Primary definitions (matching exp1_flags amend1 + Experiment T spec):
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
        round_fetches = [
            u for u in uk
            if int(u["seq"]) > prev_bound_seq
        ]
    else:
        round_fetches = list(uk)

    values = parse_report_values(report_text, claims)
    flags_by_claim: dict[str, dict[str, Any]] = {}
    flagged: list[dict[str, Any]] = []

    for c in claims:
        cid = str(c["id"])
        lab = claim_label(c)
        v = values.get(cid)
        pv = prev_values.get(cid) if prev_values is not None else None

        f1 = False
        f3 = False
        reasons: list[str] = []

        if v is None:
            f1 = True
            reasons.append(PROBLEM_MISSING)
        else:
            carriers = [u for u in uk if S.plain_contains(str(u.get("text") or ""), v)]
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
            "value": v,
            "prev_value": pv,
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


def build_G_feedback() -> str:
    """Arm G fixed generic review prompt (KS-1 clean, zero record information)."""
    return assert_ks1_clean(GENERIC_REVIEW_PROMPT)


def build_T_feedback(
    flagged: Sequence[Mapping[str, Any]],
    fetched_urls: Sequence[str],
) -> str | None:
    """Arm T feedback: fixed template listing ONLY flagged lines (id/label + problem kind)
    and the list of pages the agent actually fetched (URLs from its egress log).

    Returns None when `flagged` is empty (stop rule: no feedback).
    """
    if not flagged:
        return None
    lines = [T_FEEDBACK_HEADER]
    for item in flagged:
        cid = str(item["claim_id"])
        lab = str(item["label"])
        reason = str(item.get("problem_kind") or "; ".join(item.get("reasons") or []))
        lines.append(T_ITEM_TEMPLATE.format(claim_id=cid, label=lab, reason=reason))
    lines.append("")
    uniq_urls = sorted(dict.fromkeys(str(u) for u in fetched_urls if u))
    if uniq_urls:
        lines.append(T_FETCHED_HEADER)
        for u in uniq_urls:
            lines.append(f"- {u}")
    else:
        lines.append(T_FETCHED_NONE)
    msg = "\n".join(lines)
    return assert_ks1_clean(msg)


def build_T0_feedback(flagged: Sequence[Mapping[str, Any]]) -> str | None:
    """Arm T0 feedback: count-only message (no line ids, no URLs).

    Returns None when `flagged` is empty (same stop rule as T).
    """
    n = len(flagged)
    if n == 0:
        return None
    msg = T0_FEEDBACK_TEMPLATE.format(n=n)
    return assert_ks1_clean(msg)


def build_arm_feedback(
    arm: str,
    flag_report: Mapping[str, Any] | None = None,
) -> str | None:
    """Dispatch feedback construction by arm ('G', 'T', 'T0')."""
    if arm == "G":
        return build_G_feedback()
    if arm == "T":
        assert flag_report is not None
        return build_T_feedback(flag_report["flagged"], flag_report["fetched_urls"])
    if arm == "T0":
        assert flag_report is not None
        return build_T0_feedback(flag_report["flagged"])
    if arm == "A":
        return None
    raise ValueError(f"unsupported Experiment T arm: {arm!r}")


# =============================================================================
# Signed Logbook Chain & Reconstruct Helper (analogous to vacant_network.controller)
# =============================================================================


def make_trigger_evidence(
    arm: str,
    round_idx: int,
    flag_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build compact, deterministic triggering-evidence dict for the signed logbook event."""
    if arm == "G":
        return {
            "round": int(round_idx),
            "flag_set": [],
            "flagged_count": 0,
            "fetched_urls": [],
            "record_based": False,
        }
    fr = flag_report or {}
    flagged = [
        {
            "claim_id": str(item["claim_id"]),
            "label": str(item["label"]),
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
        "record_based": True,
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
    ts_ms: int | None = None,
    extra: Mapping[str, Any] | None = None,
) -> Any:
    """Append a signed EXPT_FEEDBACK event to a `vacant_network.logbook.Logbook`."""
    from vacant_network import crypto

    ts = int(ts_ms) if ts_ms is not None else (time.time_ns() // 1_000_000)
    payload: dict[str, Any] = {
        "schema": "vacant.d2.expT.feedback/1",
        "arm": str(arm),
        "round": int(round_idx),
        "decision": str(decision),
        "feedback_text": feedback_text,
        "evidence": dict(evidence),
        "signer": {
            "vacant_id": identity.vacant_id,
            "pub_hex": crypto.pub_to_hex(identity.pub),
        },
    }
    if extra:
        payload["extra"] = dict(extra)
    return logbook.append(EXPT_EVENT_TYPE, payload, identity, ts_ms=ts)


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
    """Verify a signed Experiment T feedback chain and return/print its reconstructed history.

    Raises `vacant_network.logbook.ChainError` if the chain is missing, empty, or fails
    cryptographic Ed25519 signature / hash-chain verification.
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
        if entry.type != EXPT_EVENT_TYPE or not isinstance(entry.payload, dict):
            continue
        p = entry.payload
        ev = p.get("evidence") or {}
        rec = {
            "seq": entry.seq,
            "ts_ms": entry.ts_ms,
            "arm": p.get("arm"),
            "round": p.get("round"),
            "decision": p.get("decision"),
            "feedback_text": p.get("feedback_text"),
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
                f"fetched_urls={n_urls} feedback_chars={fb_len}",
                file=out_stream,
            )
    return history


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify and reconstruct an Experiment T feedback chain.")
    sp = ap.add_subparsers(dest="cmd", required=True)
    rc = sp.add_parser("reconstruct", help="Verify and print events from a feedback_chain.ndjson")
    rc.add_argument("chain", help="Path to feedback_chain.ndjson")
    rc.add_argument("--json", action="store_true", help="Print reconstructed events as JSON")
    a = ap.parse_args()
    if a.cmd == "reconstruct":
        hist = reconstruct(a.chain, emit=not a.json)
        if a.json:
            print(json.dumps(hist, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
