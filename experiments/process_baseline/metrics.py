"""Process metrics v0 for agent trajectories (see README for definitions).

Everything here is a deterministic function of a normalized trajectory, so the
same code scores the no-Vacant baseline, the with-Vacant condition, and a user
reference process. The reference process is a pluggable input (JSON); this repo
only ships clearly-labelled SYNTHETIC example personas to demonstrate the metric.
"""
from __future__ import annotations

from typing import Any, Sequence


def action_sequence(steps: Sequence[dict]) -> str:
    return "".join(s["action"] for s in steps if s.get("action"))


def collapse(seq: str) -> str:
    """Run-length collapse (RRRE -> RE): compares strategy, not verbosity."""
    out = []
    for ch in seq:
        if not out or out[-1] != ch:
            out.append(ch)
    return "".join(out)


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def lcs_len(a: str, b: str) -> int:
    prev = [0] * (len(b) + 1)
    for ca in a:
        cur = [0]
        for j, cb in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if ca == cb else max(prev[j], cur[j - 1]))
        prev = cur
    return prev[-1]


def edit_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return 1 - levenshtein(a, b) / max(len(a), len(b))


def lcs_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return 2 * lcs_len(a, b) / (len(a) + len(b))


def order_features(steps: Sequence[dict]) -> dict[str, Any]:
    tool_steps = [s for s in steps if s.get("action")]
    acts = [s["action"] for s in tool_steps]
    edit_idx = [i for i, a in enumerate(acts) if a == "E"]
    first_e = edit_idx[0] if edit_idx else None
    last_e = edit_idx[-1] if edit_idx else None
    written = {p for s in tool_steps for p in s.get("files_written", [])}
    read = set()
    read_before_edit_files = True
    for s in tool_steps:
        read.update(s.get("files_read", []))
        for p in s.get("files_written", []):
            if p not in read and s.get("tool") == "edit":
                read_before_edit_files = False
    return {
        "n_steps": len(acts),
        "n_plan_texts": sum(1 for s in steps if s.get("kind") == "plan"),
        "counts": {a: acts.count(a) for a in "RSEXTAF"},
        "made_edit": first_e is not None,
        "read_before_first_edit": (first_e is not None and any(a in "RS" for a in acts[:first_e])) if first_e is not None else None,
        "edited_files_were_read_first": read_before_edit_files if written else None,
        "test_before_first_edit": ("T" in acts[:first_e]) if first_e is not None else None,
        "test_after_last_edit": ("T" in acts[last_e + 1:]) if last_e is not None else None,
        "asked_before_acting": (acts[0] == "A") if acts else None,
        "asked_any": "A" in acts,
        "n_tool_errors": sum(1 for s in tool_steps if s.get("is_error")),
        "n_retries": sum(1 for s in tool_steps if s.get("retry_of") is not None),
        "files_read": sorted(read),
        "files_written": sorted(written),
    }


BOOL_FEATURES = ["read_before_first_edit", "test_before_first_edit", "test_after_last_edit",
                 "asked_before_acting", "made_edit"]


def compare(steps: Sequence[dict], reference: dict) -> dict[str, Any]:
    """Similarity of a run to a reference process.

    reference = {"sequence": "SRTETF", "features": {"asked_before_acting": false, ...},
                 "max_diff_lines": 20 (optional)}
    Any subset of keys may be given. Returns per-component scores in [0, 1].
    """
    seq = action_sequence(steps)
    out: dict[str, Any] = {"run_sequence": seq}
    if "sequence" in reference:
        ref = reference["sequence"]
        out["edit_sim"] = round(edit_similarity(seq, ref), 3)
        out["lcs_sim"] = round(lcs_similarity(seq, ref), 3)
        out["edit_sim_collapsed"] = round(edit_similarity(collapse(seq), collapse(ref)), 3)
    feats = order_features(steps)
    want = reference.get("features", {})
    agree = [feats.get(k) == v for k, v in want.items() if feats.get(k) is not None]
    if agree:
        out["feature_agreement"] = round(sum(agree) / len(agree), 3)
        out["feature_n"] = len(agree)
    return out
