#!/usr/bin/env python3
"""probe_throughput — 找出 Claude Code worker 的並行數（DECISION 雲端修正 C4 步驟 4）。

每個並行度 c 跑 2c 次真實嘗試（輪流用 8 個不同題的工作區副本、經 `redo-claude-agent` 沙箱、不評分），量：
完成數／分鐘（=吞吐）、API 錯誤（result.is_error）、牆鐘中位數、費用。總吞吐「還在上升且沒有限流錯誤」的最大並行度＝jobs。
輸出 JSONL（每個並行度一行）到 --out。
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import pathlib
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

TASKS = ["ex_circular_buffer", "ex_yacht", "ex_say", "ex_luhn", "ex_sublist", "ex_ocr_numbers", "ex_dnd_character", "ex_series"]


def one(bank: pathlib.Path, task: str, root: pathlib.Path) -> dict:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="redo-probe-", dir=root))
    ws, logs = tmp / "w", tmp / "logs"
    shutil.copytree(bank / task / "workspace", ws)
    prompt = (bank / task / "instruction.txt").read_text().strip()
    t0 = time.time()
    p = subprocess.run(["redo-claude-agent", str(logs), "haiku", prompt], cwd=ws, capture_output=True, text=True,
                       env=dict(os.environ, REDO_WS_ROOT=str(root)), timeout=900)
    res = None
    for ln in p.stdout.splitlines():
        if ln.startswith("{"):
            try:
                o = json.loads(ln)
            except ValueError:
                continue
            if o.get("type") == "result":
                res = o
    r = {"task": task, "wall_s": round(time.time() - t0, 1), "rc": p.returncode}
    if res:
        r.update(is_error=res.get("is_error"), cost=res.get("total_cost_usd"), reason=res.get("terminal_reason"),
                 err=(str(res.get("result"))[:120] if res.get("is_error") else None))
    else:
        r.update(is_error=True, cost=None, reason="no_result", err=p.stdout[-200:] + p.stderr[-200:])
    shutil.rmtree(tmp, ignore_errors=True)
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", default="/opt/ctlwork/bm_tasks/ctl37")
    ap.add_argument("--levels", default="4,8,16,32")
    ap.add_argument("--root", default="/var/ctlws")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    root = pathlib.Path(a.root)
    for c in [int(x) for x in a.levels.split(",")]:
        n = 2 * c
        t0 = time.time()
        with cf.ThreadPoolExecutor(c) as ex:
            rs = list(ex.map(lambda i: one(pathlib.Path(a.bank), TASKS[i % len(TASKS)], root), range(n)))
        wall = time.time() - t0
        rec = {"concurrency": c, "runs": n, "wall_s": round(wall, 1), "runs_per_min": round(60 * n / wall, 2),
               "errors": sum(1 for r in rs if r["is_error"]), "median_run_wall_s": round(statistics.median(r["wall_s"] for r in rs), 1),
               "cost_usd": round(sum(r["cost"] or 0 for r in rs), 4), "error_samples": [r["err"] for r in rs if r["is_error"]][:3]}
        print(json.dumps(rec, ensure_ascii=False), flush=True)
        with open(a.out, "a") as f:
            f.write(json.dumps({**rec, "per_run": rs}, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
