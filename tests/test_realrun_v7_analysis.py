"""Pin-test for the v7 (cross-model replication) analysis path.

Prereg: ops/realrun/prereg_v7.json (committed before the first v7 model call).
v7's decision states are REPLICATED / CONTRADICTS / NOT_REPLICATED / INCOMPLETE
(same RULE as v3–v6: c > b & p < 0.05 / b > c & p < 0.05 / otherwise).
This pins that prereg_analyze.py takes the state LABELS from the plan file
(itself, not from a hardcoded v3-era name), and that monitor_v6.py --batch v7
reads the v7 run roots and points at prereg_v7.json / analyze_v7.json.
Synthetic roots in a temp dir; no model calls.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "ops" / "realrun"))
import prereg_analyze as pa  # noqa: E402
import monitor_v6 as mon  # noqa: E402

PY = sys.executable

TASKS = [f"t{i}" for i in range(8)]
ARMS = ("A_none", "B_resample3")


def _mk(root: Path, arm: str, task: str, accepted: bool) -> None:
    d = root / arm / task / "run"
    d.mkdir(parents=True, exist_ok=True)
    (d / "run_X.json").write_text(json.dumps(
        {"accepted": accepted, "infra_void": None,
         "attempts": [{"stop_reason": "visible_pass" if accepted
                       else "visible_fail"}]}),
        encoding="utf-8")


def _plan(d: Path, states: dict, reps: int = 1) -> Path:
    f = d / "prereg.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({
        "id": "v7test",
        "fixed": {"tasks": TASKS,
                  "arms": {a: [] for a in ARMS}, "reps": reps},
        "analysis": {"alpha": 0.05},
        "decision_states": states,
        "known_caveats": [],
    }), encoding="utf-8")
    return f


def _rep(root: Path, pattern: str) -> None:
    """pattern over 8 tasks: 'ab' = A-pass/B-fail, 'ca' = A-fail/B-pass,
    'aa' = both pass, 'dd' = both fail. Exactly 2 of each kind ->
    (b=2, c=2, a=2, d=2), p = 1.0 (symmetric) -> the NULL state in either
    naming; we then flip to a decisive pattern for the positive/negative
    states."""
    kinds = ["aa", "dd", "ab", "ab", "ca", "ca", "aa", "dd"]
    for t, k in zip(TASKS, kinds):
        A = k in ("ab", "aa")
        B = k in ("ca", "aa")
        _mk(root, ARMS[0], t, A)
        _mk(root, ARMS[1], t, B)


def _decisive(root: Path, positive: bool) -> None:
    """positive: A fail / B pass on all 8 -> (b=0, c=8), p=0.00390625 < 0.05.
    negative: A pass / B fail on all 8 -> (b=8, c=0), p=0.00390625 < 0.05."""
    for t in TASKS:
        _mk(root, ARMS[0], t, not positive)
        _mk(root, ARMS[1], t, positive)


V7_STATES = {"REPLICATED": "", "CONTRADICTS": "", "NOT_REPLICATED": "",
             "INCOMPLETE": ""}
V6_STATES = {"EFFECTIVE": "", "CONTRADICTS": "", "UNRESOLVED": "",
             "INCOMPLETE": ""}


def test_analyzer_v7_labels_positive(tmp_path: Path) -> None:
    r1 = tmp_path / "r1"
    _decisive(r1, positive=True)
    rep = pa.analyze(_plan(tmp_path / "p", V7_STATES), [r1])
    assert rep["pooled"]["c"] == 8 and rep["pooled"]["b"] == 0
    assert rep["state"] == "REPLICATED"


def test_analyzer_v7_labels_null_and_contradicts(tmp_path: Path) -> None:
    r1 = tmp_path / "r1"
    _rep(r1, "symmetric")  # b=c=2 -> p=1.0 -> null state
    plan = _plan(tmp_path / "p", V7_STATES)
    rep = pa.analyze(plan, [r1])
    assert rep["state"] == "NOT_REPLICATED"

    r2 = tmp_path / "r2"
    _decisive(r2, positive=False)
    rep3 = pa.analyze(plan, [r2])
    assert rep3["state"] == "CONTRADICTS"


def test_analyzer_v6_labels_unchanged(tmp_path: Path) -> None:
    r1 = tmp_path / "r1"
    _decisive(r1, positive=True)
    rep = pa.analyze(_plan(tmp_path / "p", V6_STATES), [r1])
    assert rep["state"] == "EFFECTIVE"
    r2 = tmp_path / "r2"
    _rep(r2, "symmetric")
    rep4 = pa.analyze(_plan(tmp_path / "p6b", V6_STATES), [r2])
    assert rep4["state"] == "UNRESOLVED"


def test_analyzer_v7_incomplete_rule(tmp_path: Path) -> None:
    r1 = tmp_path / "r1"
    _decisive(r1, positive=True)
    plan = _plan(tmp_path / "p", V7_STATES, reps=5)
    rep = pa.analyze(plan, [r1])
    assert rep["state"] == "INCOMPLETE"
    assert "no decision state" in rep["state_note"]


def _monitor_env(base: Path, batch: str, complete: bool) -> None:
    rows = []
    for t in range(34):
        for arm in ARMS:
            rows.append({"task": f"pg_{t:02d}", "arm": arm, "exit": 0,
                         "wall_s": 1.0, "accepted": True,
                         "refused": False, "infra_void": None,
                         "n_attempts": 1, "stop_reason": "visible_pass",
                         "requests_seen": 1})
    if not complete:
        rows = rows[:34]  # one arm's worth -> 34/68, in progress
    for k in range(1, 6):
        root = base / f"runs_{batch}_r{k}"
        root.mkdir(parents=True, exist_ok=True)
        (root / "progress.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n")


def _run_monitor(base: Path, batch: str | None) -> str:
    cmd = [PY, str(HERE / "ops" / "realrun" / "monitor_v6.py"),
           "--runs-root", str(base)]
    if batch:
        cmd += ["--batch", batch]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                       cwd=str(HERE))
    assert p.returncode == 0, p.stderr
    return p.stdout


def test_monitor_v7_complete_points_at_v7_files(tmp_path: Path) -> None:
    _monitor_env(tmp_path, "v7", complete=True)
    out = _run_monitor(tmp_path, "v7")
    assert "READY_TO_ANALYZE" in out
    assert "prereg_v7.json" in out and "analyze_v7.json" in out
    assert "runs_v7_r5" in out
    assert "launch_v6.sh" not in out


def test_monitor_v7_partial_is_not_ready(tmp_path: Path) -> None:
    _monitor_env(tmp_path, "v7", complete=False)
    out = _run_monitor(tmp_path, "v7")
    assert "NOT_READY" in out
    assert "READY_TO_ANALYZE" not in out
    assert "launch_v7.sh" in out


def test_monitor_default_still_v6(tmp_path: Path) -> None:
    # no --batch: default is v6 (existing pinned behavior)
    _monitor_env(tmp_path, "v6", complete=True)
    out = _run_monitor(tmp_path, None)
    assert "READY_TO_ANALYZE" in out
    assert "prereg_v6.json" in out and "analyze_v6.json" in out
