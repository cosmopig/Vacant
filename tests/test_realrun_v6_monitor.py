"""Pin-test for ops/realrun/monitor_v6.py (v6 interim health monitor).

The monitor is read-only and must:
  * report per-rep completeness against 68 cells (34 tasks x 2 arms);
  * compute the INTERIM (b, c, a, d) pair counts correctly (definition from
    prereg_v6.json: b = A pass & B fail, c = A fail & B pass);
  * print READY_TO_ANALYZE only when all 5 reps are complete;
  * never invent a decision state (INCOMPLETE rule).
Synthetic progress.jsonl files live in a temp dir; no model calls.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
MONITOR = HERE / "ops" / "realrun" / "monitor_v6.py"

TASKS = [f"pg_task_{i:02d}" for i in range(34)]
PY = sys.executable


def _cell(task: str, arm: str, accepted: bool) -> dict:
    return {"task": task, "arm": arm, "exit": 0 if accepted else 20,
            "wall_s": 1.0, "accepted": accepted, "refused": not accepted,
            "infra_void": None, "n_attempts": 1,
            "stop_reason": "visible_pass" if accepted else "visible_fail",
            "requests_seen": 1}


def _write_rep(root: Path, accepted_map: dict[tuple[str, str], bool] | None = None,
               cells: int | None = None) -> None:
    """Write a rep's progress.jsonl. accepted_map: (task, arm) -> accepted."""
    rows = []
    for t in TASKS:
        for arm in ("A_none", "B_resample3"):
            if accepted_map is None or (t, arm) in accepted_map:
                acc = accepted_map[(t, arm)] if accepted_map else False
                rows.append(_cell(t, arm, acc))
    if cells is not None:
        rows = rows[:cells]
    root.mkdir(parents=True, exist_ok=True)
    (root / "progress.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")


def _run_monitor(base: Path) -> str:
    p = subprocess.run([PY, str(MONITOR), "--runs-root", str(base)],
                       capture_output=True, text=True, timeout=60, cwd=str(HERE))
    assert p.returncode == 0, p.stderr
    return p.stdout


def test_partial_rep_is_in_progress_and_never_ready(tmp_path: Path) -> None:
    # rep 1 complete with a known pair pattern; rep 2 partial; 3-5 missing
    acc: dict[tuple[str, str], bool] = {}
    for i, t in enumerate(TASKS):
        if i < 10:      # both pass (a=10)
            acc[(t, "A_none")] = True
            acc[(t, "B_resample3")] = True
        elif i < 12:    # b: A pass, B fail  (2 tasks)
            acc[(t, "A_none")] = True
            acc[(t, "B_resample3")] = False
        elif i < 17:    # c: A fail, B pass  (5 tasks)
            acc[(t, "A_none")] = False
            acc[(t, "B_resample3")] = True
        else:           # both fail (d=17)
            acc[(t, "A_none")] = False
            acc[(t, "B_resample3")] = False
    _write_rep(tmp_path / "runs_v6_r1", acc)
    _write_rep(tmp_path / "runs_v6_r2", cells=10)  # partial

    out = _run_monitor(tmp_path)
    assert "r1: COMPLETE" in out
    # (b=2, c=5, a=10, d=17, n=34); mcnemar_exact(2,5) = min(1, 2*29/128) = 0.453125
    assert "INTERIM(b=2,c=5,a=10,d=17,n=34, p=0.4531)" in out
    assert "descriptive only" in out
    assert "r2: in progress (10/68)" in out
    assert "r3: not started" in out
    assert "r5: not started" in out
    assert "TOTAL: 78/340 cells" in out
    assert "NOT_READY" in out
    assert "READY_TO_ANALYZE" not in out


def test_all_reps_complete_prints_ready_and_command(tmp_path: Path) -> None:
    acc: dict[tuple[str, str], bool] = {}
    for t in TASKS:
        acc[(t, "A_none")] = True
        acc[(t, "B_resample3")] = True
    for k in range(1, 6):
        _write_rep(tmp_path / f"runs_v6_r{k}", dict(acc))
    out = _run_monitor(tmp_path)
    assert "READY_TO_ANALYZE" in out
    assert "TOTAL: 340/340 cells" in out
    assert "prereg_analyze.py --prereg ops/realrun/prereg_v6.json" in out
    assert "runs_v6_r5" in out and "analyze_v6.json" in out


def test_infra_void_counted_per_arm(tmp_path: Path) -> None:
    root = tmp_path / "runs_v6_r1"
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, t in enumerate(TASKS):
        for arm in ("A_none", "B_resample3"):
            r = _cell(t, arm, False)
            if i == 0 and arm == "B_resample3":
                r["infra_void"] = "model_call_failed"
            rows.append(r)
    (root / "progress.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")
    out = _run_monitor(tmp_path)
    assert "B_resample3: 0pass/34fail/1void" in out
    assert "A_none: 0pass/34fail" in out


def test_missing_runs_root_exits_2(tmp_path: Path) -> None:
    p = subprocess.run([PY, str(MONITOR), "--runs-root", str(tmp_path / "nope")],
                       capture_output=True, text=True, timeout=60, cwd=str(HERE))
    assert p.returncode == 2
    assert "runs root not found" in p.stderr
