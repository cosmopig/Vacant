#!/usr/bin/env python3
"""Colab 批次驅動（root）：一條共用佇列、W 個位置，每個單位＝(題目, 第幾次)，那一題的各組**同時**開跑。

    python3 driver.py --plan /srv/eval/plan.json --slots 24 --prefix c1 [--deadline 2026-09-28T12:00:00Z] [--stop-file /srv/eval/STOP]

plan.json：{"seed": …, "arms": ["A", "C361"], "samples": [1], "tasks": [{"bank": …, "id": …, "dir": <staged 題目目錄>}, …]}

- 排法照 redesign 分支 ops/eval/local/run_pairs.py：`random.Random(seed)` 打亂題目順序（第 1 次全部排在第 2 次前面），
  每個單位的組別順序也用同一個種子打亂；一個單位的各組一起佔位置、幾乎同時開始（同一時段的負載對各組一樣）。
- **時間上限**：過了就不再拿**沒開始過的**單位；已經開始的單位照樣跑完（配對不會被切成一半）。只看時間，不看結果。
- **停止檔**：`--stop-file` 出現就同上（不開新單位，跑完手上的）。可行性規則觸發時用它。
- 續跑：那一格已經有 DONE 就跳過。
- 每一格結束寫一行 `/srv/eval/progress.jsonl`：組、題、rc、牆鐘、是不是撞時限、C 組有沒有裝上——**不含任何分數**
  （這支不讀 score.json；批次跑完之前不看分數）。
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import pathlib
import random
import re
import subprocess
import threading
import time

EVAL = pathlib.Path("/srv/eval")
CELL = "/opt/eval/bin/cell.sh"


def safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)


def cell_name(prefix: str, arm: str, task: dict, s: int) -> str:
    return safe(f"{prefix}-{arm}-{task['bank']}-{task['id']}-s{s}")


def units(tasks: list[dict], arms: list[str], samples: list[int], seed: int) -> list[tuple[dict, int, list[str]]]:
    rng = random.Random(seed)
    order = list(tasks)
    rng.shuffle(order)
    out = []
    for s in samples:
        for t in order:
            group = list(arms)
            rng.shuffle(group)
            out.append((t, s, group))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True, type=pathlib.Path)
    ap.add_argument("--slots", type=int, default=24)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--deadline")
    ap.add_argument("--stop-file", type=pathlib.Path, default=EVAL / "STOP")
    a = ap.parse_args()
    plan = json.loads(a.plan.read_text())
    arms = plan["arms"]
    deadline = (time.mktime(time.strptime(a.deadline, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone) if a.deadline else None
    q = collections.deque(units(plan["tasks"], arms, plan.get("samples", [1]), plan["seed"]))
    prog = EVAL / "progress.jsonl"
    lock = threading.Lock()
    free = threading.Semaphore(a.slots)
    started_units: set[tuple[str, int]] = set()
    for ln in (prog.read_text().splitlines() if prog.exists() else []):
        try:
            r = json.loads(ln)
            started_units.add((r["unit"], r["sample"]))
        except (ValueError, KeyError):
            continue

    def run_cell(task: dict, arm: str, s: int) -> None:
        name = cell_name(a.prefix, arm, task, s)
        try:
            if (EVAL / "cells" / name / "DONE").exists():
                return
            t0 = time.time()
            with (EVAL / "cell_logs").joinpath(f"{name}.log").open("w") as f:
                rc = subprocess.run(["bash", CELL, name, task["dir"], arm, name], stdout=f, stderr=subprocess.STDOUT,
                                    env={**os.environ}).returncode
            meta = {}
            try:
                meta = json.loads((EVAL / "cells" / name / "meta.json").read_text())
            except (OSError, ValueError):
                pass
            chk = {}
            try:
                chk = json.loads((EVAL / "cells" / name / "vacant_check.json").read_text().strip().splitlines()[-1])
            except (OSError, ValueError, IndexError):
                pass
            rec = {"cell": name, "unit": f"{task['bank']}/{task['id']}", "bank": task["bank"], "task": task["id"],
                   "arm": arm, "sample": s, "cell_sh_rc": rc, "agent_rc": meta.get("rc"), "timeout": meta.get("timeout"),
                   "wall_s": meta.get("wall_s"), "install_rc": meta.get("install_rc"),
                   "c_arm_ok": chk.get("c_arm_ok") if arm != "A" else None,
                   "stop_reached": chk.get("stop_reached") if arm != "A" else None,
                   "leftover_procs": meta.get("leftover_procs"), "seconds": round(time.time() - t0, 1),
                   "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            with lock:
                with prog.open("a") as f:
                    f.write(json.dumps(rec) + "\n")
                print(json.dumps(rec), flush=True)
        finally:
            free.release()

    (EVAL / "cells").mkdir(exist_ok=True)
    (EVAL / "cell_logs").mkdir(exist_ok=True)
    threads: list[threading.Thread] = []
    print(f"{len(q)} units × {len(arms)} arms, slots={a.slots}", flush=True)
    while q:
        task, s, group = q[0]
        key = (f"{task['bank']}/{task['id']}", s)
        stop = a.stop_file.exists() or (deadline is not None and time.time() > deadline)
        if stop and key not in started_units:
            q.popleft()
            continue
        todo = [arm for arm in group if not (EVAL / "cells" / cell_name(a.prefix, arm, task, s) / "DONE").exists()]
        q.popleft()
        if not todo:
            continue
        for _ in todo:                      # 一個單位的各組一起拿位置（全部拿到才一起開跑）
            free.acquire()
        started_units.add(key)
        for arm in todo:
            th = threading.Thread(target=run_cell, args=(task, arm, s), daemon=False)
            th.start()
            threads.append(th)
    for th in threads:
        th.join()
    print("DRIVER_DONE", flush=True)
    (EVAL / "DRIVER_DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
