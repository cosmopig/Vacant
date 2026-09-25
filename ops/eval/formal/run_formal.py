"""DABstep 正式批次的驅動（`decisions/prereg/PREREG_20260925_ZERO_CONFIG_DABSTEP.md` 第五、六節）。

    python3 ops/eval/formal/run_formal.py --harbor <harbor 目錄> --jobs <jobs 根目錄> --wheel <vacant wheel> \
        --dataset <dabstep_formal.py 的輸出> --ledger <記帳代理的 ledger 目錄> --budget 4.80

- 條件依序：gemma-4-26b 開思考，然後 qwen3.8-27b 開思考（預註冊寫死）。
- 題目順序：`random.Random(20260925).shuffle(formal_79)`；同一題的 A、C **同時**開跑；同時最多 `--pairs` 對（預設 2 對＝4 個容器）。
- 停止：開新的一對之前看帳本的累計花費；剩下的錢少於 `--reserve`（預設 0.30 美元）就不再開新的，等在跑的跑完。
- 續跑：某一對兩邊都已經有 `result.json` 就跳過（中斷之後重下同一個指令即可）。
- 每一對完成就寫一行到 `<jobs>/progress.jsonl`。
- **不看結果決定要不要繼續**：這支不讀 reward，只讀花費。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import random
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).resolve().parent
RUN_ONE = HERE.parent / "pilot" / "run_one.sh"
TASKS = HERE.parent / "pilot" / "tasks.json"
CONDITIONS = [("g4", "on"), ("q38", "on")]
SEED = 20260925


def order() -> list[str]:
    tasks = list(json.loads(TASKS.read_text())["formal_79"])
    random.Random(SEED).shuffle(tasks)
    return tasks


def spent(ledger: pathlib.Path) -> float:
    try:
        return float(json.loads((ledger / "summary.json").read_text())["spent_usd"])
    except (OSError, ValueError, KeyError):
        return float("inf")          # 讀不到帳就當成沒錢：寧可停，也不超支


def done(jobs: pathlib.Path, m: str, think: str, arm: str, task: str) -> bool:
    return any((jobs / f"{m}-{think}-{arm}").glob(f"*/dabstep-{task}__*/result.json"))


def run_pair(a, m: str, think: str, task: str, lock: threading.Lock) -> dict:
    env = {"DABSTEP_PINNED": str(a.dataset), "TAG_PREFIX": "formal"}
    procs = []
    t0 = time.time()
    for arm in ("A", "C"):
        if done(a.jobs, m, think, arm, task):
            continue
        log = a.jobs / "logs" / f"{task}-{m}-{think}-{arm}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        f = log.open("w")
        procs.append((arm, f, subprocess.Popen(
            ["bash", str(RUN_ONE), str(a.harbor), str(a.jobs), str(a.wheel), task, m, think, arm],
            stdout=f, stderr=subprocess.STDOUT, env={**os.environ, **env})))
    rcs = {}
    for arm, f, p in procs:
        rcs[arm] = p.wait()
        f.close()
    rec = {"task": task, "model": m, "think": think, "rc": rcs, "wall_s": round(time.time() - t0, 1),
           "spent_after": round(spent(a.ledger), 5), "ts": time.time()}
    with lock:
        with (a.jobs / "progress.jsonl").open("a") as fp:
            fp.write(json.dumps(rec) + "\n")
    print(json.dumps(rec), flush=True)
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--harbor", required=True, type=pathlib.Path)
    ap.add_argument("--jobs", required=True, type=pathlib.Path)
    ap.add_argument("--wheel", required=True, type=pathlib.Path)
    ap.add_argument("--dataset", required=True, type=pathlib.Path)
    ap.add_argument("--ledger", required=True, type=pathlib.Path)
    ap.add_argument("--budget", type=float, default=4.80)
    ap.add_argument("--reserve", type=float, default=0.30)
    ap.add_argument("--pairs", type=int, default=2)
    a = ap.parse_args()
    a.jobs.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    stop = False
    for m, think in CONDITIONS:
        if stop:
            break
        todo = [t for t in order()
                if not (done(a.jobs, m, think, "A", t) and done(a.jobs, m, think, "C", t))]
        print(json.dumps({"condition": f"{m}-{think}", "todo": len(todo)}), flush=True)
        with ThreadPoolExecutor(max_workers=a.pairs) as ex:
            futs = []
            for t in todo:
                while len([f for f in futs if not f.done()]) >= a.pairs:
                    time.sleep(5)
                if a.budget - spent(a.ledger) < a.reserve:
                    print(json.dumps({"stop": "budget", "spent": spent(a.ledger)}), flush=True)
                    stop = True
                    break
                futs.append(ex.submit(run_pair, a, m, think, t, lock))
                time.sleep(2)
            for f in futs:
                f.result()
    print(json.dumps({"finished": True, "spent": spent(a.ledger)}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
