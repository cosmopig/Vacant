"""`vacant do` 的零設定重開模式（T05／S3）：沒有契約、專案裡有測試檔時，政策與 `ops/redo/redo.py` 的 R3 相同。

假 agent 是一支 Python 腳本：依環境變數決定第幾次寫對、寫錯或改測試。0 次模型呼叫。
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import textwrap

import pytest

from vacant_network.adapters import restart as R
from vacant_network.adapters.run import Launch

TEST = textwrap.dedent("""\
    import unittest
    from sol import f
    class T(unittest.TestCase):
        def test_one(self):
            self.assertEqual(f(1), 2)
        def test_two(self):
            self.assertEqual(f(41), 42)
    """)
GOOD = "def f(x):\n    return x + 1\n"
HALF = "def f(x):\n    return 2 if x == 1 else 0\n"
BAD = "def f(x):\n    return x\n"

AGENT = textwrap.dedent("""\
    import json, os, pathlib, sys
    st = pathlib.Path(os.environ["STUB_STATE"])
    n = json.loads(st.read_text())["n"] + 1 if st.exists() else 1
    st.write_text(json.dumps({"n": n}))
    plan = os.environ["STUB_PLAN"].split(",")
    what = plan[min(n, len(plan)) - 1]
    if what == "tamper":
        pathlib.Path("sol_test.py").write_text("import unittest\\nclass T(unittest.TestCase):\\n    def test_a(self):\\n        pass\\n")
        what = "bad"
    if what == "leftover":
        pathlib.Path("junk.txt").write_text("from attempt " + str(n))
        what = "bad"
    if what == "sleep":
        import time; time.sleep(30)
    src = {"good": %r, "half": %r, "bad": %r}.get(what)
    if src:
        pathlib.Path("sol.py").write_text(src)
    # 每一次嘗試都要是全新的工作區：前一次留下的檔不准在
    if pathlib.Path("junk.txt").exists() and what != "bad":
        pathlib.Path("saw_leftover").write_text("1")
    """) % (GOOD, HALF, BAD)


@pytest.fixture()
def proj(tmp_path, monkeypatch):
    p = tmp_path / "proj"
    p.mkdir()
    (p / "sol_test.py").write_text(TEST)
    (p / "sol.py").write_text("def f(x):\n    raise NotImplementedError\n")
    (p / "README.md").write_text("make the tests pass\n")
    monkeypatch.setenv("VACANT_WORK", str(tmp_path / "work"))
    return p


def _build(tmp_path, plan: str):
    script = tmp_path / "agent.py"
    script.write_text(AGENT)
    env = {"STUB_STATE": str(tmp_path / "state.json"), "STUB_PLAN": plan}

    def build(prompt: str, ws: pathlib.Path) -> Launch:
        return Launch(argv=[sys.executable, str(script), prompt], env=env)
    return build


def _calls(tmp_path) -> int:
    st = tmp_path / "state.json"
    return json.loads(st.read_text())["n"] if st.exists() else 0


def test_finds_only_tests_that_exist_at_start(proj):
    assert R.find_tests(proj) == ["sol_test.py"]
    (proj / "test_more.py").write_text(TEST)
    (proj / "node_modules").mkdir()
    (proj / "node_modules" / "x_test.py").write_text(TEST)
    assert R.find_tests(proj) == ["sol_test.py", "test_more.py"]


def test_stops_at_first_accepted_attempt_and_writes_it_back(proj, tmp_path):
    res = R.run(proj, _build(tmp_path, "bad,good,good"), "fix it", attempt_timeout_s=20, budget_s=300)
    assert _calls(tmp_path) == 2
    assert res["accepted"] is True and res["delivered_attempt"] == 2
    assert [a["accept"] for a in res["attempts"]] == [False, True]
    assert (proj / "sol.py").read_text() == GOOD


def test_each_attempt_starts_from_the_original_project(proj, tmp_path):
    res = R.run(proj, _build(tmp_path, "leftover,good"), "fix it", attempt_timeout_s=20, budget_s=300)
    assert res["accepted"] is True
    assert not (proj / "saw_leftover").exists()
    assert not (proj / "junk.txt").exists()          # 沒交的那一次留下的東西不回到專案


def test_no_failure_text_is_passed_to_the_next_attempt(proj, tmp_path):
    seen = []
    base = _build(tmp_path, "bad,bad,good")

    def build(prompt, ws):
        seen.append(prompt)
        return base(prompt, ws)
    R.run(proj, build, "fix it", attempt_timeout_s=20, budget_s=300)
    assert seen == ["fix it"] * 3


def test_all_fail_delivers_most_tests_passed_and_says_so(proj, tmp_path):
    res = R.run(proj, _build(tmp_path, "half,bad,bad"), "fix it", attempt_timeout_s=20, budget_s=300)
    assert _calls(tmp_path) == 3
    assert res["accepted"] is False and res["delivered_attempt"] == 1
    assert (proj / "sol.py").read_text() == HALF
    assert "not all tests pass" in R.summary(res)


def test_tampered_tests_are_restored_for_acceptance_and_never_written_back(proj, tmp_path):
    res = R.run(proj, _build(tmp_path, "tamper,good"), "fix it", attempt_timeout_s=20, budget_s=300)
    assert res["attempts"][0]["accept"] is False
    assert res["attempts"][0]["tests_tampered"] == ["sol_test.py"]
    assert res["accepted"] is True
    assert (proj / "sol_test.py").read_text() == TEST


def test_budget_caps_total_wall_clock(proj, tmp_path):
    res = R.run(proj, _build(tmp_path, "sleep"), "fix it", attempt_timeout_s=2, budget_s=3,
                min_attempt_s=0.5)
    assert len(res["attempts"]) == 2                 # 2 秒＋剩下的 1 秒；第三次沒有預算
    assert all(a["timed_out"] for a in res["attempts"])
    assert res["accepted"] is False


def test_no_tests_runs_once_and_says_nothing_was_checked(proj, tmp_path):
    (proj / "sol_test.py").unlink()
    res = R.run(proj, _build(tmp_path, "bad,good"), "fix it", attempt_timeout_s=20, budget_s=300)
    assert _calls(tmp_path) == 1
    assert res["accepted"] is None
    assert "no executable acceptance" in R.summary(res)
    assert (proj / "sol.py").read_text() == BAD     # 照實交回（和直接跑 agent 一樣）


def test_policy_matches_the_harness_policy():
    """交哪一次的規則與 redo.py 的 `_policy_deliver` 逐條相同。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "redo", pathlib.Path(__file__).resolve().parents[1] / "ops" / "redo" / "redo.py")
    redo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(redo)
    cases = [[{"accept": False, "passed": 1}, {"accept": True, "passed": 2}],
             [{"accept": False, "passed": 3}, {"accept": False, "passed": 1}, {"accept": False, "passed": 3}],
             [{"accept": False, "passed": None}, {"accept": False, "passed": 0}],
             [{"accept": True, "passed": 2}, {"accept": True, "passed": 2}]]
    for accs in cases:
        assert R.deliver_index(accs) == redo._policy_deliver(accs)


def test_cli_without_contract_uses_restart_mode(proj, tmp_path, monkeypatch, capsys):
    from vacant_network.adapters import cli
    monkeypatch.chdir(proj)
    script = tmp_path / "agent.py"
    script.write_text(AGENT)
    monkeypatch.setenv("STUB_STATE", str(tmp_path / "state.json"))
    monkeypatch.setenv("STUB_PLAN", "bad,good")
    rc = cli.main(["do", "--cmd", f"{sys.executable} {script} {{prompt}}", "--prompt", "fix it",
                   "--attempt-timeout", "20"])
    out = capsys.readouterr()
    assert "no task contract found" not in out.err
    assert rc == 0
    assert (proj / "sol.py").read_text() == GOOD
    assert "attempt 2 of 2" in out.out or "attempt 2" in out.out
