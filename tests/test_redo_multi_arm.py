"""ops/redo/analysis/multi_arm.py：多臂預註冊的配對、Holm 校正與 state（rfh4，2026-11-25）。"""
from __future__ import annotations

import importlib.util
import json
import pathlib

_spec = importlib.util.spec_from_file_location(
    "multi_arm", pathlib.Path(__file__).resolve().parents[1] / "ops" / "redo" / "analysis" / "multi_arm.py")
ma = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ma)

COMPS = [{"name": "RF_vs_R", "control": "R", "treatment": "RF"},
         {"name": "H_vs_A", "control": "A", "treatment": "H"},
         {"name": "R_vs_A", "control": "A", "treatment": "R"}]


def _run(tmp: pathlib.Path, tasks: list[str], reps: int, passes: dict, void: set = frozenset(), hints=None):
    plan = {"id": "t", "tasks": tasks, "reps": reps, "arms": {k: {} for k in ("A", "H", "R", "RF")},
            "analysis": {"alpha": 0.05, "comparisons": COMPS}}
    (tmp / "RUN.json").write_text(json.dumps({"plan": plan, "plan_sha256": "S"}))
    for (t, r, arm), ok in passes.items():
        d = tmp / "cells" / t / f"r{r}" / arm
        d.mkdir(parents=True)
        (d / "cell.json").write_text(json.dumps({
            "task": t, "rep": r, "arm": arm, "plan_sha256": "S", "provider": "p1", "pass": ok, "accepted": ok,
            "grader_kind": "scorer", "n_attempts": 1, "infra_void": "x" if (t, r, arm) in void else None}))
        (d / "attempt_1").mkdir()
        h = (hints or {}).get(arm)
        (d / "attempt_1" / "attempt.json").write_text(json.dumps({"hint_bytes": len(h.encode()) if h else 0,
                                                                  "hint_text": h}))
    return ma.load(tmp)


def test_holm_steps_down_and_stops():
    assert ma.holm({"a": 0.01, "b": 0.02, "c": 0.04}, 0.05) == {"a": True, "b": True, "c": True}
    assert ma.holm({"a": 0.01, "b": 0.03, "c": 0.04}, 0.05) == {"a": True, "b": False, "c": False}
    assert ma.holm({"a": 0.02, "b": 0.001, "c": 0.9}, 0.05) == {"a": True, "b": True, "c": False}


def test_mcnemar_matches_harness():
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ops" / "redo"))
    import redo
    for b, c in [(0, 0), (6, 29), (11, 34), (3, 5), (17, 1)]:
        assert ma.mcnemar_exact(b, c) == redo.mcnemar_exact(b, c)


def test_pairs_per_comparison_and_void_exclusion(tmp_path):
    tasks = [f"t{i}" for i in range(20)]
    passes = {}
    for t in tasks:
        passes[(t, 1, "A")] = False
        passes[(t, 1, "H")] = False
        passes[(t, 1, "R")] = True
        passes[(t, 1, "RF")] = True
    run, cells = _run(tmp_path, tasks, 1, passes, void={("t0", 1, "H")}, hints={"RF": "x" * 397})
    out = ma.analyse(run, cells)
    c = out["comparisons"]
    assert c["R_vs_A"]["c"] == 20 and c["R_vs_A"]["b"] == 0 and c["R_vs_A"]["state"] == "EFFECTIVE"
    assert c["H_vs_A"]["pairs"] == 19 and c["H_vs_A"]["excluded_void_pairs"] == 1   # void 只影響含 H 的比較
    assert c["H_vs_A"]["state"] == "UNRESOLVED"
    assert c["RF_vs_R"]["pairs"] == 20 and c["RF_vs_R"]["state"] == "UNRESOLVED"
    assert out["arms"]["RF"]["attempts_with_hint"] == 20 and out["arms"]["R"]["attempts_with_hint"] == 0
    assert out["arms"]["RF"]["hints_at_cap"] == 20 and out["arms"]["RF"]["hints_no_expected_value"] == 20


def test_hint_with_assertion_is_not_counted_as_missing_expected(tmp_path):
    tasks = [f"t{i}" for i in range(3)]
    passes = {(t, 1, a): False for t in tasks for a in ("A", "H", "R", "RF")}
    run, cells = _run(tmp_path, tasks, 1, passes, hints={"RF": "First failing test output:\nAssertionError: 1 != 2"})
    arm = ma.analyse(run, cells)["arms"]["RF"]
    assert arm["hints_no_expected_value"] == 0 and arm["hints_at_cap"] == 0 and arm["hints_text_known"] == 3


def test_incomplete_and_contradicts(tmp_path):
    tasks = [f"t{i}" for i in range(20)]
    passes = {(t, 1, a): (a == "A") for t in tasks for a in ("A", "H", "R", "RF")}
    del passes[("t3", 1, "RF")]
    run, cells = _run(tmp_path, tasks, 1, passes)
    c = ma.analyse(run, cells)["comparisons"]
    assert c["RF_vs_R"]["state"] == "INCOMPLETE"
    assert c["H_vs_A"]["state"] == "CONTRADICTS" and c["R_vs_A"]["state"] == "CONTRADICTS"
