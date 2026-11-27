#!/usr/bin/env python3
"""probe_throughput — 找出 Devin worker 的並行數（DECISION 雲端修正 C5 步驟 4）。

每個並行度 c 跑 2c 次真實嘗試（輪流用 8 個不同題的工作區副本、經 `redo-devin-agent` 沙箱、不評分），量：
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

MODEL = "swe-2-flash-medium"
TASKS = ["ex_circular_buffer", "ex_yacht", "ex_say", "ex_luhn", "ex_sublist", "ex_ocr_numbers", "ex_dnd_character", "ex_series"]


def one(bank: pathlib.Path, task: str, root: pathlib.Path) -> dict:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="redo-probe-", dir=root))
    ws, logs = tmp / "w", tmp / "logs"
    shutil.copytree(bank / task / "workspace", ws)
    prompt = (bank / task / "instruction.txt").read_text().strip()
    t0 = time.time()
    p = subprocess.run(["redo-devin-agent", str(logs), MODEL, prompt], cwd=ws, capture_output=True, text=True,
                       env=dict(os.environ, REDO_WS_ROOT=str(root)), timeout=900)
    r = {"task": task, "wall_s": round(time.time() - t0, 1), "rc": p.returncode}
    exp = logs / "devin_export.json"
    try:
        d = json.loads(exp.read_text())
        fm = d.get("final_metrics") or {}
        import filecmp
        ch = not all(filecmp.cmp(f, bank / task / "workspace" / f.relative_to(ws), shallow=False)
                     for f in ws.rglob("*") if f.is_file() and (bank / task / "workspace" / f.relative_to(ws)).exists())
        ch = ch or any(f.is_file() and not (bank / task / "workspace" / f.relative_to(ws)).exists() for f in ws.rglob("*"))
        r["changed"] = ch
        r["stdout_tail"] = (p.stdout + p.stderr)[-300:]
        bad = (fm.get("total_steps") is None) or ("Error:" in p.stdout + p.stderr)
        r.update(is_error=bool(bad), cost=None, reason=("export_incomplete_or_error" if bad else "export_ok"), err=((p.stdout + p.stderr)[-200:] if bad else None), steps=fm.get("total_steps"),
                 tok_in=fm.get("total_prompt_tokens"), tok_out=fm.get("total_completion_tokens"))
    except (OSError, ValueError):
        r.update(is_error=True, cost=None, reason="no_export", err=((p.stdout + p.stderr)[-200:]))
    shutil.rmtree(tmp, ignore_errors=True)
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", default="/opt/ctlwork/bm_tasks/ctl37")
    ap.add_argument("--levels", default="4,8,16")
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
               "errors": sum(1 for r in rs if r["is_error"]), "unchanged_ws": sum(1 for r in rs if r.get("changed") is False), "median_run_wall_s": round(statistics.median(r["wall_s"] for r in rs), 1),
               "error_samples": [r["err"] for r in rs if r["is_error"]][:3]}
        print(json.dumps(rec, ensure_ascii=False), flush=True)
        with open(a.out, "a") as f:
            f.write(json.dumps({**rec, "per_run": rs}, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
