"""把 infra_void 的格子移到一旁，讓 `run_batch.py` 照順序補跑一次（預註冊第四節；2026-09-26）。

`run_batch.py` 只看有沒有 `result.json` 決定一格跑過沒；「有評分檔但沒有評分」或「模型一個回答都沒拿到」
（`analyze_local.cells` 的 `infra_void`）的那一跑有 `result.json`，不移開就不會補跑。移開的 job 目錄整個搬到
`<jobs>/_void_first/`（不刪，留作紀錄），`moved.json` 記下搬了哪些。之後用**同一組參數**再叫一次 `run_batch.py`，
它只會補跑這些格子（照種子順序）。補跑也壞 ⇒ 那一題那一次的各組都從分析拿掉（分析時處理，這裡不動）。

    python3 ops/eval/local/rerun_void.py --jobs <jobs 根目錄> --ledger <代理 ledger 目錄> \
        --dataset <釘死的題目目錄> --prefix <標籤前綴> [--dry-run]

只讀評分來判斷「有沒有評分」（`reward is None`），不讀評分的值。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from analyze_local import cells  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jobs", required=True, type=pathlib.Path)
    ap.add_argument("--ledger", required=True, type=pathlib.Path)
    ap.add_argument("--dataset", required=True, type=pathlib.Path)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    void = [r for r in cells(a.jobs, a.ledger, a.dataset, a.prefix) if r["infra_void"]]
    dest = a.jobs / "_void_first"
    moved = []
    for r in void:
        src = a.jobs / f"g12-off-{r['arm']}-s{r['sample']}" / r["job"]
        rec = {"task": r["task"], "arm": r["arm"], "sample": r["sample"], "job": r["job"],
               "exception": r["exception"], "requests": r["requests"],
               "provider_errors": r["provider_errors"], "reward_missing": r["reward"] is None}
        if not a.dry_run and src.is_dir():
            dest.mkdir(exist_ok=True)
            shutil.move(str(src), str(dest / f"g12-off-{r['arm']}-s{r['sample']}__{r['job']}"))
            rec["moved"] = True
        moved.append(rec)
    if not a.dry_run:
        prev = []
        if (dest / "moved.json").is_file():
            prev = json.loads((dest / "moved.json").read_text())
        dest.mkdir(exist_ok=True)
        (dest / "moved.json").write_text(json.dumps(prev + moved, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({"infra_void": len(moved), "cells": moved}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
