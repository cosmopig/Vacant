#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Polyglot-Python pilot 的隱藏計分器：只取工作區的解答檔，配上原件測試檔，在乾淨目錄裡跑。

這支在架構裡承重什麼：A/B 兩臂的分子。計分端只用標準函式庫（unittest），不依賴 pytest。

判準（出處：Aider-AI/aider `benchmark/benchmark.py::run_unit_tests`——對 `.py` 題跑測試指令，
結束碼 0 ＝ 過，逾時 180 秒）：
- `pass`（主指標）＝原件測試檔的每一個測試都過、而且實際跑到的測試數 ＝ 參考解跑到的數（`n_tests`）
- `tests_passed / tests_total`（次指標）

防呆（不是 Aider 原本就有的，寫進 manifest）：
1. 只複製 `expected.json` 的 `solution_file` 那一個檔；工作區的 conftest.py、改過的測試檔、其他模組都不進計分目錄。
   解答檔不存在（或是符號連結）⇒ `status=missing`、0 分。
2. 測試檔一律用 `hidden/<id>/tests/` 的原件。
3. `n_tests` 對不上（例如解答檔動了 unittest 讓測試沒被跑到）⇒ 不算過。

⚠ 這支會**執行 agent 寫的程式**。在 Colab 上請不要用 root 直接跑：用 `--wrap` 包一層
（例如 `--wrap "sudo -u scorer bwrap --ro-bind / / --tmpfs /tmp --bind {dir} {dir} --unshare-net --die-with-parent"`，
`{dir}` 會被換成計分用的暫存目錄）。

用法：
    python3 score.py --hidden hidden/pg_bowling --workspace /path/to/ws
    python3 score.py --hidden-root hidden --runs runs.tsv        # 每行 task_id<TAB>ws
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile

MARK = "@@VACANT_TASKBANK_RESULT@@"

#: 在計分目錄裡執行的 runner（只用標準函式庫）。載入失敗也要回報，不可以讓例外吞掉結果。
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


def run_tests(solution_src: str | None, hidden_dir: str, *, python: str = sys.executable,
              wrap: str = "") -> dict:
    exp = json.load(open(os.path.join(hidden_dir, "expected.json")))
    base = {"task_id": exp["task_id"], "pass": 0, "tests_passed": 0,
            "tests_total": exp.get("n_tests"), "status": None, "detail": None}
    if solution_src is None:
        return {**base, "status": "missing"}
    d = tempfile.mkdtemp(prefix="tbscore_")
    try:
        shutil.copyfile(solution_src, os.path.join(d, exp["solution_file"]))
        for t in exp["test_files"]:
            shutil.copyfile(os.path.join(hidden_dir, "tests", t), os.path.join(d, t))
        cmd = [python, "-B", "-c", _RUNNER, exp["test_main"][:-3]]
        if wrap:
            cmd = [w.replace("{dir}", d) for w in shlex.split(wrap)] + cmd
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONDONTWRITEBYTECODE": "1",
               "PYTHONHASHSEED": "0", "HOME": d, "LANG": "C.UTF-8"}
        try:
            p = subprocess.run(cmd, cwd=d, env=env, capture_output=True, text=True,
                               timeout=exp["timeout_s"], errors="replace")
        except subprocess.TimeoutExpired:
            return {**base, "status": "timeout"}
        line = next((ln for ln in reversed(p.stdout.splitlines()) if ln.startswith(MARK)), None)
        if line is None:
            return {**base, "status": "runner_crashed", "detail": (p.stdout + p.stderr)[-800:]}
        r = json.loads(line[len(MARK):])
        if r["load_error"]:
            return {**base, "status": "load_error", "detail": r["load_error"]}
        bad = r["failures"] + r["errors"] + r["unexpected_successes"]
        passed = r["run"] - bad - r["skipped"]
        want = exp.get("n_tests")
        ok = (bad == 0 and r["run"] > 0 and (want is None or r["run"] == want))
        status = "pass" if ok else ("count_mismatch" if bad == 0 else "fail")
        return {**base, "pass": int(ok), "tests_passed": passed, "tests_run": r["run"],
                "status": status, "detail": r["first_problem"]}
    finally:
        shutil.rmtree(d, ignore_errors=True)


def score_workspace(hidden_dir: str, workspace: str, **kw) -> dict:
    exp = json.load(open(os.path.join(hidden_dir, "expected.json")))
    p = os.path.join(workspace, exp["solution_file"])
    src = p if os.path.isfile(p) and not os.path.islink(p) else None
    return run_tests(src, hidden_dir, **kw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hidden")
    ap.add_argument("--workspace")
    ap.add_argument("--hidden-root")
    ap.add_argument("--runs")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--wrap", default="")
    a = ap.parse_args()
    kw = {"python": a.python, "wrap": a.wrap}
    if a.runs:
        for line in open(a.runs):
            if line.strip():
                tid, ws = line.rstrip("\n").split("\t")[:2]
                print(json.dumps(score_workspace(os.path.join(a.hidden_root, tid), ws, **kw),
                                 ensure_ascii=False, sort_keys=True))
        return 0
    if not (a.hidden and a.workspace):
        ap.error("需要 --hidden 與 --workspace（或 --hidden-root 與 --runs）")
    print(json.dumps(score_workspace(a.hidden, a.workspace, **kw), ensure_ascii=False,
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
