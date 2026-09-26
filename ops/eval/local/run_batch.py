"""本機算力批次的驅動（2026-09-26）：一張 (題目, 組別, 第幾次) 清單，交錯排好、平行跑、可續跑。

    python3 ops/eval/local/run_batch.py --harbor <harbor 目錄> --jobs <jobs 根目錄> --dataset <釘死的題目目錄> \
        --arms A=- C1=<wheel> C2=<wheel> --samples 1 2 --parallel 6 --prefix pilot [--tasks 9 7 …] [--seed 20260926]

- **同一題、同一次的所有組別用同一台機器**（`--upstreams` 裡的機器依題目在種子順序裡的位置輪流），兩台設定不一定完全一樣，
  這樣台與台的差不會混進組別的差。⚠ 2026-09-26 試跑：1003 處理長提示很慢（請求延遲中位數 26 秒、最慢約 350 秒；
  w401c-15 是 6 秒），有兩通 300 秒沒有任何回應就被 agent 端斷掉——所以之後的批次只用 `--upstreams w401`。
- 順序：`random.Random(seed).shuffle(題目)`；每一題的各組別排在一起、組別內的順序也用同一個種子打亂——中途停下來，
  已經跑完的是一個隨機子集，而且每一題的各組別大致同時跑。
- **每台機器自己的同時跑數**：`--upstreams w401:3 1003:1`（名字:同時幾跑；2026-09-26 實測：同一台同時跑太多段對話，
  LM Studio 的提示快取會被擠掉、每一通都要重讀整段提示）。題目依種子順序按同時跑數的比例分給各台（加權輪流）。
- **時間上限**：`--deadline <UTC ISO 時間>`——過了就不再開新的一跑，等在跑的跑完（只看時間，不看結果）。
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


def _weighted(upstreams: dict[str, int]) -> list[str]:
    """加權輪流的一個週期：{w401: 3, 1003: 1} → [w401, 1003, w401, w401]（盡量攤開）。"""
    total = sum(upstreams.values())
    credit = dict.fromkeys(upstreams, 0.0)
    out = []
    for _ in range(total):
        for u in credit:
            credit[u] += upstreams[u] / total
        u = max(credit, key=lambda k: credit[k])
        credit[u] -= 1
        out.append(u)
    return out


def plan(tasks: list[str], arms: list[str], samples: list[int], seed: int,
         upstreams: dict[str, int] | tuple[str, ...] = UPSTREAMS) -> list[tuple[str, str, int, str]]:
    ups = upstreams if isinstance(upstreams, dict) else dict.fromkeys(upstreams, 1)
    cycle = _weighted(ups)
    rng = random.Random(seed)
    order = list(tasks)
    rng.shuffle(order)
    cells = []
    for s in samples:
        for i, t in enumerate(order):
            up = cycle[(i + s) % len(cycle)]
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
    ap.add_argument("--upstreams", nargs="+", default=list(UPSTREAMS),
                    help="名字 或 名字:同時跑數（例：w401:3 1003:1）")
    ap.add_argument("--deadline", help="UTC ISO 時間；過了就不再開新的一跑")
    a = ap.parse_args()
    wheels = dict(x.split("=", 1) for x in a.arms)
    tasks = a.tasks or list(json.loads(TASKS.read_text())["formal_79"])
    ups = {u.split(":")[0]: int(u.split(":")[1]) if ":" in u else a.parallel for u in a.upstreams}
    cells = [c for c in plan(tasks, list(wheels), a.samples, a.seed, ups)
             if not done(a.jobs, c[1], c[0], c[2])]
    a.jobs.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    print(f"{len(cells)} runs to go, per machine {ups}", flush=True)
    deadline = time.mktime(time.strptime(a.deadline, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone \
        if a.deadline else None

    def one(c: tuple[str, str, int, str]) -> None:
        task, arm, s, up = c
        if deadline is not None and time.time() > deadline:
            return
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

    # 每台機器一個執行緒池；各池照種子順序拿自己的格子
    pools = {u: ThreadPoolExecutor(n) for u, n in ups.items()}
    futs = [pools[c[3]].submit(one, c) for c in cells]
    for f in futs:
        f.result()
    for p in pools.values():
        p.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
