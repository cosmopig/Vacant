#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Polyglot-Python pilot 的量具（零模型呼叫）：計分器對已知正確的解給滿分、對已知不完整的交件給 0。

這支在架構裡承重什麼：沒有這一份，`score.py` 的 0 可能是「量具量不動」（記憶：判成 0 之前先證明量得動）。

每一題量七種交件：
    reference        官方參考解（.meta/example.py）            ⇒ pass=1
    stub             官方 stub（contract.md 裡那份骨架）          ⇒ pass=0
    missing          解答檔不存在                                 ⇒ pass=0（status=missing）
    empty            空檔                                         ⇒ pass=0
    syntax_error     解答檔語法錯                                 ⇒ pass=0
    tampered_tests   stub＋把工作區的測試檔改成全空＋conftest.py  ⇒ pass=0（計分用原件）
    reference_tampered 參考解＋工作區測試檔被改壞                 ⇒ pass=1（同上，反方向）
另外用 pytest（Aider 官方的跑法）對 reference／stub 交叉驗證：兩種 runner 的判定必須一致。

用法：<有 pytest 的 python> gauge_bank.py      # 印摘要、寫 gauge_report.json
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_bank as B  # noqa: E402
import score as S  # noqa: E402

REPORT = os.path.join(HERE, "gauge_report.json")


def stub_of(tid: str, solution: str) -> str:
    c = open(os.path.join(B.TEMPLATES, tid, "contract.md")).read()
    return c.split("```python\n", 1)[1].split("\n```", 1)[0] + "\n"


def pytest_pass(solution_text: str, hidden: str, exp: dict) -> bool:
    d = tempfile.mkdtemp()
    try:
        with open(os.path.join(d, exp["solution_file"]), "w") as f:
            f.write(solution_text)
        for t in exp["test_files"]:
            shutil.copyfile(os.path.join(hidden, "tests", t), os.path.join(d, t))
        p = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                            exp["test_main"]], cwd=d, capture_output=True, text=True,
                           timeout=exp["timeout_s"])
        return p.returncode == 0
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main() -> int:
    m = json.load(open(B.MANIFEST))
    rows, bad = [], 0
    for t in m["tasks"]:
        tid = t["task_id"]
        hidden = os.path.join(B.HIDDEN, tid)
        exp = json.load(open(os.path.join(hidden, "expected.json")))
        sol = exp["solution_file"]
        ref = open(os.path.join(B.REFERENCE, tid, "example.py")).read()
        stub = stub_of(tid, sol)
        cases = {"reference": (ref, None, 1), "stub": (stub, None, 0), "missing": (None, None, 0),
                 "empty": ("", None, 0), "syntax_error": (stub + "\ndef (:\n", None, 0),
                 "tampered_tests": (stub, "tamper", 0), "reference_tampered": (ref, "tamper", 1)}
        got = {}
        for name, (text, mode, want) in cases.items():
            ws = tempfile.mkdtemp()
            try:
                shutil.copytree(os.path.join(B.TEMPLATES, tid), ws, dirs_exist_ok=True)
                if text is not None:
                    with open(os.path.join(ws, sol), "w") as f:
                        f.write(text)
                if mode == "tamper":
                    for tf in exp["test_files"]:
                        with open(os.path.join(ws, tf), "w") as f:
                            f.write("import unittest\n")
                    with open(os.path.join(ws, "conftest.py"), "w") as f:
                        f.write("collect_ignore_glob = ['*']\n")
                r = S.score_workspace(hidden, ws)
            finally:
                shutil.rmtree(ws, ignore_errors=True)
            got[name] = {"pass": r["pass"], "status": r["status"],
                         "tests_passed": r["tests_passed"]}
            if r["pass"] != want:
                bad += 1
                print(f"✗ {tid} {name}: pass={r['pass']} 預期 {want} ({r['status']}) {r['detail']!r:.300}")
        py_ref, py_stub = pytest_pass(ref, hidden, exp), pytest_pass(stub, hidden, exp)
        agree = (py_ref is True) and (py_stub is False)
        if not agree:
            bad += 1
            print(f"✗ {tid} pytest 交叉驗證不一致：ref={py_ref} stub={py_stub}")
        rows.append({"task_id": tid, "n_tests": exp["n_tests"], "cases": got,
                     "pytest_reference_pass": py_ref, "pytest_stub_pass": py_stub,
                     "stub_tests_passed": got["stub"]["tests_passed"]})
        print(f"{tid:34s} ref={got['reference']['pass']} stub={got['stub']['pass']}"
              f"（stub 過 {got['stub']['tests_passed']}/{exp['n_tests']}） pytest ref/stub={py_ref}/{py_stub}")
    summary = {
        "n_tasks": len(rows),
        "reference_pass": sum(r["cases"]["reference"]["pass"] for r in rows),
        "stub_zero": sum(1 - r["cases"]["stub"]["pass"] for r in rows),
        "missing_zero": sum(1 - r["cases"]["missing"]["pass"] for r in rows),
        "empty_zero": sum(1 - r["cases"]["empty"]["pass"] for r in rows),
        "syntax_error_zero": sum(1 - r["cases"]["syntax_error"]["pass"] for r in rows),
        "tampered_tests_zero": sum(1 - r["cases"]["tampered_tests"]["pass"] for r in rows),
        "reference_tampered_pass": sum(r["cases"]["reference_tampered"]["pass"] for r in rows),
        "pytest_agrees": sum(r["pytest_reference_pass"] and not r["pytest_stub_pass"] for r in rows),
        "stub_partial_credit_tasks": [r["task_id"] for r in rows if r["stub_tests_passed"]],
        "python": sys.version.split()[0],
        "verdict": "OK" if bad == 0 else f"{bad} 個格子不符",
    }
    with open(REPORT, "w") as f:
        json.dump({"summary": summary, "rows": rows}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
