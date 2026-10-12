#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DataBench（SemEval-2025 Task 8）pilot 的 cell.sh 版計分器：
`python3 scorer.py <hidden 目錄> <最後的工作區目錄>`，stdout 最後一行是一個 JSON 物件，
至少有 `"pass": true|false`（`ops/colab_campaign_20260927/PLAN_BATCH2_TASK3.md` 步驟 3）。

判準逐字搬自 `ops/vacantrun/task_banks_20260927/databench/score.py`（那支的出處：PyPI
`databench-eval` 4.0.1，MIT，`databench_eval/eval.py::Evaluator.default_compare`，
只拿掉 `self`）。只把介面換成 cell.sh 的位置參數，`correct` 映成 `pass`。

只讀工作區**根目錄**的 `answer.txt`，取第一個非空行；不存在／讀不到／沒有非空行都是 0 分，
`note` 記原因。需要 pandas＋numpy（PLAN 步驟 20 允許：Colab 系統 python 本來就有）。
**任何例外都吞下並輸出 JSON**（沒輸出＝那一格被判 infra_void）。
"""
from __future__ import annotations

import json
import math
import os
import sys

MAX_ANSWER_BYTES = 1_000_000


def _score(hidden_dir: str, workspace: str) -> dict:
    import numpy as np
    import pandas as pd

    # ── 逐字搬自 databench-eval 4.0.1 Evaluator.default_compare（只把 self 拿掉） ──
    def default_compare(value, truth, semantic):
        STRIP_CHARS = "[]'\" "
        semantic = semantic.strip()
        valid_null_set = [None, "nan", "", " ", np.nan, "np.nan", "None"]

        if str(value).strip(STRIP_CHARS) in valid_null_set and str(truth).strip(STRIP_CHARS) in valid_null_set:
            return True
        if str(value).strip(STRIP_CHARS) in valid_null_set or str(truth).strip(STRIP_CHARS) in valid_null_set:
            return False

        if semantic == "boolean":
            valid_true_values = ['true', 'yes', 'y']
            valid_false_values = ['false', 'no', 'n']
            value_str = str(value).strip(STRIP_CHARS).lower()
            truth_str = str(truth).strip(STRIP_CHARS).lower()
            return (value_str in valid_true_values and truth_str in valid_true_values) or (value_str in valid_false_values and truth_str in valid_false_values)
        elif semantic == "category":
            value_str = str(value).strip(STRIP_CHARS)
            truth_str = str(truth).strip(STRIP_CHARS)
            if value_str == truth_str:
                return True

            try:
                value_date = pd.to_datetime(value_str).date()
                truth_date = pd.to_datetime(truth_str).date()
                return value_date == truth_date
            except (ValueError, TypeError):
                if not value_str and not truth_str:
                    return True
                return value_str == truth_str
        elif semantic == "number":
            try:
                value_cleaned = ''.join(char for char in str(value) if char.isdigit() or char in ['.', '-'])
                truth_cleaned = ''.join(char for char in str(truth) if char.isdigit() or char in ['.', '-'])
                return math.trunc(float(value_cleaned) * 100) == math.trunc(float(truth_cleaned) * 100)
            except:  # noqa: E722  官方原文
                return False
        elif semantic == "list[category]":
            try:
                value_list = [item.strip(STRIP_CHARS) for item in str(value).strip('[]').split(',')]
                truth_list = [item.strip(STRIP_CHARS) for item in str(truth).strip('[]').split(',')]
                value_list = [
                    v if v not in valid_null_set else ""
                    for v in value_list
                ]
                truth_list = [
                    t if t not in valid_null_set else "" for t in truth_list
                ]
                if len(value_list) != len(truth_list):
                    return False

                # Attempt to parse each item as a date
                try:
                    value_dates = [pd.to_datetime(item).date() for item in value_list]
                    truth_dates = [pd.to_datetime(item).date() for item in truth_list]
                    return set(value_dates) == set(truth_dates)
                except (ValueError, TypeError):
                    # If parsing as dates fails, compare as strings
                    return set(value_list) == set(truth_list)
            except Exception as exc:  # noqa: F841
                return False
        elif semantic == "list[number]":
            try:
                value_list = sorted(float(''.join(c for c in v.strip() if c.isdigit() or c in ['.', '-'])) for v in str(value).strip('[]').split(',') if v.strip())
                truth_list = sorted(float(''.join(c for c in t.strip() if c.isdigit() or c in ['.', '-'])) for t in str(truth).strip('[]').split(',') if t.strip())

                value_list = [int(v * 100) / 100 for v in value_list]
                truth_list = [int(t * 100) / 100 for t in truth_list]

                if len(value_list) != len(truth_list):
                    return False

                return set(value_list) == set(truth_list)
            except Exception as exc:  # noqa: F841
                return False
        else:
            raise Exception(f"Semantic not supported: {semantic}")
    # ── 官方逐字結束 ─────────────────────────────────────────────────────────

    exp = json.load(open(os.path.join(hidden_dir, "expected.json")))
    p = os.path.join(workspace, "answer.txt")
    value, status = None, "missing"
    if os.path.isfile(p) and not os.path.islink(p):
        text = open(p, "rb").read(MAX_ANSWER_BYTES).decode("utf-8", errors="replace")
        status = "empty"
        for ln in text.splitlines():
            if ln.strip():
                value, status = ln.rstrip("\r\n"), "ok"
                break
    ok = bool(value is not None and default_compare(value, exp["answer"], exp["type"]))
    note = None if ok else f"status={status}; predicted={value!r}; expected_type={exp['type']}"
    return {"pass": ok, "correct": int(ok), "status": status, "note": note,
            "task_id": exp.get("task_id"), "type": exp.get("type"), "predicted": value}


def main() -> int:
    if len(sys.argv) != 3:
        print(json.dumps({"pass": False, "note": "usage: scorer.py <hidden_dir> <workspace_dir>"}))
        return 0
    hidden_dir, workspace = sys.argv[1], sys.argv[2]
    try:
        result = _score(hidden_dir, workspace)
    except Exception as e:  # 不准丟例外沒輸出（含 pandas/numpy 匯入失敗）
        result = {"pass": False, "note": f"scorer_error: {type(e).__name__}: {e}"}
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
