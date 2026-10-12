#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DABench pilot 的 cell.sh 版計分器：`python3 scorer.py <hidden 目錄> <最後的工作區目錄>`，
stdout 最後一行是一個 JSON 物件，至少有 `"pass": true|false`（第二批任務題庫的格式，
`ops/colab_campaign_20260927/PLAN_BATCH2_TASK3.md` 步驟 3）。

判準逐字搬自 `ops/vacantrun/task_banks_20260927/dabench/score.py`（那支的出處：
InfiAgent/InfiAgent@3d6c4a70 的 `examples/DA-Agent/eval_closed_form.py`——
`extract_format`（正規式 `@(\\w+)\\[(.*?)\\]`，同名取最後一個）與
`is_equal`（字串相等，或兩邊 float 差 < 1e-6））。只把介面換成 cell.sh 的位置參數，
`abq`（主指標，每個子答案都對才算 1）映成 `pass`。

只讀工作區**根目錄**的 `answer.txt`；不存在／讀不到／空的／抽不到任何 `@name[value]` 都是 0 分，
`note` 記原因。**任何例外都吞下並輸出 JSON**（沒輸出＝那一格被判 infra_void，PLAN 步驟 20）。
"""
from __future__ import annotations

import json
import os
import re
import sys

MAX_ANSWER_BYTES = 1_000_000


# ── 逐字搬自 InfiAgent/InfiAgent@3d6c4a70 examples/DA-Agent/eval_closed_form.py ──
def extract_format(input_string):
    pattern = r"@(\w+)\[(.*?)\]"
    matches = re.findall(pattern, input_string)
    answer_names = [match[0] for match in matches]
    answers = [match[1] for match in matches]
    return answer_names, answers


def is_equal(response, label):
    if response == label:
        return True
    else:
        try:
            return abs(float(response) - float(label)) < 1e-6
        except:  # noqa: E722  官方原文就是 bare except
            return False
# ── 官方逐字結束 ─────────────────────────────────────────────────────────


def read_answer(workspace: str) -> str | None:
    p = os.path.join(workspace, "answer.txt")
    if not os.path.isfile(p) or os.path.islink(p):
        return None
    raw = open(p, "rb").read(MAX_ANSWER_BYTES + 1)
    try:
        return raw[:MAX_ANSWER_BYTES].decode("utf-8", errors="replace")
    except Exception:
        return None


def score(hidden_dir: str, workspace: str) -> dict:
    exp = json.load(open(os.path.join(hidden_dir, "expected.json")))
    labels = {n: v for n, v in exp["common_answers"]}
    text = read_answer(workspace)
    if text is None:
        status, extracted = "missing", {}
    else:
        names, answers = extract_format(text)
        extracted = dict(zip(names, answers))
        status = "ok" if extracted else ("empty" if not text.strip() else "no_items")
    correct = {n: bool(is_equal(extracted.get(n), v)) for n, v in labels.items()}
    n_ok = sum(correct.values())
    abq = int(bool(labels) and n_ok == len(labels))
    psaq = round(n_ok / len(labels), 6) if labels else 0.0
    note = None if abq else f"status={status}; n_correct={n_ok}/{len(labels)}"
    return {"pass": bool(abq), "abq": abq, "psaq": psaq, "status": status, "note": note,
            "task_id": exp.get("task_id"), "n_items": len(labels)}


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
