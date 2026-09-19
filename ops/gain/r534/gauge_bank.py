#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R534 題庫量具：驗「渲染出來的測試檔」與「既有 run 用的那把尺」是同一把。

這支在架構裡承重什麼
--------------------
`build_bank.py` 把題庫的 `(args, expected)` 字面值渲染成 agent 跑得到的檔案。
那個轉換一旦有偏差，R534 的每一個數字都會與 r460／r532 的 `meets_demand`
不可比，而偏差在報表上長得跟「機制沒效果」一模一樣。這支是那個轉換的量具。

三件事，三種強度（誠實地標出來哪一件其實很弱）
----------------------------------------------
1. **fail-closed（強）**：每一題餵一個 `return None` 的樁，可見與隱藏都必須判不過。
   量不到就不是通過——樁被判過就是尺壞了。
2. **正控制（很弱：20 題只覆蓋得到 1 題）**：`ops/gain/data/lcb_probe_solutions.json`
   是本 repo 手寫的 v1/v2 探針解，與這 20 題的交集只有 `lcb_3779`。
   LCB 沒有 canonical solution ⇒ **其餘 19 題沒有參考解正控制**，
   這是 R534 必須寫進報告的量具邊界，不是可以略過的細節。
3. **等價（強，而且是真資料）**：把已歸檔 run（r460／r532）的 `calls.jsonl` 裡
   那些**模型真的寫過的候選碼**抽出來，同一份碼同時餵給
     (a) 本 repo 既有判準 `gain_run.meets_demand(code, task["hidden_check"]["code"])`
     (b) 渲染出來的 `ops/gain/r534/hidden/<task_id>/test_hidden.py`
   兩邊逐一比對。零模型呼叫。**只比對沙箱的 AST 政策本來就收得下的候選**
   （`vacant.checks._candidate_functions` 不回 None 的那些），否則比到的是沙箱政策
   而不是 case 集合與比對器——政策差異是真的、而且是已知的（R393 的 typing 坑、
   `_FORBIDDEN_ATTRS` 連 `list.remove` 都擋），但那是**另一個**問題，
   混進來會讓這支量不到它該量的東西。被政策擋掉的候選單獨計數印出來。

用法
----
    python3 ops/gain/r534/gauge_bank.py                 # 全部 20 題
    python3 ops/gain/r534/gauge_bank.py --task lcb_3534 # 單題
    python3 ops/gain/r534/gauge_bank.py --max-candidates 3
