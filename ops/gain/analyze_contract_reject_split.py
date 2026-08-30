#!/usr/bin/env python3
"""把 `outside_input_contract` 這個狀態拆成兩種不同意義的拒絕。

round345 發現 GROUNDED 票幾乎從不投 FAIL（`analyze_review_gate.py` 量到
raw TN 17-33% vs grounded TN ~0%），round350 進一步查出主要拒絕理由是
`outside_input_contract`——但 `verify_review_counterexample`
（`gain_run.py:340,354`）用同一個狀態字串蓋住兩種完全不同的情況：

  1. `arity_mismatch`  —— 評審給的 TEST_ARGS 參數個數就跟函式簽名對不上，
     這是評審自己格式錯誤，不是候選解答的問題。
  2. `domain_violation` —— 參數個數對，但值不滿足題目自己宣告的 input_contract
     前置條件（評審找的「反例」根本不在合法輸入域內）。

這支不改動任何 runtime 邏輯、不重跑實驗，只是離線重讀已經落盤的
`calls.jsonl`（含 review 回應全文與 initial 生成全文，鐵律3全 I/O 落盤）
與 `rows.jsonl`，用跟 `gain_run.py` 相同的解析/AST 簽名推導邏輯重新分類。

用法：
  python3 ops/gain/analyze_contract_reject_split.py --run runs/<dir> [--json out.json]
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.gain.gain_run import extract_code, parse_review_claim  # noqa: E402


def _param_count_from_code(code: str, entry_point: str) -> int | None:
    try:
        tree = ast.parse(code)
        fn = next(
            node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == entry_point
        )
        return len(fn.args.posonlyargs) + len(fn.args.args)
    except (SyntaxError, StopIteration):
        return None


def load_calls(d: pathlib.Path) -> list[dict]:
    calls = []
    for line in (d / "calls.jsonl").open(encoding="utf-8"):
        line = line.strip()
        if line:
            calls.append(json.loads(line))
    return calls


def load_on_rows(d: pathlib.Path) -> list[dict]:
    rows = []
    for line in (d / "rows.jsonl").open(encoding="utf-8"):
        line = line.strip()
        if line:
            r = json.loads(line)
            if r.get("arm") == "ON":
                rows.append(r)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--json")
    args = ap.parse_args()
    d = pathlib.Path(args.run)
    rows = load_on_rows(d)
    calls = load_calls(d)

    # initial generation text，一題一份（phase=initial）
    initial_by_task: dict[str, str] = {}
    for c in calls:
        meta = c.get("meta") or {}
        if meta.get("arm") == "ON" and meta.get("phase") == "initial" and c.get("ok"):
            initial_by_task.setdefault(meta.get("task_id"), c.get("response", ""))

    # review 回應全文，key = (task_id, agent_id)
    review_text_by_key: dict[tuple, str] = {}
    for c in calls:
        if c.get("role") != "review":
            continue
        meta = c.get("meta") or {}
        key = (meta.get("task_id"), c.get("agent_id"))
        if c.get("ok"):
            review_text_by_key[key] = c.get("response", "")

    split = collections.Counter()
    unresolved = 0
    examples = collections.defaultdict(list)
    for r in rows:
        task_id = r["task_id"]
        entry_point = r.get("entry_point")
        initial_code = extract_code(initial_by_task.get(task_id, ""))
        n_params = _param_count_from_code(initial_code, entry_point) if entry_point else None
        for e in r["review_evidence"]:
            if e["status"] != "outside_input_contract":
                continue
            text = review_text_by_key.get((task_id, e["agent_id"]))
            if text is None:
                split["missing_call_log"] += 1
                unresolved += 1
                continue
            claim = parse_review_claim(text)
            if claim is None:
                split["reclassified_as_unparseable"] += 1
                continue
            claimed_args, _expected = claim
            if n_params is None:
                split["unknown_signature"] += 1
                unresolved += 1
                continue
            if len(claimed_args) != n_params:
                split["arity_mismatch"] += 1
                if len(examples["arity_mismatch"]) < 3:
                    examples["arity_mismatch"].append(
                        {"task_id": task_id, "agent_id": e["agent_id"],
                         "n_params": n_params, "n_claimed_args": len(claimed_args)})
            else:
                split["domain_violation"] += 1
                if len(examples["domain_violation"]) < 3:
                    examples["domain_violation"].append(
                        {"task_id": task_id, "agent_id": e["agent_id"]})

    total = sum(split.values())
    print(f"--- outside_input_contract 拆解（n={total}, 其中 {unresolved} 筆缺資料無法判定）---")
    for k, v in split.most_common():
        print(f"  {k}: {v} ({100*v/total:.1f}%)" if total else f"  {k}: {v}")
    print()
    print("樣本（各取前 3 筆）：")
    print(json.dumps(dict(examples), ensure_ascii=False, indent=2))

    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps({"run": str(d), "n": total, "unresolved": unresolved,
                        "split": dict(split), "examples": dict(examples)},
                       ensure_ascii=False, indent=2),
            encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
