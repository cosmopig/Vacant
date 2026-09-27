#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DataBench pilot 的隱藏計分器：讀工作區 `answer.txt` 的第一個非空行，用官方判等對 `hidden/<id>/expected.json`。

這支在架構裡承重什麼：A/B 兩臂的分子。

出處（逐字搬過來、不改判準）：PyPI `databench-eval` 4.0.1（MIT，Jorge Osés Grijalba）的
`databench_eval/eval.py::Evaluator.default_compare`——SemEval-2025 Task 8 官方計分器。
重點：boolean 接受 true/yes/y、false/no/n；number 取 `trunc(x*100)` 相等（截到小數兩位，不是四捨五入）；
category 字串相等，否則試著當日期比；list 類比「集合相等＋長度相等」（順序不管）。
需要 pandas＋numpy（官方判等用 `pd.to_datetime`、`np.nan`）。

與官方不同的地方（manifest 逐條記）：
1. 官方一個 predictions.txt 一行一題；這裡每題一個 `answer.txt`，取**第一個非空行**（去掉行尾換行）。
2. `answer.txt` 不存在／讀不出來／沒有非空行 ⇒ 0 分，`status` 分開記。
3. 只讀工作區**根目錄**的 `answer.txt`。

用法：
    python3 score.py --hidden hidden/db_066_08 --workspace /path/to/ws
    python3 score.py --hidden-root hidden --runs runs.tsv
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
import pandas as pd

MAX_ANSWER_BYTES = 1_000_000


# ── databench_eval 4.0.1 Evaluator.default_compare（逐字，只把 self 拿掉） ──
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


def first_line(workspace: str) -> tuple[str | None, str]:
    p = os.path.join(workspace, "answer.txt")
    if not os.path.isfile(p) or os.path.islink(p):
        return None, "missing"
    text = open(p, "rb").read(MAX_ANSWER_BYTES).decode("utf-8", errors="replace")
    for ln in text.splitlines():
        if ln.strip():
            return ln.rstrip("\r\n"), "ok"
    return None, "empty"


def score_value(value: str | None, expected: dict, status: str = "ok") -> dict:
    ok = bool(value is not None and default_compare(value, expected["answer"], expected["type"]))
    return {"task_id": expected["task_id"], "type": expected["type"], "status": status,
            "correct": int(ok), "predicted": value}


def score_workspace(hidden_dir: str, workspace: str) -> dict:
    exp = json.load(open(os.path.join(hidden_dir, "expected.json")))
    value, status = first_line(workspace)
    return score_value(value, exp, status)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hidden")
    ap.add_argument("--workspace")
    ap.add_argument("--hidden-root")
    ap.add_argument("--runs")
    a = ap.parse_args()
    if a.runs:
        for line in open(a.runs):
            if line.strip():
                tid, ws = line.rstrip("\n").split("\t")[:2]
                print(json.dumps(score_workspace(os.path.join(a.hidden_root, tid), ws),
                                 ensure_ascii=False, sort_keys=True))
        return 0
    if not (a.hidden and a.workspace):
        ap.error("需要 --hidden 與 --workspace（或 --hidden-root 與 --runs）")
    print(json.dumps(score_workspace(a.hidden, a.workspace), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