"""

from __future__ import annotations

import argparse
import ast
import glob
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, REPO)

from ops.gain.gain_run import (  # noqa: E402
    _GAIN_ALLOWED_IMPORTS, extract_code, meets_demand)
from vacant.checks import _candidate_functions  # noqa: E402
from ops.gain.r534.select_tasks import BANK_PATH, BANK_SHA256  # noqa: E402

CALLS_GLOBS = ("runs/g_r460_harness_lcb2_*/calls.jsonl",
               "runs/g_r532_lcb2_*/calls.jsonl")
TIMEOUT_S = 8

RUNNER = r"""
import importlib.util, os, sys, traceback
sys.path.insert(0, os.getcwd())
spec = importlib.util.spec_from_file_location("hid", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except Exception:
    print("IMPORT_FAIL")
    sys.exit(1)
checks = [(n, v) for n, v in vars(mod).items()
          if n.startswith("check_") and callable(v)]
checks.sort(key=lambda kv: kv[0])
for name, fn in checks:
    try:
        fn()
    except Exception as exc:
        print("FAIL %s %s: %s" % (name, type(exc).__name__, str(exc)[:200]))
        sys.exit(1)
print("PASS %d" % len(checks))
"""


def _bank() -> dict[str, dict]:
    import hashlib

    raw = open(BANK_PATH, "rb").read()
    if hashlib.sha256(raw).hexdigest() != BANK_SHA256:
        raise SystemExit("題庫 sha256 不符。停。")
    return {json.loads(l)["task_id"]: json.loads(l)
            for l in raw.decode("utf-8").splitlines() if l.strip()}


def _policy_ok(code: str, entry_point: str) -> bool:
    """沙箱的 AST 政策收不收這份候選（＝既有判準會不會在跑之前就判 False）。

    用的就是 `vacant.checks._candidate_functions` 本人，不自己重寫一份近似品——
    重寫的近似品會在某個角落與真政策分岔，而那正是這支要排除的干擾。
    """
    try:
        ast.parse(code)
    except SyntaxError:
        return False
    return _candidate_functions(
        code, allowed_imports=_GAIN_ALLOWED_IMPORTS,
        allowed_entry_points=(entry_point,)) is not None


def _run_rendered(task_id: str, code: str, which: str) -> bool:
    """在暫存目錄裡跑渲染出來的測試檔（子行程＋逾時），回傳過不過。"""
    path = (os.path.join(HERE, "hidden", task_id, "test_hidden.py") if which == "hidden"
            else os.path.join(HERE, "templates", task_id, "tests_visible", "test_visible.py"))
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "solution.py"), "w", encoding="utf-8") as fh:
            fh.write(code)
        try:
            proc = subprocess.run(
                [sys.executable, "-c", RUNNER, path],
                cwd=tmp, capture_output=True, text=True, timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return False
        return proc.returncode == 0


def _candidates(task_prompt: str, entry_point: str,
                limit: int) -> tuple[list[str], int]:
    """回 (可比對的候選碼, 被沙箱政策擋掉的份數)；確定性：檔名＋行序。

    ⚠ 預篩用的是 **JSON 編碼過**的前綴（`json.dumps(prompt)`）。直接拿原字串當
      子字串比對會在第一個換行就對不上——calls.jsonl 裡換行是 `\n` 兩個字元，
      而那個錯誤不會報錯，只會讓候選數靜靜地變成 0。
    """
    needle = json.dumps(task_prompt, ensure_ascii=False)[1:120]
    out: list[str] = []
    seen: set[str] = set()
    blocked = 0
    for pattern in CALLS_GLOBS:
        for path in sorted(glob.glob(os.path.join(REPO, pattern))):
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    if len(out) >= limit:
                        return out, blocked
                    if needle not in line:
                        continue        # 便宜的預篩，避免每行都 json.loads
                    rec = json.loads(line)
                    if rec.get("role") != "gen" or not rec.get("ok"):
                        continue
                    if task_prompt not in (rec.get("prompt") or ""):
                        continue
                    code = extract_code(rec.get("response") or "")
                    if not code or code in seen:
                        continue
                    seen.add(code)
                    if not _policy_ok(code, entry_point):
                        blocked += 1
                        continue
                    out.append(code)
    return out, blocked


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="R534 題庫量具（零模型呼叫）")
    ap.add_argument("--task", action="append", help="只驗這些 task_id")
    ap.add_argument("--max-candidates", type=int, default=5,
                    help="每題最多比對幾份已歸檔候選碼（預設 5）")
    args = ap.parse_args(argv)

    manifest = json.load(open(os.path.join(HERE, "bank_manifest.json"), encoding="utf-8"))
    task_ids = args.task or sorted(manifest["tasks"])
    bank = _bank()
    probes = json.load(open(os.path.join(REPO, "ops", "gain", "data",
                                         "lcb_probe_solutions.json"), encoding="utf-8"))

    failures: list[str] = []
    n_equiv = n_disagree = n_probe = n_blocked = 0
    for tid in task_ids:
        rec = bank[tid]
        ep = rec["entry_point"]
        hidden_code = None
        # 既有判準吃的 check 原始碼：直接用 loader 產的那一份，不自己重拼。
        from vacant.codebench import _lcb_check_code
        hidden_code = _lcb_check_code(ep, rec["visible_tests"] + rec["hidden_tests"])
        visible_code = _lcb_check_code(ep, rec["visible_tests"])

        stub = f"def {ep}(*a, **k):\n    return None\n"
        if _run_rendered(tid, stub, "hidden"):
            failures.append(f"{tid}: 樁被隱藏測資判過（fail-closed 破功）")
        if _run_rendered(tid, stub, "visible"):
            failures.append(f"{tid}: 樁被可見測資判過（fail-closed 破功）")

        if tid in probes:
            n_probe += 1
            if not _run_rendered(tid, probes[tid], "hidden"):
                failures.append(f"{tid}: 探針解沒過渲染出來的隱藏測資")
            if not _run_rendered(tid, probes[tid], "visible"):
                failures.append(f"{tid}: 探針解沒過渲染出來的可見測資")

        cands, blocked = _candidates(rec["prompt"], ep, args.max_candidates)
        n_blocked += blocked
        agree = disagree = 0
        for code in cands:
            want_hidden, _ = meets_demand(code, hidden_code, TIMEOUT_S, entry_point=ep)
            want_visible, _ = meets_demand(code, visible_code, TIMEOUT_S, entry_point=ep)
            got_hidden = _run_rendered(tid, code, "hidden")
            got_visible = _run_rendered(tid, code, "visible")
            if want_hidden == got_hidden and want_visible == got_visible:
                agree += 1
            else:
                disagree += 1
                failures.append(
                    f"{tid}: 判準不等價 hidden(既有={want_hidden} 渲染={got_hidden}) "
                    f"visible(既有={want_visible} 渲染={got_visible})")
        n_equiv += agree
        n_disagree += disagree
        print(f"{tid:>10}  樁被擋 ✓  候選 {len(cands):>2} 份：一致 {agree} 不一致 {disagree}"
              f"  沙箱政策擋掉 {blocked}"
              f"{'  探針解 ✓' if tid in probes else ''}")

    print()
    print(f"等價比對：{n_equiv} 份一致、{n_disagree} 份不一致"
          f"（比對的是沙箱 AST 政策收得下的候選）")
    print(f"沙箱政策擋掉 {n_blocked} 份候選——**在那些碼上兩條路徑本來就會不同**："
          "既有判準連跑都不跑就判 False，渲染出來的測試檔會照跑。"
          "R534 的主指標因此要指名走哪一條，見 bank_manifest.json 的 scoring 欄位。")
    print(f"正控制覆蓋：{n_probe}/{len(task_ids)} 題有手寫探針解"
          f"——其餘沒有參考解，證不了正解會被判過")
    if failures:
        print()
        for f in failures:
            print("FAIL:", f)
        return 1
    print("verdict = OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
