"""本機算力批次的驅動（2026-09-26）：一張 (題目, 組別, 第幾次) 清單，交錯排好、平行跑、可續跑。

    python3 ops/eval/local/run_batch.py --harbor <harbor 目錄> --jobs <jobs 根目錄> --dataset <釘死的題目目錄> \
        --arms A=- C1=<wheel> C2=<wheel> --samples 1 2 --parallel 6 --prefix pilot [--tasks 9 7 …] [--seed 20260926]

- **同一題、同一次的所有組別用同一台機器**（`1003`／`w401` 依題目在種子順序裡的位置輪流），兩台設定不一定完全一樣，
  這樣台與台的差不會混進組別的差。
- 順序：`random.Random(seed).shuffle(題目)`；每一題的各組別排在一起、組別內的順序也用同一個種子打亂——中途停下來，
  已經跑完的是一個隨機子集，而且每一題的各組別大致同時跑。
- 續跑：那一格已經有 `result.json` 就跳過。每一跑結束寫一行到 `<jobs>/progress.jsonl`（不含評分）。
- **不看結果決定要不要繼續**：這支不讀 reward。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).resolve().parent
RUN = HERE / "run_local.sh"
TASKS = HERE.parent / "pilot" / "tasks.json"
UPSTREAMS = ("w401", "1003")


def plan(tasks: list[str], arms: list[str], samples: list[int], seed: int) -> list[tuple[str, str, int, str]]:
    rng = random.Random(seed)
    order = list(tasks)
    rng.shuffle(order)
    cells = []
    for s in samples:
        for i, t in enumerate(order):
            up = UPSTREAMS[(i + s) % len(UPSTREAMS)]
            group = list(arms)
            rng.shuffle(group)
            cells += [(t, arm, s, up) for arm in group]
    return cells


def done(jobs: pathlib.Path, arm: str, task: str, s: int) -> bool:
    return any((jobs / f"g12-off-{arm}-s{s}").glob(f"*/dabstep-{task}__*/result.json"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--harbor", required=True)
    ap.add_argument("--jobs", required=True, type=pathlib.Path)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--arms", nargs="+", required=True, help="名字=wheel（A 用 -）")
    ap.add_argument("--samples", nargs="+", type=int, default=[1])
    ap.add_argument("--tasks", nargs="*")
    ap.add_argument("--parallel", type=int, default=6)
    ap.add_argument("--prefix", default="local")
    ap.add_argument("--seed", type=int, default=20260926)
    a = ap.parse_args()
    wheels = dict(x.split("=", 1) for x in a.arms)
    tasks = a.tasks or list(json.loads(TASKS.read_text())["formal_79"])
    cells = [c for c in plan(tasks, list(wheels), a.samples, a.seed) if not done(a.jobs, c[1], c[0], c[2])]
    a.jobs.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    print(f"{len(cells)} runs to go, parallel {a.parallel}", flush=True)

    def one(c: tuple[str, str, int, str]) -> None:
        task, arm, s, up = c
        log = a.jobs / "logs" / f"{task}-{arm}-s{s}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        with log.open("w") as f:
            rc = subprocess.run(["bash", str(RUN), a.harbor, str(a.jobs), wheels[arm], task, arm, up, str(s)],
                                stdout=f, stderr=subprocess.STDOUT,
                                env={**__import__("os").environ, "DABSTEP_PINNED": a.dataset,
                                     "TAG_PREFIX": a.prefix}).returncode
        rec = {"task": task, "arm": arm, "sample": s, "upstream": up, "rc": rc,
               "seconds": round(time.time() - t0, 1), "has_result": done(a.jobs, arm, task, s),
               "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        with lock:
            with (a.jobs / "progress.jsonl").open("a") as f:
                f.write(json.dumps(rec) + "\n")
            print(json.dumps(rec), flush=True)

    with ThreadPoolExecutor(a.parallel) as ex:
        list(ex.map(one, cells))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
