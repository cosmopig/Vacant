#!/usr/bin/env python3
"""Offline failure taxonomy + selection-ceiling replay over recorded G-experiment calls.

READ-ONLY on runs/. Zero network calls: everything below re-executes candidate code that
is already on disk (calls.jsonl responses) through the *local* sandbox in vacant/checks.py,
using gain_run.py's own extract_code()/meets_demand() so the pass/fail definition matches
what the real runner used. See ops/gain/gain_run.py:98-130 for those two functions and
vacant/checks.py for the sandbox itself.

Usage:
    export VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz
    .venv/bin/python ops/gain/replay/failure_taxonomy.py [--run RUN_NAME ...] [--out OUT.json]
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import pathlib
import random
import signal
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from ops.gain.gain_run import (  # noqa: E402
    _GAIN_ALLOWED_IMPORTS, behavior_signature, extract_code, load_tasks, meets_demand,
)
from vacant.checks import _candidate_functions, _run_sandboxed  # noqa: E402

SEED = "g-r212-route-20260828"
N = 179
DEFAULT_RUNS = ["g_r441_gemma_only_mbpp_b", "g_r356_3arm_20260830"]
TIMEOUT_S = 10.0  # authoritative sandbox timeout, only used for cross-validation sampling


# ── FAST in-process re-execution ────────────────────────────────────────────
# WHY THIS EXISTS: the authoritative scorer is vacant.checks.run_python_check via
# gain_run.meets_demand() -- a runner process that spawns a *second* worker process and
# RPCs every call across a pipe (vacant/checks.py:488-595). That is the right design for
# scoring a live run (it is the actual product's acceptance gate and must be adversary-
# safe), but this replay is running on a machine shared by several concurrent sibling
# sessions (observed load average ~600-1000 on 12 cores). Under that contention, spawning
# 2 fresh OS processes per single assertion-suite check (and hidden_check has up to ~100
# assertions run one RPC round-trip at a time) either stalls for many seconds per check or
# times out from scheduler starvation alone -- which would corrupt the "sandbox_timeout"
# vs "fails_visible" split with load artifacts, not real candidate behavior.
#
# The pass/fail *rule* is unchanged: check_code is the exact same string gain_run hands to
# the sandbox (self-contained -- it defines its own __aeq tolerance-aware comparator and
# execs a fresh copy of the canonical solution to diff against, see the sample printed
# during development). What changes is only the *isolation mechanism*: instead of a
# separate worker process reached over a wire-literal RPC, the candidate and the check
# code are exec'd directly into one shared namespace dict in this process, with a
# SIGALRM wall-clock cutoff standing in for the subprocess timeout. This is safe to do
# here specifically because every candidate passed through `_candidate_functions` first
# -- the exact AST allowlist (vacant/checks.py:172-231) the real sandbox itself uses to
# decide whether to even attempt a run -- so only candidates using the same 11-module
# import whitelist and no forbidden calls/attrs are ever exec'd.
# Equivalence to the authoritative path is not assumed -- see `_cross_validate()` below,
# which re-runs a random sample through the real sandboxed `meets_demand` and reports the
# agreement rate; that number is part of this report's output, not asserted separately.
class _Timeout(Exception):
    pass


def _alarm(_signum, _frame):
    raise _Timeout()


def _exec_with_timeout(sources: list[str], timeout_s: float) -> tuple[dict | None, str]:
    """Exec each source into one shared namespace; return (ns, "ok"|"timeout"|"exception:T")."""
    ns: dict = {}
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.setitimer(signal.ITIMER_REAL, timeout_s)
    try:
        for src in sources:
            exec(compile(src, "<candidate>", "exec"), ns, ns)  # noqa: S102
        return ns, "ok"
    except _Timeout:
        return None, "timeout"
    except BaseException as exc:  # candidate/check raised -- that IS a fail signal
        return None, f"exception:{type(exc).__name__}"
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def fast_check(code: str, check_code: str, timeout_s: float = 10.0) -> tuple[bool, str]:
    """In-process stand-in for gain_run.meets_demand's boolean result. See module docstring."""
    _, status = _exec_with_timeout([code, check_code], timeout_s)
    return status == "ok", status


