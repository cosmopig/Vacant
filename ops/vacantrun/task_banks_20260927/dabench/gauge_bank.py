#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DABench pilot 的量具（零模型呼叫）：參考解重現標準答案、計分器雙向（對的滿分、錯的零分）。

這支在架構裡承重什麼：沒有這一份，`score.py` 算出來的 0 可能是「量具量不動」而不是「agent 沒做到」
（記憶：判成 0 之前先證明量得動）。兩段：

1. `--reproduce`（渲染之前跑）：依 `build_bank.candidate_order` 的順序，對每一個有參考解的候選題，
   在暫存工作區裡跑 `reference/solutions.py` 的解，用 `score.py` 的判等對官方標準答案，
   寫 `reference/reproduction.json`。`build_bank.py` 只從這份結果取題。
2. 預設（渲染之後跑）：對 `templates/`＋`hidden/` 的每一題量八種交件：
   參考解輸出 ⇒ 1、標準答案原文 ⇒ 1、夾雜說明文字 ⇒ 1、檔不存在 ⇒ 0、空檔 ⇒ 0、
   每個值都改錯 ⇒ 0、只對第一項（多項題）⇒ abq 0、答案只放在子資料夾 ⇒ 0；
   另外掃樣板裡有沒有出現標準答案的字面值（洩題警告）。

需要分析用的 venv（pandas／numpy／scipy／scikit-learn）；計分本身只用標準函式庫。

用法：
    <venv>/bin/python gauge_bank.py --reproduce
    <venv>/bin/python gauge_bank.py              # 印結果並寫 gauge_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
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


def _write(ws: str, rel: str, text: str) -> None:
    p = os.path.join(ws, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text)


def reproduce() -> int:
    import solutions  # noqa: E402  需要 pandas 等，只在這一段才載入
    qs, ls = B.load()
    byid = {q["id"]: q for q in qs}
    order = B.candidate_order(qs, ls)
    results = {}
    for level in B.LEVELS:
        for qid in order[level]:
            fn = solutions.SOLUTIONS.get(qid)
            if fn is None:
                break                     # 依序檢查：第一個沒有參考解的候選之後都不看
            q = byid[qid]
            with tempfile.TemporaryDirectory() as ws:
                os.makedirs(os.path.join(ws, "data"))
                dp = os.path.join(ws, "data", q["file_name"])
                with open(dp, "wb") as f:
                    f.write(B.fetch("da-dev-tables/" + q["file_name"]))
                try:
                    items = fn(dp)
                    text = "".join(f"@{n}[{v}]\n" for n, v in items)
                    err = None
                except Exception:
                    text, err = "", traceback.format_exc(limit=2)
            exp = {"task_id": B.task_dir(qid), "common_answers": ls[qid]["common_answers"]}
            r = S.score_text(text, exp)
            results[str(qid)] = {
                "level": level, "reproduced": bool(r["abq"]), "psaq": r["psaq"],
                "reference_output": text, "error": err,
                "note": None if r["abq"] else "參考解與標準答案不符：" + ", ".join(
                    f"{n}: ref={r['predicted'][n]!r} label={v!r}"
                    for n, v in ls[qid]["common_answers"] if not r["correct"][n])}
    out = {"generated_by": "gauge_bank.py --reproduce",
           "solutions_sha256": B.sha256_bytes(open(os.path.join(HERE, "reference",
                                                                "solutions.py"), "rb").read()),
           "results": results}
    with open(B.REPRO, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    for level in B.LEVELS:
        rs = [(k, v) for k, v in results.items() if v["level"] == level]
        ok = [k for k, v in rs if v["reproduced"]]
        print(f"{level}: 檢查 {len(rs)}、重現 {len(ok)}")
        for k, v in rs:
            if not v["reproduced"]:
                print(f"   ✗ {k}: {v['note'] or v['error']}")
    return 0


def perturb(v: str) -> str:
    try:
        x = float(v)
    except ValueError:
        return v + "_x"
    return repr(x + 1.0 + abs(x) * 0.5)


def gauge() -> int:
    m = json.load(open(B.MANIFEST))
    repro = json.load(open(B.REPRO))["results"]
    rows, bad = [], 0
    for t in m["tasks"]:
        tid = t["task_id"]
        exp = json.load(open(os.path.join(B.HIDDEN, tid, "expected.json")))
        labels = exp["common_answers"]
        label_text = "".join(f"@{n}[{v}]\n" for n, v in labels)
        cases = {
            "reference": (repro[str(t["source_id"])]["reference_output"], 1),
            "label_verbatim": (label_text, 1),
            "with_prose": ("Here is my answer after running the analysis.\n\n" + label_text
                           + "\nDone.\n", 1),
            "missing": (None, 0),
            "empty": ("", 0),
            "all_wrong": ("".join(f"@{n}[{perturb(v)}]\n" for n, v in labels), 0),
            "subdir_only": ("SUBDIR", 0),
        }
        if len(labels) > 1:
            n0, v0 = labels[0]
            cases["first_only"] = (f"@{n0}[{v0}]\n" + "".join(
                f"@{n}[{perturb(v)}]\n" for n, v in labels[1:]), 0)
        got = {}
        for name, (text, want) in cases.items():
            ws = tempfile.mkdtemp()
            try:
                shutil.copytree(os.path.join(B.TEMPLATES, tid), ws, dirs_exist_ok=True)
                if text == "SUBDIR":
                    _write(ws, "out/answer.txt", label_text)
                elif text is not None:
                    _write(ws, "answer.txt", text)
                r = S.score_workspace(os.path.join(B.HIDDEN, tid), ws)
            finally:
                shutil.rmtree(ws)
            got[name] = r["abq"]
            if r["abq"] != want:
                bad += 1
                print(f"✗ {tid} {name}: abq={r['abq']} 預期 {want} ({r['status']})")
            if name == "all_wrong" and r["psaq"] != 0:
                bad += 1
                print(f"✗ {tid} all_wrong psaq={r['psaq']}")
        goal = open(os.path.join(B.TEMPLATES, tid, "goal.md")).read() + \
            open(os.path.join(B.TEMPLATES, tid, "contract.md")).read()
        leaks = [v for _, v in labels if len(v) >= 3 and re.search(
            r"(?<![\d.])" + re.escape(v) + r"(?![\d])", goal)]
        rows.append({"task_id": tid, "cases": got, "label_literal_in_template": leaks})
    n = len(rows)
    summary = {
        "n_tasks": n,
        "reference_full_marks": sum(r["cases"]["reference"] for r in rows),
        "label_full_marks": sum(r["cases"]["label_verbatim"] for r in rows),
        "missing_zero": sum(1 - r["cases"]["missing"] for r in rows),
        "empty_zero": sum(1 - r["cases"]["empty"] for r in rows),
        "all_wrong_zero": sum(1 - r["cases"]["all_wrong"] for r in rows),
        "subdir_only_zero": sum(1 - r["cases"]["subdir_only"] for r in rows),
        "first_only_zero": sum(1 - r["cases"]["first_only"] for r in rows if "first_only" in r["cases"]),
        "first_only_applicable": sum("first_only" in r["cases"] for r in rows),
        "tasks_with_label_literal_in_template": [r["task_id"] for r in rows
                                                 if r["label_literal_in_template"]],
        "verdict": "OK" if bad == 0 else f"{bad} 個格子不符",
    }
    with open(REPORT, "w") as f:
        json.dump({"summary": summary, "rows": rows}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reproduce", action="store_true")
    a = ap.parse_args()
    return reproduce() if a.reproduce else gauge()


if __name__ == "__main__":
    sys.exit(main())
