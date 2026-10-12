#!/usr/bin/env python3
"""把「樣板＋隱藏」格式的程式題庫（R534／BCB／colab_banks_20260927 同一個格式）轉成 cell.sh 吃的題目目錄。

    python3 stage_code_bank.py --bank <名字> --templates <templates 目錄> --hidden <hidden 目錄> --out <staged 根目錄> \
        [--ids a b …] [--manifest bank_manifest.json]

每題輸出 `<out>/<bank>/<id>/`：
- `instruction.txt`：給 pi 的那一句（與 2026-09-24 BCB 批次相同：只叫它讀 goal.md 與 contract.md）
- `workspace/`：樣板整份（goal.md、contract.md、tests_visible/、run_tests.sh）——agent 看到的就是這些
- `hidden/test_hidden.py` ＋ `hidden/tests_visible/`（**原本的**可見測試，計分用；agent 改工作區裡的那份不影響計分）
- `scorer.py`：scorers/code_suite.py（量具同一套判準）
並印出 plan.json 要的 tasks 陣列（JSON）。有 `--manifest` 時只收 manifest 裡沒被排除的題。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil

HERE = pathlib.Path(__file__).resolve().parent
PROMPT = "Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file."


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", required=True)
    ap.add_argument("--templates", required=True, type=pathlib.Path)
    ap.add_argument("--hidden", required=True, type=pathlib.Path)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--vm-root", default="/srv/eval/staged", help="VM 上 staged 根目錄（寫進 plan 的 dir）")
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--manifest", type=pathlib.Path)
    a = ap.parse_args()
    ids = a.ids or sorted(p.name for p in a.templates.iterdir() if p.is_dir())
    if a.manifest:
        m = json.loads(a.manifest.read_text())
        rows = m.get("tasks") or m.get("items") or m
        usable = {r["id"] for r in rows if isinstance(r, dict) and not r.get("excluded") and not r.get("exclude_reason")}
        ids = [i for i in ids if i in usable]
    tasks = []
    for tid in ids:
        src, hid = a.templates / tid, a.hidden / tid / "test_hidden.py"
        if not (src / "goal.md").is_file() or not hid.is_file():
            raise SystemExit(f"{tid}: 缺 goal.md 或 test_hidden.py")
        d = a.out / a.bank / tid
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(src, d / "workspace")
        (d / "hidden").mkdir(parents=True)
        shutil.copy2(hid, d / "hidden" / "test_hidden.py")
        shutil.copytree(src / "tests_visible", d / "hidden" / "tests_visible")
        shutil.copy2(HERE / "scorers" / "code_suite.py", d / "scorer.py")
        (d / "instruction.txt").write_text(PROMPT + "\n")
        tasks.append({"bank": a.bank, "id": tid, "dir": f"{a.vm_root}/{a.bank}/{tid}"})
    print(json.dumps(tasks, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