def fast_behavior_key(code: str, task: dict, timeout_s: float = 10.0) -> str:
    """In-process stand-in for gain_run.behavior_signature -- same probe shape (ok/type/repr
    or err/type/message triples per behavior_inputs entry), computed without a subprocess.
    Only used to bucket OFF5's 5 candidates by observed behavior; never used as a pass/fail
    score (that always goes through hidden_check via fast_check/meets_demand)."""
    entry_point = task.get("entry_point")
    inputs = task.get("behavior_inputs")
    if not inputs or not entry_point:
        ok, _ = fast_check(code, task["visible_check"]["code"], timeout_s)
        return "VISIBLE_PASS" if ok else "VISIBLE_FAIL"
    ns, status = _exec_with_timeout([code], timeout_s)
    if ns is None:
        return "EXEC_FAIL"
    fn = ns.get(entry_point)
    if not callable(fn):
        return "EXEC_FAIL"
    results = []
    for args in inputs:
        old = signal.signal(signal.SIGALRM, _alarm)
        signal.setitimer(signal.ITIMER_REAL, timeout_s)
        try:
            val = fn(*args)
            results.append(["ok", type(val).__name__, repr(val)])
        except _Timeout:
            results.append(["err", "Timeout", ""])
        except BaseException as exc:
            results.append(["err", type(exc).__name__, str(exc)[:200]])
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)
    return json.dumps(results, sort_keys=True)


# ── task loading ──────────────────────────────────────────────────────────
def load_task_map() -> dict[str, dict]:
    return {t["task_id"]: t for t in load_tasks("evalplus", SEED, N)}


# ── call index ────────────────────────────────────────────────────────────
def load_calls(run: str) -> list[dict]:
    path = REPO / "runs" / run / "calls.jsonl"
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out


def index_calls(calls: list[dict]) -> dict[tuple, list[dict]]:
    """(arm, task_id, role, phase) -> [ok==True calls], time-ordered."""
    idx: dict[tuple, list[dict]] = collections.defaultdict(list)
    for c in calls:
        if not c.get("ok"):
            continue
        meta = c.get("meta") or {}
        arm = meta.get("arm")
        if not arm:
            continue
        key = (arm, meta.get("task_id"), c["role"], meta.get("phase"))
        idx[key].append(c)
    for v in idx.values():
        v.sort(key=lambda c: c.get("ts_ms", 0))
    return idx


def load_rows(run: str) -> list[dict]:
    path = REPO / "runs" / run / "rows.jsonl"
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out


