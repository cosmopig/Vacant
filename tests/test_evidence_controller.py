"""Unit tests for the frozen evidence controller in vacant_network.controller."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from ops.e1 import assert_ks1_clean as e1_assert_ks1_clean
from vacant_network.controller import (
    ACTION_CONTINUE,
    ACTION_DELIVER_BEST_BUDGET,
    ACTION_REPAIR,
    ACTION_RESTART_FRESH,
    ACTION_RESTORE_BEST,
    ACTION_STOP_SUCCESS,
    CONTROLLER_ACTION_LINES,
    CONTROLLER_ACTIONS,
    FEEDBACK_MAX_BYTES,
    REPAIR_PASS_RATIO,
    STUCK_CONSECUTIVE_SIGNATURE,
    build_controller_feedback,
    build_feedback,
    controller_event,
    decide,
    reconstruct,
    save_controller_chain,
)
from vacant_network.identity import Identity, PublicIdentity
from vacant_network.logbook import ChainError, Logbook
from vacant_network.memory import assert_ks1_clean as mem_assert_ks1_clean


def _att(passed: int, total: int, failing: list[str] | None = None, *, accepted: bool | None = None,
         first_problem: str | None = None, status: str = "ok") -> dict:
    failing = list(failing or [])
    tests: dict[str, bool] = {}
    for i in range(passed):
        tests[f"test_pass_{i}"] = True
    for name in failing:
        tests[name] = False
    while len(tests) < total:
        tests[f"test_fail_{len(tests)}"] = False
    return {
        "tests": tests,
        "passed": passed,
        "total": total,
        "accepted": (total > 0 and passed == total) if accepted is None else accepted,
        "status": status,
        "first_problem": first_problem,
    }


def test_frozen_thresholds_and_ks1_clean():
    assert REPAIR_PASS_RATIO == 0.70
    assert STUCK_CONSECUTIVE_SIGNATURE == 2
    assert FEEDBACK_MAX_BYTES == 400
    assert CONTROLLER_ACTIONS == {
        "stop_success",
        "deliver_best_budget",
        "restore_best",
        "restart_fresh",
        "repair",
        "continue",
    }
    for action, line in CONTROLLER_ACTION_LINES.items():
        assert "\n" not in line
        mem_assert_ks1_clean(line)
        e1_assert_ks1_clean(line)
        fb = build_controller_feedback(action, ["test_a"], "AssertionError: 1 != 2")
        mem_assert_ks1_clean(fb)
        e1_assert_ks1_clean(fb)


def test_rule_1_stop_success():
    d = decide(
        _att(10, 10),
        history=[],
        best=None,
        remaining_attempts=2,
        remaining_budget_s=1200.0,
    )
    assert d.action == ACTION_STOP_SUCCESS
    assert d.rule == 1
    assert d.delivered_index == 0
    assert d.evidence["accepted"] is True
    assert d.evidence["unsatisfied"] == []


def test_rule_2_deliver_best_budget_attempts_and_wall():
    a1 = _att(6, 10, ["t1", "t2", "t3", "t4"])
    a2 = _att(4, 10, ["t1", "t2", "t3", "t4", "t5", "t6"])
    # Exhausted attempts: should deliver attempt 1 (index 0) because 6 > 4.
    d = decide(a2, history=[a1], best=a1, remaining_attempts=0, remaining_budget_s=500.0)
    assert d.action == ACTION_DELIVER_BEST_BUDGET
    assert d.rule == 2
    assert d.delivered_index == 0
    assert d.evidence["delivered_attempt"] == 1
    assert d.evidence["unsatisfied"] == ["t1", "t2", "t3", "t4"]

    # Tie on passed count -> latest wins (index 1).
    a2_tie = _att(6, 10, ["t5", "t6", "t7", "t8"])
    d_tie = decide(a2_tie, history=[a1], best=a1, remaining_attempts=0, remaining_budget_s=500.0)
    assert d_tie.action == ACTION_DELIVER_BEST_BUDGET
    assert d_tie.rule == 2
    assert d_tie.delivered_index == 1
    assert d_tie.evidence["unsatisfied"] == ["t5", "t6", "t7", "t8"]

    # Exhausted wall budget (< min_attempt_s) -> rule 2 even with remaining attempts.
    d_wall = decide(a1, history=[], best=None, remaining_attempts=2, remaining_budget_s=30.0, min_attempt_s=60.0)
    assert d_wall.action == ACTION_DELIVER_BEST_BUDGET
    assert d_wall.rule == 2
    assert d_wall.delivered_index == 0


def test_rule_3_restore_best():
    a1 = _att(7, 10, ["t1", "t2", "t3"])
    a2 = _att(5, 10, ["t1", "t2", "t3", "t4", "t5"])
    d = decide(a2, history=[a1], best=a1, remaining_attempts=1, remaining_budget_s=600.0)
    assert d.action == ACTION_RESTORE_BEST
    assert d.rule == 3
    assert d.feedback_source == "best"
    assert d.evidence["worse_than_best"] is True


def test_rule_4_restart_fresh_stuck():
    a1 = _att(4, 10, ["t1", "t2", "t3", "t4", "t5", "t6"])
    a2 = _att(4, 10, ["t1", "t2", "t3", "t4", "t5", "t6"])
    d = decide(a2, history=[a1], best=a1, remaining_attempts=1, remaining_budget_s=600.0)
    assert d.action == ACTION_RESTART_FRESH
    assert d.rule == 4
    assert d.evidence["consecutive_same_signature"] == 2
    assert d.evidence["no_progress_stuck"] is True


def test_rule_5_repair_threshold_70_percent():
    # Exactly 70% (7/10) -> repair.
    d70 = decide(_att(7, 10, ["t1", "t2", "t3"]), history=[], best=None, remaining_attempts=2, remaining_budget_s=1200.0)
    assert d70.action == ACTION_REPAIR
    assert d70.rule == 5
    assert d70.evidence["mostly_passing"] is True

    # 69% (69/100) -> NOT repair, falls through to continue (rule 6).
    d69 = decide(
        {"passed": 69, "total": 100, "accepted": False, "failure_signature": ["t1"]},
        history=[],
        best=None,
        remaining_attempts=2,
        remaining_budget_s=1200.0,
    )
    assert d69.action == ACTION_CONTINUE
    assert d69.rule == 6


def test_rule_6_continue():
    a1 = _att(2, 10, ["t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8"])
    a2 = _att(5, 10, ["t1", "t2", "t3", "t4", "t5"])
    d = decide(a2, history=[a1], best=a1, remaining_attempts=1, remaining_budget_s=600.0)
    assert d.action == ACTION_CONTINUE
    assert d.rule == 6
    assert d.feedback_source == "current"


def test_ordering_conflicts():
    # Conflict A: All pass AND budget exhausted -> Rule 1 beats Rule 2.
    d12 = decide(_att(10, 10), history=[], best=None, remaining_attempts=0, remaining_budget_s=0.0)
    assert d12.action == ACTION_STOP_SUCCESS
    assert d12.rule == 1

    # Conflict B: Budget exhausted AND worse than best -> Rule 2 beats Rule 3.
    a1 = _att(8, 10, ["t1", "t2"])
    a2 = _att(3, 10, ["t1", "t2", "t3", "t4", "t5", "t6", "t7"])
    d23 = decide(a2, history=[a1], best=a1, remaining_attempts=0, remaining_budget_s=600.0)
    assert d23.action == ACTION_DELIVER_BEST_BUDGET
    assert d23.rule == 2
    assert d23.delivered_index == 0

    # Conflict C: Worse than best AND stuck (2 consecutive identical signatures) -> Rule 3 beats Rule 4.
    best_a = _att(8, 10, ["t1", "t2"])
    stuck1 = _att(4, 10, ["t1", "t2", "t3", "t4", "t5", "t6"])
    stuck2 = _att(4, 10, ["t1", "t2", "t3", "t4", "t5", "t6"])
    d34 = decide(stuck2, history=[best_a, stuck1], best=best_a, remaining_attempts=1, remaining_budget_s=600.0)
    assert d34.evidence["worse_than_best"] is True
    assert d34.evidence["no_progress_stuck"] is True
    assert d34.action == ACTION_RESTORE_BEST
    assert d34.rule == 3

    # Conflict D: Stuck AND >=70% passing (e.g. 8/10 stuck twice on same 2 tests) -> Rule 4 beats Rule 5.
    hi1 = _att(8, 10, ["t1", "t2"])
    hi2 = _att(8, 10, ["t1", "t2"])
    d45 = decide(hi2, history=[hi1], best=hi1, remaining_attempts=1, remaining_budget_s=600.0)
    assert d45.evidence["no_progress_stuck"] is True
    assert d45.evidence["mostly_passing"] is True
    assert d45.action == ACTION_RESTART_FRESH
    assert d45.rule == 4

    # Conflict E: Worse than best AND >=70% passing (9/10 -> 8/10) -> Rule 3 beats Rule 5.
    b9 = _att(9, 10, ["t1"])
    c8 = _att(8, 10, ["t1", "t2"])
    d35 = decide(c8, history=[b9], best=b9, remaining_attempts=1, remaining_budget_s=600.0)
    assert d35.action == ACTION_RESTORE_BEST
    assert d35.rule == 3


def test_feedback_byte_cap_and_shared_structure():
    many_tests = [f"very_long_test_module.TestCase.test_case_number_{i:03d}" for i in range(40)]
    long_problem = "Traceback (most recent call last):\n" + ("  line of noise\n" * 50) + "AssertionError: 42 != 99 (中文測試)"
    fb = build_feedback(many_tests, long_problem)
    assert len(fb.encode("utf-8")) <= FEEDBACK_MAX_BYTES
    assert "Failing tests:" in fb
    assert "AssertionError" in fb
    mem_assert_ks1_clean(fb)
    e1_assert_ks1_clean(fb)

    # C appends exactly one action line to the exact same shared base feedback.
    fb_c = build_controller_feedback(ACTION_REPAIR, many_tests, long_problem)
    assert fb_c == f"{fb}\n{CONTROLLER_ACTION_LINES[ACTION_REPAIR]}"
    mem_assert_ks1_clean(fb_c)
    e1_assert_ks1_clean(fb_c)


def test_chain_verify_reconstruct_and_tamper_detection(tmp_path: Path):
    ident = Identity.generate()
    pub = PublicIdentity(vacant_id=ident.vacant_id, pub=ident.pub)
    book = Logbook()

    a1 = _att(4, 10, ["t1", "t2", "t3", "t4", "t5", "t6"])
    d1 = decide(a1, history=[], best=None, remaining_attempts=2, remaining_budget_s=1200.0)
    controller_event(book, ident, attempt=1, decision=d1, ts_ms=1000)

    a2 = _att(4, 10, ["t1", "t2", "t3", "t4", "t5", "t6"])
    d2 = decide(a2, history=[a1], best=a1, remaining_attempts=1, remaining_budget_s=600.0)
    controller_event(book, ident, attempt=2, decision=d2, ts_ms=2000)

    a3 = _att(10, 10)
    d3 = decide(a3, history=[a1, a2], best=a1, remaining_attempts=0, remaining_budget_s=300.0)
    controller_event(book, ident, attempt=3, decision=d3, ts_ms=3000)

    chain_path = tmp_path / "controller_chain.ndjson"
    save_controller_chain(book, ident, chain_path)

    buf = io.StringIO()
    hist = reconstruct(chain_path, stream=buf)
    assert len(hist) == 3
    assert [h["action"] for h in hist] == [ACTION_CONTINUE, ACTION_RESTART_FRESH, ACTION_STOP_SUCCESS]
    assert [h["rule"] for h in hist] == [6, 4, 1]
    out = buf.getvalue()
    assert "action=restart_fresh" in out
    assert "action=stop_success" in out

    # Explicit pub verification works too.
    assert len(reconstruct(chain_path, pub=pub, emit=False)) == 3

    # Tamper with middle entry payload -> verify fails!
    lines = chain_path.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[1])
    row["payload"]["action"] = ACTION_REPAIR
    lines[1] = json.dumps(row)
    chain_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ChainError):
        reconstruct(chain_path, emit=False)

    # Wrong public key -> verify fails!
    save_controller_chain(book, ident, chain_path)
    other = Identity.generate()
    other_pub = PublicIdentity(vacant_id=other.vacant_id, pub=other.pub)
    with pytest.raises(ChainError):
        reconstruct(chain_path, pub=other_pub, emit=False)


def test_vacant_do_controller_policy_and_cli_option(tmp_path: Path, monkeypatch):
    """Verify `vacant do --policy controller` keeps/restores workspaces and writes a verifiable chain."""
    from vacant_network.adapters import cli as adapters_cli
    from vacant_network.adapters import restart as RS
    from vacant_network.adapters.run import Launch

    # CLI parser accepts --policy controller and defaults to restart
    p_def = adapters_cli.build_parser().parse_args(["do", "--cmd", "echo {prompt}", "--prompt", "hi"])
    assert p_def.policy == "restart"
    p_ctl = adapters_cli.build_parser().parse_args(
        ["do", "--policy", "controller", "--cmd", "echo {prompt}", "--prompt", "hi"]
    )
    assert p_ctl.policy == "controller"

    # End-to-end RS.run with policy="controller": attempt 1 passes 3/4 (repair >=70%),
    # attempt 2 receives attempt 1's workspace (marker present) and passes 4/4 (stop_success).
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vhome"))
    monkeypatch.setenv("VACANT_WORK", str(tmp_path / "vwork"))
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "sol_test.py").write_text(
        "import unittest\nfrom sol import f\nclass T(unittest.TestCase):\n"
        "    def test_1(self): self.assertEqual(f(1), 1)\n"
        "    def test_2(self): self.assertEqual(f(2), 2)\n"
        "    def test_3(self): self.assertEqual(f(3), 3)\n"
        "    def test_4(self): self.assertEqual(f(4), 4)\n",
        encoding="utf-8",
    )
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    agent_py = tmp_path / "fake_agent.py"
    agent_py.write_text(
        "import os, pathlib, sys\n"
        "st = pathlib.Path(os.environ['ST'])\n"
        "cf = st / 'n'\n"
        "n = int(cf.read_text()) + 1 if cf.exists() else 1; cf.write_text(str(n))\n"
        "(st / f'prompt{n}').write_text(sys.argv[1])\n"
        "mk = pathlib.Path('marker.txt')\n"
        "(st / f'marker{n}').write_text(mk.read_text() if mk.is_file() else '<NONE>')\n"
        "if n == 1:\n"
        "    pathlib.Path('sol.py').write_text('def f(x): return x if x <= 3 else -1\\n')\n"
        "    mk.write_text('kept_from_1')\n"
        "else:\n"
        "    pathlib.Path('sol.py').write_text('def f(x): return x\\n')\n",
        encoding="utf-8",
    )
    import sys

    def build(prompt_text: str, ws: Path) -> Launch:
        return Launch(argv=[sys.executable, str(agent_py), prompt_text], env={"ST": str(state_dir)})

    res = RS.run(
        proj,
        build,
        "solve task",
        max_attempts=3,
        attempt_timeout_s=30.0,
        budget_s=90.0,
        min_attempt_s=1.0,
        agent="fake",
        policy="controller",
    )
    assert res["accepted"] is True
    assert res["policy"] == "controller"
    assert len(res["attempts"]) == 2
    assert res["attempts"][0]["controller_action"] == ACTION_REPAIR
    assert res["attempts"][0]["controller_rule"] == 5
    assert res["attempts"][1]["controller_action"] == ACTION_STOP_SUCCESS
    assert res["attempts"][1]["controller_rule"] == 1
    assert (state_dir / "marker2").read_text() == "kept_from_1"
    assert CONTROLLER_ACTION_LINES[ACTION_REPAIR] in (state_dir / "prompt2").read_text()
    chain = res["controller_chain"]
    hist = reconstruct(chain, emit=False)
    assert [h["action"] for h in hist] == [ACTION_REPAIR, ACTION_STOP_SUCCESS]


def test_ctl_metrics_five_metrics_and_paired(tmp_path: Path):
    """Verify ops/redo/analysis/ctl_metrics.py computes all 5 metrics and C vs B / C vs R."""
    from ops.redo.analysis import ctl_metrics

    plan_sha = "abc123"
    plan = {
        "id": "synth_ctl",
        "tasks": ["t1", "t2"],
        "reps": 1,
        "arms": {"A": {}, "R": {}, "B": {}, "C": {}},
    }
    (tmp_path / "RUN.json").write_text(json.dumps({"plan_sha256": plan_sha, "plan": plan}))

    def write_cell(task: str, rep: int, arm: str, *, passed: bool, hid_p: int, hid_t: int,
                   att_acc_tests: list[dict[str, bool]], delivered: int, tokens: int, wall: float):
        cdir = tmp_path / "cells" / task / f"r{rep}" / arm
        cdir.mkdir(parents=True)
        atts_summary = []
        for idx, tr in enumerate(att_acc_tests, start=1):
            adir = cdir / f"attempt_{idx}"
            adir.mkdir()
            att_doc = {
                "acc": {"test_results": tr, "accept": all(tr.values()), "passed": sum(tr.values()), "run": len(tr)},
                "grade": {"pass": passed if idx == delivered else False,
                          "detail": {"tests_passed": hid_p if idx == delivered else 0, "tests_total": hid_t, "status": "ok"}},
            }
            (adir / "attempt.json").write_text(json.dumps(att_doc))
            atts_summary.append({
                "k": idx,
                "usage": {"calls": 2, "input": tokens // len(att_acc_tests), "output": 0},
            })
        cell = {
            "task": task, "rep": rep, "arm": arm, "plan_sha256": plan_sha,
            "infra_void": None, "pass": passed, "delivered_attempt": delivered,
            "n_attempts": len(att_acc_tests), "wall_s": wall, "agent_wall_s": wall,
            "attempts": atts_summary,
        }
        (cdir / "cell.json").write_text(json.dumps(cell))

    # t1: C passes (no broken tests), B fails (attempt 1 passed a,b; delivered attempt 2 passed a only -> 1/2 broken), R fails
    write_cell("t1", 1, "C", passed=True, hid_p=4, hid_t=4,
               att_acc_tests=[{"a": True, "b": False}, {"a": True, "b": True}], delivered=2, tokens=200, wall=10.0)
    write_cell("t1", 1, "B", passed=False, hid_p=2, hid_t=4,
               att_acc_tests=[{"a": True, "b": True, "c": False}, {"a": True, "b": False, "c": False}],
               delivered=2, tokens=300, wall=20.0)
    write_cell("t1", 1, "R", passed=False, hid_p=1, hid_t=4,
               att_acc_tests=[{"a": False, "b": False}], delivered=1, tokens=150, wall=15.0)
    write_cell("t1", 1, "A", passed=False, hid_p=1, hid_t=4,
               att_acc_tests=[{"a": True, "b": False}], delivered=1, tokens=100, wall=30.0)
    # t2: C passes, B passes, R fails, A fails
    write_cell("t2", 1, "C", passed=True, hid_p=4, hid_t=4,
               att_acc_tests=[{"a": True, "b": True}], delivered=1, tokens=100, wall=6.0)
    write_cell("t2", 1, "B", passed=True, hid_p=4, hid_t=4,
               att_acc_tests=[{"a": True, "b": True}], delivered=1, tokens=100, wall=8.0)
    write_cell("t2", 1, "R", passed=False, hid_p=2, hid_t=4,
               att_acc_tests=[{"a": True, "b": False}], delivered=1, tokens=200, wall=12.0)
    write_cell("t2", 1, "A", passed=False, hid_p=0, hid_t=4,
               att_acc_tests=[{"a": False, "b": False}], delivered=1, tokens=100, wall=25.0)

    out = ctl_metrics.analyse(tmp_path)
    assert out["per_arm"]["C"]["hidden_success_rate"] == 1.0
    assert out["per_arm"]["C"]["hidden_satisfaction_macro"] == 1.0
    assert out["per_arm"]["C"]["tokens_per_success"] == 150.0
    assert out["per_arm"]["C"]["broken_after_pass_micro"] == 0.0
    assert out["per_arm"]["B"]["broken_tests"] == 1
    assert out["per_arm"]["B"]["ever_passed_tests"] == 4
    assert out["per_arm"]["B"]["broken_after_pass_micro"] == 0.25
    assert out["comparisons"]["C_vs_B"]["treatment_only_c"] == 1
    assert out["comparisons"]["C_vs_B"]["control_only_b"] == 0
    assert out["comparisons"]["C_vs_R"]["treatment_only_c"] == 2
    assert out["comparisons"]["C_vs_R"]["mcnemar_exact_p"] == 0.5
    md = ctl_metrics.render_report(out)
    assert "C_vs_B" in md and "C_vs_R" in md

