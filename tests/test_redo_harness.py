"""ops/redo/redo.py 的守門測試（0 次模型呼叫）。

這支量具是「原生 agent＋測試沒過就重開」那一格的唯一量具（ops/redo/MISSION.md）。
它壞掉的方式如果是安靜的，整批數字就白跑——所以 selftest 進 CI，另外補三條 selftest 不方便驗的：
runner 被 SIGTERM 時 agent 不會變孤兒、已 commit 的三份計畫檔載得進來、screen16 是 redo1 的子集。
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import signal
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
REDO = ROOT / "ops" / "redo" / "redo.py"
PLANS = ROOT / "ops" / "redo" / "plans"


def _load():
    spec = importlib.util.spec_from_file_location("redo_harness", REDO)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["redo_harness"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_selftest_all_green():
    r = subprocess.run([sys.executable, str(REDO), "selftest", "--quiet"], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "REDO_SELFTEST_OK" in r.stdout


def test_committed_plans_load_and_are_consistent():
    redo = _load()
    plans = {p.name: redo.load_plan(p) for p in sorted(PLANS.glob("*.json"))}
    assert {"redo1_pi_gemma12b_polyglot34.json", "screen16_pi_gemma12b.json", "smoke2_pi_gemma12b.json"} <= set(plans)
    main, screen = plans["redo1_pi_gemma12b_polyglot34.json"], plans["screen16_pi_gemma12b.json"]
    assert len(main["tasks"]) == 34 and main["reps"] == 5
    assert set(screen["tasks"]) < set(main["tasks"]) and len(screen["tasks"]) == 16
    for name, plan in plans.items():
        ctrl, treat = (plan["arms"][a] for a in plan["pair"])
        # 等預算：處理臂的總牆鐘上限不超過對照臂的時限（這是主張的一部分，改了就不是同一個實驗）
        assert ctrl["policy"] == "single" and treat["policy"] == "restart", name
        assert treat["budget_s"] <= ctrl["attempt_timeout_s"], name
        assert treat.get("hint", "none") == "none", name
        # 兩臂用同一個 agent 指令（差別只在父行程的迴圈）
        assert "agent" not in ctrl and "agent" not in treat, name
        # 三份計畫除了題目／重複數之外，條件必須相同（篩選和確認量的是同一件事）
        strip = lambda p: {k: v for k, v in p.items()                                    # noqa: E731
                           if k not in ("id", "tasks", "reps", "prereg", "_sha256", "_path", "seed")}
        assert strip(plan) == strip(main), name


def test_sigterm_kills_running_agents(tmp_path):
    redo = _load()
    bank = tmp_path / "bank"
    (bank / "t1" / "workspace").mkdir(parents=True)
    (bank / "t1" / "workspace" / "sol_test.py").write_text("import unittest\n")
    marker = tmp_path / "pid"
    agent = tmp_path / "agent.py"
    agent.write_text("import os, sys, time\nopen(sys.argv[1], 'w').write(str(os.getpid()))\ntime.sleep(600)\n")
    plan = {"schema": redo.SCHEMA, "id": "sigterm", "bank": str(bank), "tasks": ["t1"], "reps": 1,
            "arms": {"A": {"policy": "single"}, "R": {"policy": "restart", "max_attempts": 2}},
            "pair": ["A", "R"], "attempt_timeout_s": 600,
            "agent": {"argv": [sys.executable, str(agent), str(marker)], "usage": "none"},
            "providers": [{"name": "x", "jobs": 1}], "grader": {"visible_equals_grader": True}}
    pf = tmp_path / "plan.json"
    pf.write_text(json.dumps(plan))
    runner = subprocess.Popen([sys.executable, str(REDO), "run", "--plan", str(pf), "--root", str(tmp_path / "root"),
                               "--allow-uncommitted-plan"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            if marker.exists() and marker.read_text().strip():
                break
            time.sleep(0.1)
        pid = int(marker.read_text())
        runner.send_signal(signal.SIGTERM)
        assert runner.wait(timeout=30) == 130
        for _ in range(50):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            raise AssertionError("runner 被 SIGTERM 之後 agent 行程還活著")
        # 被中斷的那一格沒有 cell.json（續跑時重做），不會留下半成品被當成結果
        assert not list((tmp_path / "root").glob("cells/*/r*/*/cell.json"))
    finally:
        if runner.poll() is None:
            runner.kill()
