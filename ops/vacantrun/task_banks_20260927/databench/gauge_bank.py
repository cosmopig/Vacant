#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DataBench pilot 的量具（零模型呼叫）：參考解重現官方答案、計分器雙向（對的滿分、錯的零分）。

兩段（與 `../dabench/gauge_bank.py` 同形）：
1. `--reproduce`：依候選順序跑 `reference/solutions.py`，用 `score.py` 的官方判等對官方答案，
   寫 `reference/reproduction.json`。`build_bank.py` 只從這份取題。
2. 預設：對渲染好的每一題量七種交件——參考解 ⇒ 1、官方答案原文 ⇒ 1、第一行答案＋後面幾行說明 ⇒ 1、
   檔不存在 ⇒ 0、空檔 ⇒ 0、改錯的答案（依型別造）⇒ 0、答案只放在子資料夾 ⇒ 0。
   `--official-eval <eval.py>` 另外核對 `score.default_compare` 與官方原始碼逐字相同（去掉 `self`）。

需要 pandas＋pyarrow。
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import shutil
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "reference"))

import build_bank as B  # noqa: E402
import score as S  # noqa: E402

REPORT = os.path.join(HERE, "gauge_report.json")


def reproduce() -> int:
    import pandas as pd
    import solutions
    src = B.source()
    rows = B.load_qa(src)
    by = {(r["dataset"], r["row"]): r for r in rows}
    order = B.candidate_order(src, rows)
    tables = {}
    results = {}
    for t in B.TYPES:
        for k in order[t]:
            key = B.key_str(k)
            fn = solutions.SOLUTIONS.get(key)
            if fn is None:
                break
            if k[0] not in tables:
                tables[k[0]] = pd.read_csv(io.BytesIO(B.csv_bytes(src, k[0])))
            try:
                val, err = fn(tables[k[0]].copy()), None
            except Exception:
                val, err = None, traceback.format_exc(limit=2)
            exp = {"task_id": B.task_id(k), "answer": str(by[k]["answer"]), "type": t}
            r = S.score_value(val, exp)
            results[key] = {"type": t, "reproduced": bool(r["correct"]), "reference_output": val,
                            "error": err,
                            "note": None if r["correct"] else
                            f"參考解 {val!r} ≠ 官方答案 {str(by[k]['answer'])!r}"}
    out = {"generated_by": "gauge_bank.py --reproduce",
           "solutions_sha256": B.sha256_bytes(open(os.path.join(HERE, "reference", "solutions.py"),
                                                   "rb").read()),
           "results": results}
    with open(B.REPRO, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    for t in B.TYPES:
        rs = [(k, v) for k, v in results.items() if v["type"] == t]
        print(f"{t}: 檢查 {len(rs)}、重現 {sum(v['reproduced'] for _, v in rs)}")
        for k, v in rs:
            if not v["reproduced"]:
                print(f"   ✗ {k}: {v['note'] or ''} {v['error'] or ''}")
    return 0


def wrong_answer(truth: str, typ: str) -> str:
    if typ == "boolean":
        return "False" if truth.strip().lower() in ("true", "yes", "y") else "True"
    if typ == "number":
        x = float("".join(c for c in truth if c.isdigit() or c in ".-"))
        return repr(x * 1.5 + 1.0)
    if typ == "category":
        return "zzz_not_a_value"
    items = [s.strip() for s in truth.strip("[]").split(",")]
    if typ == "list[number]":
        items[0] = repr(float("".join(c for c in items[0] if c.isdigit() or c in ".-")) + 1000.5)
        return "[" + ", ".join(items) + "]"
    items[0] = "'zzz_not_a_value'"
    return "[" + ", ".join(items) + "]"


def check_verbatim(official: str) -> bool:
    """官方 eval.py 的 default_compare 與 score.default_compare：AST 相同（self 參數拿掉）。"""
    tree = ast.parse(open(official).read())
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
              and n.name == "default_compare")
    fn.args.args = fn.args.args[1:]
    mine = next(n for n in ast.walk(ast.parse(open(os.path.join(HERE, "score.py")).read()))
                if isinstance(n, ast.FunctionDef) and n.name == "default_compare")
    return ast.dump(fn) == ast.dump(mine)


def gauge(official: str | None) -> int:
    m = json.load(open(B.MANIFEST))
    repro = json.load(open(B.REPRO))["results"]
    rows, bad = [], 0
    for t in m["tasks"]:
        tid = t["task_id"]
        exp = json.load(open(os.path.join(B.HIDDEN, tid, "expected.json")))
        truth, typ = exp["answer"], exp["type"]
        cases = {"reference": (repro[t["source"]]["reference_output"] + "\n", 1),
                 "label_verbatim": (truth + "\n", 1),
                 "with_prose_after": (truth + "\n\nComputed with pandas from the parquet file.\n", 1),
                 "missing": (None, 0), "empty": ("\n\n", 0),
                 "wrong": (wrong_answer(truth, typ) + "\n", 0), "subdir_only": ("SUBDIR", 0)}
        got = {}
        for name, (text, want) in cases.items():
            ws = tempfile.mkdtemp()
            try:
                shutil.copytree(os.path.join(B.TEMPLATES, tid), ws, dirs_exist_ok=True)
                if text == "SUBDIR":
                    os.makedirs(os.path.join(ws, "out"))
                    open(os.path.join(ws, "out", "answer.txt"), "w").write(truth + "\n")
                elif text is not None:
                    open(os.path.join(ws, "answer.txt"), "w").write(text)
                r = S.score_workspace(os.path.join(B.HIDDEN, tid), ws)
            finally:
                shutil.rmtree(ws, ignore_errors=True)
            got[name] = r["correct"]
            if r["correct"] != want:
                bad += 1
                print(f"✗ {tid} {name}: {r['correct']} 預期 {want} ({r['status']}, {r['predicted']!r})")
        rows.append({"task_id": tid, "type": typ, "cases": got})
    summary = {"n_tasks": len(rows),
               "by_type": {ty: sum(r["type"] == ty for r in rows) for ty in B.TYPES}}
    for name in ("reference", "label_verbatim", "with_prose_after"):
        summary[name + "_full_marks"] = sum(r["cases"][name] for r in rows)
    for name in ("missing", "empty", "wrong", "subdir_only"):
        summary[name + "_zero"] = sum(1 - r["cases"][name] for r in rows)
    if official:
        same = check_verbatim(official)
        summary["default_compare_ast_equals_official"] = same
        if not same:
            bad += 1
    summary["verdict"] = "OK" if bad == 0 else f"{bad} 個格子不符"
    with open(REPORT, "w") as f:
        json.dump({"summary": summary, "rows": rows}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reproduce", action="store_true")
    ap.add_argument("--official-eval")
    a = ap.parse_args()
    return reproduce() if a.reproduce else gauge(a.official_eval)


if __name__ == "__main__":
    sys.exit(main())