# ── AST-level classification helpers ───────────────────────────────────────
def top_and_any_names(code: str):
    """Return (top_level_def_names, any_def_names) or (None, None) on SyntaxError."""
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return None, None
    top = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            top.append(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if isinstance(value, ast.Lambda):
                top.extend(t.id for t in targets if isinstance(t, ast.Name))
    anyn = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return top, anyn


def classify(code: str, task: dict, row_visible_ok: bool) -> tuple[str, str | None]:
    """(class, subclass) for a candidate already known to fail hidden_check."""
    entry_point = task.get("entry_point")
    top, anyn = top_and_any_names(code)
    if top is None:
        return "syntax_or_import_error", "syntax_error"
    funcs = _candidate_functions(
        code, allowed_imports=_GAIN_ALLOWED_IMPORTS,
        allowed_entry_points=(entry_point,) if entry_point else (),
    )
    if funcs is None:
        return "syntax_or_import_error", "forbidden_import_or_call"
    if entry_point and entry_point not in funcs:
        sub = "defined_but_not_top_level" if entry_point in anyn else "never_defined"
        return "naming_miss", sub
    if row_visible_ok:
        return "hidden_only_fail", None
    _, status = fast_check(code, task["visible_check"]["code"])
    if status == "timeout":
        return "sandbox_timeout", None
    return "fails_visible", status


# ── OFF5 sibling bucket resolution ─────────────────────────────────────────
def resolve_off5_code(row: dict, task: dict, calls5: list[dict]) -> tuple[str | None, str]:
    """Reconstruct which of the 5 OFF5 candidates was scored for this row.

    Returns (code_or_None, status) where status in
    {"unique", "resolved_by_visible_ok", "resolved_by_hidden_agreement", "ambiguous"}.
    """
    codes = [extract_code(c["response"]) for c in calls5]
    sigs = [fast_behavior_key(c, task) for c in codes]
    buckets: dict[str, list[int]] = collections.defaultdict(list)
    for i, s in enumerate(sigs):
        buckets[s].append(i)
    max_votes = max(len(v) for v in buckets.values())
    tied = [v for v in buckets.values() if len(v) == max_votes]
    winners = [i for grp in tied for i in grp]
    uniq_codes = list(dict.fromkeys(codes[i] for i in winners))
    if len(uniq_codes) == 1:
        return uniq_codes[0], "unique"
    # narrow by the visible_ok this row actually recorded
    matching = []
    for c in uniq_codes:
        ok, _ = fast_check(c, task["visible_check"]["code"])
        if ok == row["visible_ok"]:
            matching.append(c)
    matching = list(dict.fromkeys(matching))
    if len(matching) == 1:
        return matching[0], "resolved_by_visible_ok"
    pool = matching or uniq_codes
    hidden = [fast_check(c, task["hidden_check"]["code"])[0] for c in pool]
    if len(set(hidden)) == 1:
        return pool[0], "resolved_by_hidden_agreement"
    return None, "ambiguous"


# ── main replay ─────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--validate-n", type=int, default=25,
                     help="sample size for cross-validating fast_check against the "
                          "authoritative subprocess-sandboxed meets_demand")
    args = ap.parse_args()
    runs = args.run or DEFAULT_RUNS

    tasks = load_task_map()
    hidden_cache: dict[tuple[str, str], bool] = {}
    validation_pairs: list[tuple[str, str]] = []  # (task_id, code) sampled for cross-check

    def hidden_pass(task_id: str, code: str) -> bool:
        key = (task_id, code)
        if key not in hidden_cache:
            t = tasks[task_id]
            ok, _ = fast_check(code, t["hidden_check"]["code"])
            hidden_cache[key] = ok
            validation_pairs.append(key)
        return hidden_cache[key]

    report: dict = {"runs": {}}

    for run in runs:
        print(f"=== {run} ===", file=sys.stderr)
        rows = load_rows(run)
        calls = load_calls(run)
        cidx = index_calls(calls)

        # sibling pool per task_id: all ok==True gen/revise candidate codes in this run
        sibling_pool: dict[str, list[str]] = collections.defaultdict(list)
        off5_pool: dict[str, list[str]] = collections.defaultdict(list)
        for (arm, tid, role, phase), clist in cidx.items():
            if role not in ("gen", "revise"):
                continue
            for c in clist:
                code = extract_code(c["response"])
                sibling_pool[tid].append(code)
                if arm == "OFF5":
                    off5_pool[tid].append(code)

        class_counts = collections.Counter()      # (arm, cls) -> n
        subclass_counts = collections.Counter()    # (arm, cls, sub) -> n
        ceiling_counts = collections.Counter()      # (arm, cls, "any_ceiling"/"off5_ceiling") -> n
        reconstruction_status = collections.Counter()
        sanity_mismatch = []
        unresolved_rows = []
        examples = collections.defaultdict(list)   # (arm, cls) -> [task_id,...] up to 5

        n_failing = 0
        n_processed = 0
        for row in rows:
            if row.get("meets_demand") is not False:
                continue
            n_failing += 1
            n_processed += 1
            if n_processed % 5 == 0:
                print(f"  ... {n_processed} failing rows processed", file=sys.stderr, flush=True)
            arm, tid = row["arm"], row["task_id"]
            task = tasks.get(tid)
            if task is None:
                unresolved_rows.append((arm, tid, "task_not_found"))
                continue

            code = None
            status = "unique"
            if arm == "OFF":
                calls1 = cidx.get(("OFF", tid, "gen", None))
                if calls1:
                    code = extract_code(calls1[0]["response"])
            elif arm == "ON":
                sel = row.get("selected_version", "")
                if sel.startswith("initial"):
                    c = cidx.get(("ON", tid, "gen", "initial"))
                else:
                    c = cidx.get(("ON", tid, "revise", "revision"))
                if c:
                    code = extract_code(c[0]["response"])
            elif arm == "OFF5":
                calls5 = cidx.get(("OFF5", tid, "gen", None))
                if calls5 and len(calls5) == 5:
                    code, status = resolve_off5_code(row, task, calls5)
                else:
                    status = f"incomplete_calls({len(calls5) if calls5 else 0})"
            reconstruction_status[status] += 1

            if code is None:
                unresolved_rows.append((arm, tid, status))
                continue

            # sanity check: does replaying hidden_check on this reconstructed code
            # reproduce the row's own recorded meets_demand=False?
            replay_ok = hidden_pass(tid, code)
            if replay_ok is not False:
                sanity_mismatch.append((arm, tid, status, replay_ok))
                unresolved_rows.append((arm, tid, "sanity_mismatch"))
                continue

            cls, sub = classify(code, task, row["visible_ok"])
            class_counts[(arm, cls)] += 1
            if sub:
                subclass_counts[(arm, cls, sub)] += 1
            if len(examples[(arm, cls)]) < 5:
                examples[(arm, cls)].append(tid)

            # ceiling: does ANY sibling candidate (this task, this run) pass hidden_check?
            sibs = [c for c in sibling_pool.get(tid, []) if c != code]
            any_ceiling = any(hidden_pass(tid, c) for c in dict.fromkeys(sibs))
            off5_sibs = [c for c in off5_pool.get(tid, []) if c != code]
            off5_ceiling = any(hidden_pass(tid, c) for c in dict.fromkeys(off5_sibs)) if off5_sibs else False
            if any_ceiling:
                ceiling_counts[(arm, cls, "any_ceiling")] += 1
            if off5_ceiling:
                ceiling_counts[(arm, cls, "off5_ceiling")] += 1

        run_report = {
            "n_failing_rows": n_failing,
            "reconstruction_status": dict(reconstruction_status),
            "n_unresolved": len(unresolved_rows),
            "unresolved_sample": unresolved_rows[:20],
            "n_sanity_mismatch": len(sanity_mismatch),
            "sanity_mismatch_sample": sanity_mismatch[:10],
            "class_counts": {f"{a}|{c}": n for (a, c), n in class_counts.items()},
            "subclass_counts": {f"{a}|{c}|{s}": n for (a, c, s), n in subclass_counts.items()},
            "ceiling_counts": {f"{a}|{c}|{k}": n for (a, c, k), n in ceiling_counts.items()},
            "examples": {f"{a}|{c}": v for (a, c), v in examples.items()},
        }
        report["runs"][run] = run_report
        print(json.dumps(run_report, indent=2, ensure_ascii=False), file=sys.stderr)

    # ── cross-validate the fast in-process path against the authoritative sandbox ──
    # Sample from the actual (task_id, code) pairs this run relied on and re-score them
    # through the real subprocess sandbox (gain_run.meets_demand). This is the check that
    # the speed shortcut above did not quietly change the answer.
    print(f"\ncross-validating fast_check against authoritative meets_demand "
          f"({len(hidden_cache)} distinct (task,code) pairs seen)...", file=sys.stderr)
    rng = random.Random(20260903)
    sample = rng.sample(validation_pairs, min(args.validate_n, len(validation_pairs)))
    agree = disagree = inconclusive = 0
    disagreements = []
    for task_id, code in sample:
        t = tasks[task_id]
        fast_ok = hidden_cache[(task_id, code)]
        try:
            real_ok, real_err = meets_demand(
                code, t["hidden_check"]["code"], 30, entry_point=t.get("entry_point"))
        except Exception as exc:  # InfraVoid or similar -- not a disagreement, just noise
            inconclusive += 1
            print(f"  inconclusive {task_id}: {exc}", file=sys.stderr)
            continue
        if real_ok == fast_ok:
            agree += 1
        else:
            disagree += 1
            disagreements.append({"task_id": task_id, "fast": fast_ok, "authoritative": real_ok})
        print(f"  ... validated {agree + disagree + inconclusive}/{len(sample)}",
              file=sys.stderr, flush=True)
    report["cross_validation"] = {
        "n_sampled": len(sample), "agree": agree, "disagree": disagree,
        "inconclusive": inconclusive, "disagreements": disagreements,
        "note": "sampled from hidden_check fast_check() calls only "
                "(the fast in-process re-execution path); visible_check narrowing and "
                "behavior-signature bucketing in resolve_off5_code() were not separately "
                "cross-validated -- their downstream effect is caught by the "
                "reconstruction sanity check (replaying hidden_check must reproduce the "
                "row's own recorded meets_demand=False) already applied to every row.",
    }
    print(json.dumps(report["cross_validation"], indent=2, ensure_ascii=False), file=sys.stderr)

    out_path = args.out or str(REPO / "ops" / "gain" / "replay" / "failure_taxonomy_out.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nwrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
