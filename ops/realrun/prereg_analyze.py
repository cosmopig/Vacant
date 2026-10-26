#!/usr/bin/env python3
"""Pre-registered analysis for the v3 live-resample batch (ops/realrun/prereg_v3.json).

The plan file was committed BEFORE the first model call. This tool reads the
plan, reads the on-disk run roots, computes EXACTLY the pre-registered
statistic (exact two-sided McNemar on (task, rep) pairs, via the project's own
`vacant_network.research.mcnemar_exact`), and applies the pre-registered
decision states. Nothing here invents a threshold or a state: both come from
the plan file. If fewer roots than registered reps are given, the batch is
INCOMPLETE and no decision state is assigned (pre-registered budget rule).

Usage:
  python3 ops/realrun/prereg_analyze.py --prereg ops/realrun/prereg_v3.json \
      --roots <root_r1> <root_r2> <root_r3> [--json out.json]
  python3 ops/realrun/prereg_analyze.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

try:
    import vacant_network  # noqa: F401
except ImportError:  # pragma: no cover - depends on install layout
    sys.path.insert(0, str(HERE.parent.parent))

from vacant_network.research import mcnemar_exact  # noqa: E402


def read_run(root: Path, arm: str, task: str) -> dict:
    """One run's summary, reduced to what the pre-registered outcome needs."""
    run_dir = root / arm / task / "run"
    files = sorted(run_dir.glob("run_*.json"))
    files = [f for f in files if "receipts" not in f.name]
    if not files:
        return {"present": False, "accepted": None, "infra_void": True,
                "stop_reason": None}
    s = json.loads(files[0].read_text(encoding="utf-8"))
    return {
        "present": True,
        "accepted": s.get("accepted") is True,
        "infra_void": bool(s.get("infra_void")),
        "stop_reason": (s.get("attempts") or [{}])[-1].get("stop_reason")
        if s.get("attempts") else s.get("stop_reason"),
    }


def rep_pairs(root: Path, tasks: list[str], arm_a: str, arm_b: str) -> dict:
    """Paired outcomes for one rep. infra_void on either side drops the pair."""
    pairs, voids = [], []
    for t in tasks:
        a = read_run(root, arm_a, t)
        b = read_run(root, arm_b, t)
        if not (a["present"] and b["present"]):
            voids.append({"task": t, "reason": "missing_run_dir"})
            continue
        if a["infra_void"] or b["infra_void"]:
            voids.append({"task": t, "reason": "infra_void",
                          "a": a, "b": b})
            continue
        pairs.append({"task": t, "a": a["accepted"], "b": b["accepted"]})
    return {"pairs": pairs, "voids": voids}


def discordant(pairs: list[dict]) -> tuple[int, int]:
    b = sum(1 for p in pairs if p["a"] and not p["b"])
    c = sum(1 for p in pairs if p["b"] and not p["a"])
    return b, c


def decision_state(c: int, b: int, p: float, alpha: float) -> str:
    """Exactly the pre-registered rule (see prereg_v3.json decision_states)."""
    if p < alpha and c > b:
        return "EFFECTIVE"
    if p < alpha and c < b:
        return "CONTRADICTS"
    return "UNRESOLVED"


def analyze(prereg_path: Path, roots: list[Path]) -> dict:
    plan = json.loads(prereg_path.read_text(encoding="utf-8"))
    tasks = plan["fixed"]["tasks"]
    arms = plan["fixed"]["arms"]
    arm_a, arm_b = sorted(arms)  # A_none < B_resample3
    alpha = float(plan["analysis"].get("alpha", 0.05))
    reps_registered = int(plan["fixed"]["reps"])

    per_rep = []
    for i, root in enumerate(roots, 1):
        rp = rep_pairs(root, tasks, arm_a, arm_b)
        b, c = discordant(rp["pairs"])
        p = mcnemar_exact(b, c)
        per_rep.append({
            "rep": i, "root": str(root), "n_pairs": len(rp["pairs"]),
            "b": b, "c": c, "p": p, "voids": rp["voids"],
            "a_acc": sum(1 for x in rp["pairs"] if x["a"]),
            "b_acc": sum(1 for x in rp["pairs"] if x["b"]),
        })
    # pooled: all reps' pairs concatenated (the pre-registered primary unit)
    all_pairs = []
    for root in roots:
        all_pairs.extend(rep_pairs(root, tasks, arm_a, arm_b)["pairs"])
    b, c = discordant(all_pairs)
    p = mcnemar_exact(b, c)

    if len(roots) < reps_registered:
        state = "INCOMPLETE"
        note = (f"{len(roots)}/{reps_registered} registered reps present; "
                "pre-registered budget rule: no decision state assigned")
    else:
        state = decision_state(c, b, p, alpha)
        note = "all registered reps present"
    return {
        "prereg_id": plan.get("id"),
        "prereg_file": str(prereg_path),
        "alpha": alpha,
        "arm_a": arm_a, "arm_b": arm_b,
        "n_pairs": len(all_pairs),
        "n_runs_per_arm": len(all_pairs),
        "per_rep": per_rep,
        "pooled": {"b": b, "c": c, "p": p},
        "state": state,
        "state_note": note,
        "states_from_plan": plan["decision_states"],
        # v5 prereg carries its caveats under "honesty" (frozen file; no key
        # added after the fact). Earlier preregs use "known_caveats". Neither
        # is normative for the decision; both are just carried through.
        "caveats": plan.get("known_caveats", plan.get("honesty", [])),
    }


