#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aider Polyglot（Python 子集）pilot 的 cell.sh 版計分器：
`python3 scorer.py <hidden 目錄> <最後的工作區目錄>`，stdout 最後一行是一個 JSON 物件，
至少有 `"pass": true|false`（`ops/colab_campaign_20260927/PLAN_BATCH2_TASK3.md` 步驟 3）。

判準出處：`ops/vacantrun/task_banks_20260927/polyglot_py/score.py`（那支的出處：
Aider-AI/aider `benchmark/benchmark.py::run_unit_tests`——結束碼 0 ＝ 過）。
只取工作區的解答檔，配上 `hidden/<id>/tests/` 的**原件**測試檔，在乾淨目錄裡跑；
`pass`＝所有測試都過，而且實際跑到的測試數等於 `expected.json` 的 `n_tests`。

**這支會執行 agent 寫的程式**，因此逐字比照第一批 `scorers/code_suite.py` 的隔離做法
（PLAN 步驟 20 明講）：一個測試檔一個行程、`SUITE_TIMEOUT_S`（預設 60 秒）逾時、
`RLIMIT_AS` 2 GB。cell.sh 已經在另一個計分使用者的圍牆裡呼叫這支，這裡的資源限制
是第二層（同一台機器 48 格同時跑，比題庫自己的量具那台忙）。
**任何例外都吞下並輸出 JSON**（沒輸出＝那一格被判 infra_void）。
"""
from __future__ import annotations

import json
import os
import resource
import shutil
import subprocess
import sys
import tempfile

MEM = 2048 * 1024 * 1024
SUITE_TIMEOUT_S = float(os.environ.get("SUITE_TIMEOUT_S", "60"))
MARK = "@@VACANT_TASKBANK_RESULT@@"

#: 在計分目錄裡執行的 runner（只用標準函式庫），逐字取自
#: `ops/vacantrun/task_banks_20260927/polyglot_py/score.py::_RUNNER`。
_RUNNER = r"""
import json, sys, traceback, unittest
sys.path.insert(0, ".")
mod = sys.argv[1]
out = {"run": 0, "failures": 0, "errors": 0, "skipped": 0, "unexpected_successes": 0,
       "load_error": None, "first_problem": None}
try:
    suite = unittest.TestLoader().loadTestsFromName(mod)
except BaseException:
    out["load_error"] = traceback.format_exc(limit=3)[-800:]
else:
    res = unittest.TestResult()
    suite.run(res)
    out.update(run=res.testsRun, failures=len(res.failures), errors=len(res.errors),
               skipped=len(res.skipped), unexpected_successes=len(res.unexpectedSuccesses))
    probs = res.failures + res.errors
    if probs:
        out["first_problem"] = (str(probs[0][0]) + "\n" + probs[0][1])[-800:]
sys.stdout.flush()
print("\n@@VACANT_TASKBANK_RESULT@@" + json.dumps(out))
"""


def _lim():
    # 盡力而為：Colab（Linux）上會生效；macOS 的 RLIMIT_AS 有已知的核心層限制
    # （即使 getrlimit 回報 hard=RLIM_INFINITY，setrlimit 仍可能報 ValueError），
    # 量具在本機（Mac）跑時不能因為設不了記憶體上限就讓整支 scorer 死掉。
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEM, MEM))
    except (ValueError, OSError):
        pass


def run_tests(solution_src: str | None, hidden_dir: str, exp: dict) -> dict:
    base = {"pass": False, "tests_passed": 0, "tests_total": exp.get("n_tests"),
            "status": None, "detail": None, "task_id": exp.get("task_id")}
    if solution_src is None:
        return {**base, "status": "missing", "note": f"no {exp['solution_file']} in workspace"}
    d = tempfile.mkdtemp(prefix="pgscore_")
    try:
        shutil.copyfile(solution_src, os.path.join(d, exp["solution_file"]))
        for t in exp["test_files"]:
            shutil.copyfile(os.path.join(hidden_dir, "tests", t), os.path.join(d, t))
        cmd = [sys.executable, "-B", "-c", _RUNNER, exp["test_main"][:-3]]
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONDONTWRITEBYTECODE": "1",
               "PYTHONHASHSEED": "0", "HOME": d, "LANG": "C.UTF-8"}
        try:
            p = subprocess.run(cmd, cwd=d, env=env, capture_output=True, text=True,
                               timeout=SUITE_TIMEOUT_S, errors="replace", preexec_fn=_lim)
        except subprocess.TimeoutExpired:
            return {**base, "status": "timeout", "note": f"suite timed out after {SUITE_TIMEOUT_S}s"}
        line = next((ln for ln in reversed(p.stdout.splitlines()) if ln.startswith(MARK)), None)
        if line is None:
            return {**base, "status": "runner_crashed",
                    "note": (p.stdout + p.stderr)[-800:]}
        r = json.loads(line[len(MARK):])
        if r["load_error"]:
            return {**base, "status": "load_error", "note": r["load_error"]}
        bad = r["failures"] + r["errors"] + r["unexpected_successes"]
        passed = r["run"] - bad - r["skipped"]
        want = exp.get("n_tests")
        ok = (bad == 0 and r["run"] > 0 and (want is None or r["run"] == want))
        status = "pass" if ok else ("count_mismatch" if bad == 0 else "fail")
        note = None if ok else f"status={status}; run={r['run']} want={want} bad={bad}"
        return {**base, "pass": bool(ok), "tests_passed": passed, "tests_run": r["run"],
                "status": status, "detail": r["first_problem"], "note": note}
    finally:
        shutil.rmtree(d, ignore_errors=True)


def score(hidden_dir: str, workspace: str) -> dict:
    exp = json.load(open(os.path.join(hidden_dir, "expected.json")))
    p = os.path.join(workspace, exp["solution_file"])
    src = p if os.path.isfile(p) and not os.path.islink(p) else None
    return run_tests(src, hidden_dir, exp)


def main() -> int:
    if len(sys.argv) != 3:
        print(json.dumps({"pass": False, "note": "usage: scorer.py <hidden_dir> <workspace_dir>"}))
        return 0
    hidden_dir, workspace = sys.argv[1], sys.argv[2]
    try:
        result = score(hidden_dir, workspace)
    except Exception as e:  # 不准丟例外沒輸出
        result = {"pass": False, "note": f"scorer_error: {type(e).__name__}: {e}"}
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
