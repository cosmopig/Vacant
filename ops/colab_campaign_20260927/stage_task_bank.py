#!/usr/bin/env python3
"""把任務題庫 agent 的「templates／hidden」格式（`ops/vacantrun/task_banks_20260927/{dabench,databench,polyglot_py}`）
轉成 `cell.sh` 吃的題目目錄格式（第二批，任務導向三題庫；PLAN_BATCH2_TASK3.md 步驟 2）。

    python3 stage_task_bank.py --bank <dabench|databench|polyglot_py> --templates <templates 目錄> \
        --hidden <hidden 目錄> --scorer <scorers/<bank>.py> --out <staged 根目錄> \
        [--ids a b …] [--manifest bank_manifest.json]

每題輸出 `<out>/<bank>/<id>/`：
- `instruction.txt`：給 pi 的那一句（PLAN 步驟 2 明講：**用第一批同一句**，不改這一句）。
- `workspace/`：`templates/<id>/` 整份原樣複製——agent 看到的就是這些（不含 hidden／reference）。
- `hidden/`：`hidden/<id>/` 整份原樣複製（`expected.json`，polyglot 另有 `tests/`）。
- `scorer.py`：對應題庫的 `scorers/<bank>.py`。
並印出 plan.json 要的 tasks 陣列（JSON），dir 欄位用 `--vm-root`（VM 上 staged 根目錄）。

`--manifest` 時只收 manifest `tasks` 裡沒被標記 `excluded`／`exclude_reason` 的題 id（三個 pilot
manifest 目前的 `tasks` 陣列本來就只列已選中的題，這個開關是保險，不是必要條件）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil

PROMPT = "Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file."


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", required=True, choices=["dabench", "databench", "polyglot_py"])
    ap.add_argument("--templates", required=True, type=pathlib.Path)
    ap.add_argument("--hidden", required=True, type=pathlib.Path)
    ap.add_argument("--scorer", required=True, type=pathlib.Path)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--vm-root", default="/srv/eval/staged", help="VM 上 staged 根目錄（寫進 plan 的 dir）")
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--manifest", type=pathlib.Path)
    a = ap.parse_args()

    ids = a.ids or sorted(p.name for p in a.templates.iterdir() if p.is_dir())
    if a.manifest:
        m = json.loads(a.manifest.read_text())
        rows = m.get("tasks", [])
        usable = {r["task_id"] for r in rows if isinstance(r, dict)
                  and not r.get("excluded") and not r.get("exclude_reason")}
        ids = [i for i in ids if i in usable]

    tasks = []
    for tid in ids:
        src, hid = a.templates / tid, a.hidden / tid
        if not src.is_dir() or not hid.is_dir():
            raise SystemExit(f"{tid}: 缺 templates/{tid} 或 hidden/{tid}")
        if not (hid / "expected.json").is_file():
            raise SystemExit(f"{tid}: hidden/{tid} 缺 expected.json")
        d = a.out / a.bank / tid
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(src, d / "workspace")
        shutil.copytree(hid, d / "hidden")
        shutil.copy2(a.scorer, d / "scorer.py")
        (d / "instruction.txt").write_text(PROMPT + "\n")
        tasks.append({"bank": a.bank, "id": tid, "dir": f"{a.vm_root}/{a.bank}/{tid}"})
    print(json.dumps(tasks, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
