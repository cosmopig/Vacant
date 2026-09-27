#!/usr/bin/env python3
"""把公開的 HumanEval（OpenAI，MIT）拆成 Vacant 要的 V/GT 工作區。

**題庫是第三方的、公開的、有公開 pass@1 數字的**——這一批刻意不用本 repo 自己的題庫。
來源：https://raw.githubusercontent.com/openai/human-eval/master/data/HumanEval.jsonl.gz

## 抽樣：等距，不挑題

`range(0, 164, STRIDE)`。**沒有隨機種子、沒有人工挑選**，所以「挑到好做的題」這件事
在流程上不可表達。要換題數就換 STRIDE，清單會跟著確定性地變。

## 可見 ↔ 隱藏（與 r534 同一個關係：可見 ⊂ 隱藏）

· **可見**＝官方 `check(candidate)` 裡**前 N 條 assert**（含它們前面的 setup 陳述），
  渲染成 `tests_visible/test_visible.py` 的 `check_visible_XX()`。閘門看這一份。
· **隱藏**＝官方 `check(candidate)` **整份**，一題一個布林。那就是 HumanEval 的
  標準計分方式（pass@1，n=1 樣本），所以算出來的數字跟外面公布的是同一把尺。

⚠ 可見是隱藏的子集 ⇒ 「過了可見卻沒過隱藏」量得出來（假交付）。
⚠ 隱藏那份**永遠不進工作區**，失敗訊息也不回饋給模型。
"""
from __future__ import annotations

import ast
import gzip
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
STRIDE = int(sys.argv[1]) if len(sys.argv) > 1 else 8
VISIBLE_ASSERTS = 2

CONTRACT = """# Contract

Write your answer in `solution.py` at the root of this workspace.

- Define a top-level function named `{entry}`. Not a method, not a class.
- It must **return** the answer. Printing is not returning.
- Standard library only. No network, no installed packages.
- Keep the same signature as the stub in `goal.md`.

The checks that ship with this task are in `tests_visible/`. Run them with:

    sh run_tests.sh
"""

RUN_TESTS = """#!/bin/sh
# Run the checks that ship with this task against the current directory.
exec python3 - "$@" <<'PY'
import importlib.util, os, sys, traceback
sys.path.insert(0, os.getcwd())
failed = 0
d = os.path.join(os.getcwd(), "tests_visible")
for name in sorted(os.listdir(d)):
    if not (name.startswith("test_") and name.endswith(".py")):
        continue
    spec = importlib.util.spec_from_file_location("vis_" + name[:-3], os.path.join(d, name))
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        failed += 1
        print("%s: could not be imported" % name)
        traceback.print_exc()
        continue
    for cname, fn in [(n, v) for n, v in vars(mod).items()
                      if n.startswith("check_") and callable(v)]:
        try:
            fn()
        except Exception as e:
            failed += 1
            print("FAIL %s::%s  %s: %s" % (name, cname, type(e).__name__, e))
        else:
            print("pass %s::%s" % (name, cname))
print("%d check(s) failed" % failed)
sys.exit(1 if failed else 0)
PY
"""

VIS_HEADER = '''"""Visible checks for {tid} — a strict SUBSET of the official HumanEval test.

Rendered from HumanEval.jsonl.gz (openai/human-eval, MIT) by build.py.
The official full test is the hidden ruler and never enters this workspace.
"""

import solution

'''


def visible_src(tid: str, entry: str, test_src: str, n: int) -> str | None:
    """把官方 check() 的前 n 條 assert 渲染成獨立的 check_visible_XX()。"""
    try:
        tree = ast.parse(test_src)
    except SyntaxError:
        return None
    fn = next((x for x in tree.body
               if isinstance(x, ast.FunctionDef) and x.name == "check"), None)
    if fn is None:
        return None
    setup, asserts = [], []
    for st in fn.body:
        if isinstance(st, ast.Assert):
            asserts.append(st)
            if len(asserts) >= n:
                break
        else:
            setup.append(st)
    if not asserts:
        return None
    setup_src = "\n".join("    " + ast.unparse(s) for s in setup)
    out = [VIS_HEADER.format(tid=tid)]
    for i, a in enumerate(asserts, 1):
        body = [f"    candidate = solution.{entry}"]
        if setup_src:
            body.append(setup_src)
        body.append("    " + ast.unparse(a))
        out.append(f"def check_visible_{i:02d}():\n" + "\n".join(body) + "\n")
    return "\n".join(out)


def main() -> int:
    rows = [json.loads(l) for l in gzip.open(HERE / "HumanEval.jsonl.gz", "rt")]
    picked, skipped = [], []
    tasks_dir = HERE / "tasks"
    hidden_dir = HERE / "hidden"
    for i in range(0, len(rows), STRIDE):
        r = rows[i]
        tid = r["task_id"].replace("/", "_")          # HumanEval/0 -> HumanEval_0
        vis = visible_src(tid, r["entry_point"], r["test"], VISIBLE_ASSERTS)
        if vis is None:
            skipped.append({"task_id": r["task_id"], "why": "沒有可抽的 assert"})
            continue
        d = tasks_dir / tid
        (d / "tests_visible").mkdir(parents=True, exist_ok=True)
        (d / "goal.md").write_text(
            "Complete the following Python function.\n\n```python\n"
            + r["prompt"].rstrip() + "\n```\n", encoding="utf-8")
        (d / "contract.md").write_text(
            CONTRACT.format(entry=r["entry_point"]), encoding="utf-8")
        (d / "run_tests.sh").write_text(RUN_TESTS, encoding="utf-8")
        (d / "tests_visible" / "test_visible.py").write_text(vis, encoding="utf-8")
        h = hidden_dir / tid
        h.mkdir(parents=True, exist_ok=True)
        (h / "official_test.py").write_text(r["test"], encoding="utf-8")
        (h / "meta.json").write_text(json.dumps(
            {"task_id": r["task_id"], "entry_point": r["entry_point"]},
            ensure_ascii=False), encoding="utf-8")
        picked.append({"task_id": r["task_id"], "dir": tid,
                       "entry_point": r["entry_point"]})
    (HERE / "manifest.json").write_text(json.dumps({
        "source": "https://raw.githubusercontent.com/openai/human-eval/master/data/HumanEval.jsonl.gz",
        "total_in_bank": len(rows), "stride": STRIDE,
        "visible_asserts": VISIBLE_ASSERTS,
        "picked_n": len(picked), "picked": picked, "skipped": skipped,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"抽了 {len(picked)} 題（等距 stride={STRIDE}），跳過 {len(skipped)}")
    for p in picked:
        print("  ", p["task_id"], p["entry_point"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
