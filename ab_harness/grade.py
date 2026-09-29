#!/usr/bin/env python3
"""grade.py — score ONE finished cell against the hidden checks.

Rules that are not negotiable here:

1. The hidden tree is copied into a FRESH grading directory together with the
   candidate `solution.py`. It is never copied into the agent's workspace, and
   it is never read while the agent is running. Grading runs strictly after.
2. Only `solution.py` is carried over. Nothing else the agent produced is
   visible to the grader, so an agent cannot pass by littering the workspace.
3. The verdict is a conjunction: every `check_*` in the hidden file must pass.
   A count of passing cases is not a verdict.
4. A cell with no `solution.py` scores `delivered=False, passed=False`. It is
   NOT dropped, and it is NOT silently excluded.

Two numbers are recorded for every cell, and they are different questions:

  hidden_pass        did the file that exists satisfy the hidden checks?
                     (what would have shipped if nothing had gated it)
  delivered          was this cell actually allowed to deliver?
                     A  plain arm: always true, there is no gate.
                     B  vacant arm: true only if vacant accepted.
  correct            delivered AND hidden_pass.  <-- this is the headline metric.
                     A refusal counts as a failure. That is the whole point.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
HIDDEN = ROOT / "bank_hidden"
RUNS = ROOT / "runs"

GRADER = r'''
import importlib.util, json, sys, pathlib
here = pathlib.Path(__file__).resolve().parent
sol = here / "solution.py"
hid = sorted(here.glob("test_hidden*.py"))
if not sol.exists():
    print(json.dumps({"error": "no solution.py"})); sys.exit(0)
results = []
for path in hid:
    spec = importlib.util.spec_from_file_location("h_" + path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        results.append({"file": path.name, "check": "<import>", "ok": False,
                        "err": f"{type(e).__name__}: {e}"}); continue
    checks = [(n, v) for n, v in vars(mod).items()
              if n.startswith("check_") and callable(v)]
    if not checks:
        main = getattr(mod, "main", None)
        checks = [("<main>", main)] if callable(main) else []
    for name, fn in checks:
        try:
            fn()
        except Exception as e:
            results.append({"file": path.name, "check": name, "ok": False,
                            "err": f"{type(e).__name__}: {str(e)[:200]}"})
        else:
            results.append({"file": path.name, "check": name, "ok": True})
print("<<<GRADE_JSON>>>" + json.dumps(results))
'''


def grade_cell(cell: pathlib.Path) -> dict:
    task = cell.name.split("__")[0]
    arm = cell.name.split("__")[1]
    ws = cell / "workspace"
    sol = ws / "solution.py"

    with tempfile.TemporaryDirectory(prefix=f"grade_{task}_{arm}_") as td:
        g = pathlib.Path(td)
        if sol.is_file():
            shutil.copy2(sol, g / "solution.py")
        for h in (HIDDEN / task).glob("test_hidden*.py"):
            shutil.copy2(h, g / h.name)
        (g / "_grader.py").write_text(GRADER, encoding="utf-8")
        proc = subprocess.run([sys.executable, "_grader.py"], cwd=g,
                              capture_output=True, text=True, timeout=600)

    raw = ""
    for line in proc.stdout.splitlines():
        if line.startswith("<<<GRADE_JSON>>>"):
            raw = line[len("<<<GRADE_JSON>>>"):]
    if not raw:
        # The grader could not produce a verdict. The overwhelmingly common cause
        # is that the agent delivered no solution.py. That is a FAILURE, not a
        # missing observation, and it stays in the denominator either way -- but
        # the two are different claims so both are recorded.
        meta_p0 = cell / "meta.json"
        m0 = json.loads(meta_p0.read_text()) if meta_p0.is_file() else {}
        rec = {"cell": cell.name, "task": task, "arm": arm,
               "has_solution": sol.is_file(),
               "grader_error": True, "grader_stderr": proc.stderr[-300:],
               "checks_total": 0, "checks_passed": 0,
               "hidden_pass": False,
               "delivered": bool(sol.is_file()) and arm == "A",
               "agent_rc": m0.get("agent_rc"), "timed_out": bool(m0.get("timed_out")),
               "wall_s": m0.get("wall_s"),
               "gate_verdict": ("agent produced no solution.py"
                                if not sol.is_file() else "grader failed on a present file"),
               "failing": ["<no solution.py delivered>"] if not sol.is_file() else ["<grader error>"]}
        if arm == "C":
            jp = cell / "judge.json"
            if jp.is_file():
                j = json.loads(jp.read_text())
                rp = cell / "release.json"
                rec["delivered"] = bool(json.loads(rp.read_text()).get("released")) \
                    if rp.is_file() else j.get("outcome") == "accept"
                rec["gate_verdict"] = "{} (no file to verify)".format(j.get("outcome"))
        rec["correct"] = bool(rec["delivered"] and rec["hidden_pass"])
        rec["refusal_reason"] = None if rec["correct"] else rec.get("gate_verdict")
        (cell / "grade.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False))
        return rec

    checks = json.loads(raw)
    n_ok = sum(1 for c in checks if c["ok"])
    hidden_pass = bool(checks) and n_ok == len(checks)

    # Did the gate actually let this deliver? Arm-specific, because the two
    # vacant shapes report differently and collapsing them would hide which
    # mechanism did the refusing.
    delivered, refusal, gate_verdict = True, None, "none (no gate in this arm)"
    if arm == "C":
        jp = cell / "judge.json"
        rp = cell / "release.json"
        if jp.is_file():
            j = json.loads(jp.read_text())
            gate_verdict = j.get("outcome")
            if rp.is_file():
                r = json.loads(rp.read_text())
                delivered = bool(r.get("released"))
                refusal = None if delivered else (j.get("outcome") or "not_released")
                gate_verdict = "{} -> released={} readback_ok={}".format(
                    j.get("outcome"), r.get("released"), r.get("readback_ok"))
            else:
                delivered = j.get("outcome") == "accept"
                refusal = None if delivered else (j.get("outcome") or "judge_failed")
        else:
            delivered, refusal = False, "no_judge"
    elif arm == "B":
        # Vacant's native plugin is installed. On opencode it records the trace
        # but never reaches the Stop check, so it can decline nothing; the
        # verdict field records that rather than implying a gate ran.
        sp = cell / "vacant" / "summary.json"
        if sp.is_file():
            d = json.loads(sp.read_text())
            delivered = bool(d.get("accepted"))
            refusal = d.get("stop_reason")
            gate_verdict = "{} stop={}".format(d.get("accepted"), d.get("stop_reason"))
        else:
            tr = cell / "vacant_home_trace" / "projects"
            nproj = len(list(tr.iterdir())) if tr.exists() else 0
            gate_verdict = ("trace-only: {} project(s) recorded, no stop check "
                            "(opencode plugin registers no stop-equivalent hook)"
                            ).format(nproj)

    meta_p = cell / "meta.json"
    meta = json.loads(meta_p.read_text()) if meta_p.is_file() else {}
    rec = {
        "cell": cell.name, "task": task, "arm": arm,
        "agent_rc": meta.get("agent_rc"),
        "timed_out": bool(meta.get("timed_out")),
        "wall_s": meta.get("wall_s"),
        "gate_verdict": gate_verdict,
        "has_solution": sol.is_file(),
        "checks_total": len(checks), "checks_passed": n_ok,
        "hidden_pass": hidden_pass,
        "delivered": delivered,
        "correct": bool(delivered and hidden_pass),
        "refusal_reason": refusal,
        "failing": [f"{c['file']}::{c['check']}" for c in checks if not c["ok"]][:8],
    }
    (cell / "grade.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", default=None)
    ap.add_argument("--root", default=None, help="runs root (default runs/)")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    root = pathlib.Path(a.root) if a.root else RUNS
    cells = ([root / a.cell] if a.cell else
             sorted(p for p in root.iterdir() if p.is_dir() and "__" in p.name))
    for c in cells:
        if not c.is_dir():
            continue
        if (c / "grade.json").exists():
            print(f"skip (already graded) {c.name}")
            continue
        r = grade_cell(c)
        print(json.dumps({k: r.get(k) for k in
                          ("cell", "hidden_pass", "delivered", "correct",
                           "checks_passed", "checks_total", "refusal_reason")},
                         ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
