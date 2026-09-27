#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DABench pilot 的隱藏計分器：讀工作區的 `answer.txt`，用官方判等規則對 `hidden/<id>/expected.json`。

這支在架構裡承重什麼：A/B 兩臂的分子。**只依賴標準函式庫**（root 在 Colab 上直接跑，不需要分析用的 venv）。

出處（逐字搬過來、不改判準）：InfiAgent/InfiAgent@3d6c4a70 的
`examples/DA-Agent/eval_closed_form.py`——`extract_format`（正規式 `@(\\w+)\\[(.*?)\\]`，
同名取最後一個）與 `is_equal`（字串相等，或兩邊 float 差 < 1e-6）。每題：
- `abq`（主指標）＝每個子答案都判對 ⇒ 1，否則 0（官方 Accuracy by Question）
- `psaq`＝判對的子答案比例（官方 Accuracy Proportional by Sub-Question）

與官方不同的地方（寫進 manifest，不准省略）：
1. 官方在計分前用 GPT-3.5 把回應改寫成 `@name[value]` 格式；這裡沒有這一步，agent 自己寫。
2. `answer.txt` 不存在／讀不出文字／空的／抽不到任何 `@name[value]` ⇒ 0 分，**留在分母**
   （官方的 `evaluate_responses` 會把沒有回應的題直接略過，分母變小）。`status` 欄分開記這幾種。
3. 只讀工作區**根目錄**的 `answer.txt`（contract.md 寫明的位置）。子資料夾裡同名的檔不算。

用法：
    python3 score.py --hidden hidden/dab_427 --workspace /path/to/ws      # 印一行 JSON
    python3 score.py --hidden-root hidden --runs runs.tsv                   # 批次：每行 task_id<TAB>ws
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

MAX_ANSWER_BYTES = 1_000_000


# ── 官方 eval_closed_form.py（逐字） ─────────────────────────────────────
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


def score_text(text: str | None, expected: dict) -> dict:
    labels = {n: v for n, v in expected["common_answers"]}
    if text is None:
        status = "missing"
        extracted: dict[str, str] = {}
    else:
        names, answers = extract_format(text)
        extracted = dict(zip(names, answers))
        status = "ok" if extracted else ("empty" if not text.strip() else "no_items")
    correct = {n: bool(is_equal(extracted.get(n), v)) for n, v in labels.items()}
    n_ok = sum(correct.values())
    return {"task_id": expected["task_id"], "status": status,
            "abq": int(bool(labels) and n_ok == len(labels)),
            "psaq": round(n_ok / len(labels), 6) if labels else 0.0,
            "n_items": len(labels), "n_correct": n_ok, "correct": correct,
            "predicted": {n: extracted.get(n) for n in labels}}


def read_answer(workspace: str) -> str | None:
    p = os.path.join(workspace, "answer.txt")
    if not os.path.isfile(p) or os.path.islink(p):
        return None
    raw = open(p, "rb").read(MAX_ANSWER_BYTES + 1)
    try:
        return raw[:MAX_ANSWER_BYTES].decode("utf-8", errors="replace")
    except Exception:
        return None


def score_workspace(hidden_dir: str, workspace: str) -> dict:
    expected = json.load(open(os.path.join(hidden_dir, "expected.json")))
    return score_text(read_answer(workspace), expected)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hidden")
    ap.add_argument("--workspace")
    ap.add_argument("--hidden-root")
    ap.add_argument("--runs", help="TSV：task_id<TAB>workspace")
    a = ap.parse_args()
    if a.runs:
        for line in open(a.runs):
            if not line.strip():
                continue
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
