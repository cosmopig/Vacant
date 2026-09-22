#!/usr/bin/env python3
"""把 **LiveCodeBench v6**（公開、第三方、競賽題）拆成 Vacant 要的 V/GT 工作區。

## 為什麼換這個題庫

上一批（HumanEval）兩臂都 100%，因為題目對「有可執行驗收可以自我迭代的 agent」
太簡單。這一批換成**競賽難題**，而且——關鍵——**可見與隱藏的落差是題庫自己給的**：

· **可見** ＝ `public_test_cases`（題目頁面上看得到的 2 條小範例）
· **隱藏** ＝ `private_test_cases` ＋ public（約 42 條，含**很大的輸入**）

⇒ 「過了可見卻過不了隱藏」在這裡是**會發生的事**（naive 演算法、超時），
   那正是閘門與假交付要量的東西。上一批那個落差幾乎不存在，所以分不開。

## 抽樣：等距，不挑題

leetcode 平台（函式型，對得上 `solution.py` 的契約）的 **medium 與 hard 各取 10 題**，
各自依 `question_id` 排序後等距取。沒有隨機種子、沒有人工挑選。
（atcoder 是 stdin/stdout 型，與本契約不同，整批排除。）

## 判等與逾時

判等沿用本 repo 的 `_aeq`（與 `vacant_network/codebench.py::_lcb_check_code` 逐行同義）。
每條 case 逾時 10 秒、每題總上限 180 秒——**超時算不過**，那是競賽語意，不是量具壞掉。
"""
from __future__ import annotations

import base64
import json
import pathlib
import pickle
import sys
import zlib

HERE = pathlib.Path(__file__).resolve().parent
PER_DIFF = int(sys.argv[1]) if len(sys.argv) > 1 else 10
#: **污染窗**：只收比賽日期在這之後的題。模型自稱截止 2025-01（實測：它記得
#: "Two Sum"，但本批 9 個題目標題全部答 UNKNOWN），這裡再多留一個月的邊。
MIN_DATE = sys.argv[2] if len(sys.argv) > 2 else "2025-02-01"

CONTRACT = """# Contract

Write your answer in `solution.py` at the root of this workspace.

- Define a top-level function named `{entry}`. Not a method, not a class.
- It is called positionally: `{entry}(*args)`. The checks pass the arguments
  in the order the task statement gives them.
- It must **return** the answer. Printing is not returning.
- Standard library only. No network, no installed packages.
- Large inputs are used. An algorithm that is correct but too slow will fail.

The checks that ship with this task are in `tests_visible/`. Run them with:

    sh run_tests.sh
"""

RUN_TESTS = pathlib.Path(
    "/tmp/claude-0/-home-user-Vacant/95031510-877c-5775-9ca5-176a6cda6673"
    "/scratchpad/he/tasks/HumanEval_0/run_tests.sh")

AEQ = '''
def _aeq(a, b):
    """與 vacant_network/codebench.py::_lcb_check_code 的 __aeq 同一套判等。"""
    try:
        if a == b:
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= 1e-6
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_aeq(x, y) for x, y in zip(a, b))
    return a == b
'''


def parse_case(c: dict) -> tuple[list, object] | None:
    """LCB 的 case：`input` 是逐行的 JSON 引數，`output` 是 JSON。"""
    try:
        args = [json.loads(x) for x in c["input"].split("\n") if x.strip() != ""]
        want = json.loads(c["output"])
    except Exception:                                        # noqa: BLE001
        return None
    return args, want


def main() -> int:
    rows = [json.loads(l) for l in open(HERE / "test6.jsonl")]
    lc = [r for r in rows if r["platform"] == "leetcode"]
    picked, skipped = [], []
    for diff in ("medium", "hard"):
        pool = sorted([r for r in lc if r["difficulty"] == diff
                       and r["contest_date"] >= MIN_DATE],
                      key=lambda r: int(r["question_id"]))
        stride = max(1, len(pool) // PER_DIFF)
        sel = pool[::stride][:PER_DIFF]
        for r in sel:
            qid = r["question_id"]
            tid = f"lcbv6_{qid}"
            entry = json.loads(r["metadata"]).get("func_name")
            if not entry:
                skipped.append({"qid": qid, "why": "沒有 func_name"})
                continue
            pub = json.loads(r["public_test_cases"])
            priv = json.loads(pickle.loads(zlib.decompress(
                base64.b64decode(r["private_test_cases"].encode()))))
            vis = [parse_case(c) for c in pub]
            vis = [v for v in vis if v]
            allc = [parse_case(c) for c in pub + priv]
            allc = [v for v in allc if v]
            if not vis or len(allc) < 5:
                skipped.append({"qid": qid, "why": "測資解析不出來"})
                continue
            d = HERE / "tasks" / tid
            (d / "tests_visible").mkdir(parents=True, exist_ok=True)
            (d / "goal.md").write_text(
                f"# {r['question_title']}\n\n{r['question_content']}\n\n"
                f"---\n\n請寫一個**頂層** Python 函式（不要用 class）：\n\n"
                f"```python\ndef {entry}(...):\n    ...\n```\n\n"
                f"只能用標準函式庫。函式必須**回傳**答案，不要印出。\n",
                encoding="utf-8")
            (d / "contract.md").write_text(CONTRACT.format(entry=entry),
                                           encoding="utf-8")
            (d / "run_tests.sh").write_text(RUN_TESTS.read_text(), encoding="utf-8")
            body = [f'"""Visible checks for {tid} — LiveCodeBench v6 的 '
                    f'public_test_cases（題目頁面上看得到的那幾條）。"""',
                    "", "import solution", AEQ, ""]
            for i, (args, want) in enumerate(vis, 1):
                body.append(f"def check_visible_{i:02d}():\n"
                            f"    args = {args!r}\n"
                            f"    want = {want!r}\n"
                            f"    got = solution.{entry}(*args)\n"
                            f"    assert _aeq(got, want), "
                            f'"args=%r got=%r want=%r" % (args, got, want)\n')
            (d / "tests_visible" / "test_visible.py").write_text(
                "\n".join(body), encoding="utf-8")
            h = HERE / "hidden" / tid
            h.mkdir(parents=True, exist_ok=True)
            (h / "cases.json").write_text(json.dumps(
                {"entry_point": entry, "cases": [{"args": a, "want": w}
                                                 for a, w in allc]},
                ensure_ascii=False), encoding="utf-8")
            picked.append({"task_id": tid, "qid": qid, "entry_point": entry,
                           "difficulty": diff, "title": r["question_title"],
                           "contest_date": r["contest_date"][:10],
                           "visible_n": len(vis), "hidden_n": len(allc)})
    (HERE / "manifest.json").write_text(json.dumps({
        "source": "https://huggingface.co/datasets/livecodebench/code_generation_lite (test6.jsonl)",
        "platform": "leetcode only（atcoder 是 stdin/stdout 型，排除）",
        "per_difficulty": PER_DIFF, "min_contest_date": MIN_DATE, "picked_n": len(picked),
        "picked": picked, "skipped": skipped,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"抽了 {len(picked)} 題，跳過 {len(skipped)}")
    for p in picked:
        print(f"  {p['task_id']:<14}{p['difficulty']:<8}{p['contest_date']}  "
              f"可見 {p['visible_n']:<3}隱藏 {p['hidden_n']:<4}{p['title'][:44]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
