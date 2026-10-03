"""程式題篩選組的驅動（2026-09-26）：`ops/eval/local/run_batch.py` 的同一套排法，跑 `run_code.sh`。

    python3 ops/eval/codesuite/run_code_batch.py --harbor <harbor 目錄> --jobs <jobs 根目錄> --suite <lcb_visible/livecodebench> \
        --tasks abc310_b 3553 … --arms A=- [C=<wheel>] --samples 1 --upstreams 1003:1 --prefix codesmoke [--deadline …] \
        [--wait-free 1003:<留出批次的 progress.jsonl>:100]

- 排法、續跑、時限、不讀 reward：全部照 `run_batch.py`（`plan()` 直接從那裡匯入，不另寫一份）。
  **不改 `run_batch.py`**——留出批次（預註冊）還在用它，它的補跑那一步會重新載入那個檔。
- `--wait-free <機器>:<progress.jsonl>:<n>`：等那個檔裡 `upstream==<機器>` 的行數到 n 才開始——留出批次的驅動是每台機器一條固定的佇列，
  1003 做完它那一份之後就閒著；這一支只在那之後用它，不和留出批次搶同一台機器。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "local"))
from run_batch import plan  # noqa: E402

RUN = HERE / "run_code.sh"


def done(jobs: pathlib.Path, arm: str, task: str, s: int) -> bool:
    return any((jobs / f"g12-off-{arm}-s{s}").glob(f"*/{task}__*/result.json"))


def _count(progress: pathlib.Path, up: str) -> int:
    try:
        return sum(1 for ln in progress.read_text().splitlines() if ln.strip() and json.loads(ln).get("upstream") == up)
    except (OSError, ValueError):
        return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--harbor", required=True)
    ap.add_argument("--jobs", required=True, type=pathlib.Path)
    ap.add_argument("--suite", required=True, help="lcb_visible/livecodebench 目錄")
    ap.add_argument("--arms", nargs="+", required=True, help="名字=wheel（A 用 -）")
    ap.add_argument("--samples", nargs="+", type=int, default=[1])
    ap.add_argument("--tasks", nargs="+", required=True)
    ap.add_argument("--prefix", default="code")
    ap.add_argument("--seed", type=int, default=20260926)
    ap.add_argument("--upstreams", nargs="+", default=["1003:1"])
    ap.add_argument("--deadline", help="UTC ISO 時間；過了就不再開新的一跑")
    ap.add_argument("--wait-free", help="<機器>:<progress.jsonl>:<n>")
    a = ap.parse_args()
    if a.wait_free:
        up, prog, n = a.wait_free.split(":")
        while _count(pathlib.Path(prog), up) < int(n):
            time.sleep(60)
        print(f"[{time.strftime('%FT%TZ', time.gmtime())}] {up} is free ({n} runs in {prog})", flush=True)
    wheels = dict(x.split("=", 1) for x in a.arms)
    ups = {u.split(":")[0]: int(u.split(":")[1]) if ":" in u else 1 for u in a.upstreams}
    cells = [c for c in plan(a.tasks, list(wheels), a.samples, a.seed, ups) if not done(a.jobs, c[1], c[0], c[2])]
    a.jobs.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    print(f"{len(cells)} runs to go, per machine {ups}", flush=True)
    deadline = time.mktime(time.strptime(a.deadline, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone if a.deadline else None

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
                                env={**os.environ, "CODESUITE": a.suite, "TAG_PREFIX": a.prefix}).returncode
        rec = {"task": task, "arm": arm, "sample": s, "upstream": up, "rc": rc,
               "seconds": round(time.time() - t0, 1), "has_result": done(a.jobs, arm, task, s),
               "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        with lock:
            with (a.jobs / "progress.jsonl").open("a") as f:
                f.write(json.dumps(rec) + "\n")
            print(json.dumps(rec), flush=True)

    pools = {u: ThreadPoolExecutor(n) for u, n in ups.items()}
    futs = [pools[c[3]].submit(one, c) for c in cells]
    for f in futs:
        f.result()
    for p in pools.values():
        p.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