def selftest() -> int:
    """Known (b,c) fixtures -> known p and state; negative control: flip one
    summary and the answer MUST change (proves the tool reads the files)."""
    tasks = [f"t{i}" for i in range(6)]
    arms = ["A", "B"]

    def mk(root: Path, arm: str, task: str, accepted: bool) -> None:
        d = root / arm / task / "run"
        d.mkdir(parents=True, exist_ok=True)
        (d / "run_X.json").write_text(json.dumps(
            {"accepted": accepted, "infra_void": None,
             "attempts": [{"stop_reason": "visible_pass" if accepted
                           else "visible_fail"}]}),
            encoding="utf-8")

    def mkplan(d: Path, reps: int) -> Path:
        plan = {
            "id": "selftest",
            "fixed": {"tasks": tasks, "arms": {a: [] for a in arms},
                      "reps": reps},
            "analysis": {"alpha": 0.05},
            "decision_states": {"EFFECTIVE": "", "CONTRADICTS": "",
                                "UNRESOLVED": "", "INCOMPLETE": ""},
            "known_caveats": [],
        }
        f = d / "prereg.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(plan), encoding="utf-8")
        return f

    fails = []

    def check(name: str, cond: bool) -> None:
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")
        if not cond:
            fails.append(name)

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        # case 1: all 6 pairs A fail / B pass -> (b=0,c=6), p=2*0.5^6
        r1 = base / "r1"
        for t in tasks:
            mk(r1, "A", t, False)
            mk(r1, "B", t, True)
        plan = mkplan(base, reps=1)
        rep = analyze(plan, [r1])
        check("c1 b=0,c=6", (rep["pooled"]["b"], rep["pooled"]["c"]) == (0, 6))
        check("c1 p=0.03125", abs(rep["pooled"]["p"] - 0.03125) < 1e-12)
        check("c1 EFFECTIVE", rep["state"] == "EFFECTIVE")

        # negative control: make t0 (A pass, B fail) -> (b=1,c=5), p=0.21875,
        # state MUST drop from EFFECTIVE (proves the tool reads the summaries)
        mk(r1, "A", "t0", True)
        mk(r1, "B", "t0", False)
        rep2 = analyze(plan, [r1])
        check("nc b=1,c=5", (rep2["pooled"]["b"], rep2["pooled"]["c"]) == (1, 5))
        check("nc p=0.21875", abs(rep2["pooled"]["p"] - 0.21875) < 1e-12)
        check("nc state flipped to UNRESOLVED", rep2["state"] == "UNRESOLVED")

        # case 2: reversed -> (b=6,c=0) -> CONTRADICTS (direction guard)
        r2 = base / "r2"
        for t in tasks:
            mk(r2, "A", t, True)
            mk(r2, "B", t, False)
        rep3 = analyze(plan, [r2])
        check("c2 CONTRADICTS", rep3["state"] == "CONTRADICTS")

        # case 3: (b=2,c=4) -> p=2*(1+6+15)/64=0.6875 -> UNRESOLVED
        r3 = base / "r3"
        for i, t in enumerate(tasks):
            mk(r3, "A", t, i >= 2)   # t0,t1 fail A ; all pass except? see below
            mk(r3, "B", t, i < 4)    # t0..t3 pass B
        # A: t0 F t1 F t2 T t3 T t4 T t5 T ; B: t0 T t1 T t2 T t3 T t4 F t5 F
        # discordant: (A T,B F): t4,t5 -> b=2 ; (A F,B T): t0,t1 -> c=2 ; n=4
        # p = min(1, 2*(C(4,0)+C(4,1)+C(4,2))/16) = min(1, 22/16) = 1.0 (capped)
        rep4 = analyze(plan, [r3])
        check("c3 b=2,c=2 p=1.0 UNRESOLVED",
              (rep4["pooled"]["b"], rep4["pooled"]["c"]) == (2, 2)
              and abs(rep4["pooled"]["p"] - 1.0) < 1e-12
              and rep4["state"] == "UNRESOLVED")

        # case 4: infra_void on one side -> pair dropped, voids reported
        r4 = base / "r4"
        for t in tasks:
            mk(r4, "A", t, True)
            mk(r4, "B", t, True)
        d = r4 / "B" / "t5" / "run"
        (d / "run_X.json").write_text(json.dumps(
            {"accepted": None, "infra_void": "model_error",
             "attempts": [{"stop_reason": "infra_void"}]}), encoding="utf-8")
        rep5 = analyze(plan, [r4])
        check("c4 void pair dropped", rep5["n_pairs"] == 5
              and len(rep5["per_rep"][0]["voids"]) == 1
              and rep5["per_rep"][0]["voids"][0]["reason"] == "infra_void")

        # case 5: registered reps=3, only 2 roots -> INCOMPLETE, no state
        plan3 = mkplan(base / "p3", reps=3)
        rep6 = analyze(plan3, [r1, r2])
        check("c5 INCOMPLETE", rep6["state"] == "INCOMPLETE"
              and "no decision state" in rep6["state_note"])

    if fails:
        print(f"SELFTEST FAIL: {fails}")
        return 1
    print("SELFTEST PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prereg", required=False)
    ap.add_argument("--roots", nargs="*", default=[])
    ap.add_argument("--json", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.prereg or not a.roots:
        ap.error("--prereg and --roots are required (or --selftest)")
    rep = analyze(Path(a.prereg), [Path(r) for r in a.roots])
    out = json.dumps(rep, ensure_ascii=False, indent=1)
    if a.json:
        Path(a.json).write_text(out + "\n", encoding="utf-8")
    print(out)
    print(f"STATE: {rep['state']}  ({rep['state_note']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
