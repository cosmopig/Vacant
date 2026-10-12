"""本機算力批次的驅動，共用一條佇列（2026-09-27）：兩台機器都從同一條佇列拿「一題一次」，那一題的各組都在拿到它的那台機器跑。

`run_batch.py` 把題目事先分給各台（加權輪流）；S36-nocap 收尾時 w401 的份先跑完、閒了一個小時，剩下的全擠在 1003（RUNLOG §16）。
這一支改成：
- **一個單位＝(題目, 第幾次)**，照 `random.Random(seed)` 打亂的順序排成一條佇列（第 1 次全部排在第 2 次前面）。
- 每台機器 `名字:位置數` 個工作執行緒。一個位置空出來：**先拿這台機器已經接下、還沒開始的格子**（同一題的另一組），
  沒有才從共用佇列拿下一個單位——那個單位的各組都排進這台機器（組別順序也用同一個種子打亂），自己先跑第一組。
  ⇒ 同一題同一次的各組同一台機器、幾乎同時開始；快的機器自然多做，沒有誰閒著。
- **時間上限**（`--deadline`，UTC）：過了就不再從共用佇列拿**沒開始過的**單位；**已經接下的單位照樣跑完**（配對不會被切成一半）。
  「開始過」＝`progress.jsonl` 裡有那一題那一次的任何一行，或這一次執行已經接下——所以過了時間上限之後用同一組參數再叫一次
  （例如 `rerun_void.py` 移開 infra_void 之後補跑），只會補那些開始過的單位。只看時間，不看結果。
- 續跑：那一格已經有 `result.json` 就跳過。同一單位已經有一組跑完、另一組沒有 ⇒ 剩下的那組排回**跑完那組用的機器**
  （從那一跑的 `config.json` 讀代理網址裡的 `/up/<名字>/`），配對仍在同一台。
- 每一跑結束寫一行到 `<jobs>/progress.jsonl`（不含評分）。**這支不讀 reward**。

    python3 ops/eval/local/run_pairs.py --harbor <harbor 目錄> --jobs <jobs 根目錄> --dataset <釘死的題目目錄> \
        --arms A=- C361=<wheel> --samples 1 --upstreams w401:4 1003:4 --seed <種子> --prefix <標籤前綴> \
        (--tasks 9 7 … | --manifest <UNSEEN_MANIFEST.json>) [--deadline 2026-09-28T02:00:00Z]

一跑的內容和 `run_batch.py` 相同（`run_local.sh`；回合上限由環境變數 `MAX_TURNS` 決定）。
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
from typing import Callable

HERE = pathlib.Path(__file__).resolve().parent
RUN = HERE / "run_local.sh"

Cell = tuple[str, str, int, str]                      # (題目, 組別, 第幾次, 機器)


def units(tasks: list[str], arms: list[str], samples: list[int], seed: int) -> list[tuple[str, int, list[str]]]:
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


def done(jobs: pathlib.Path, arm: str, task: str, s: int) -> bool:
    return any((jobs / f"g12-off-{arm}-s{s}").glob(f"*/dabstep-{task}__*/result.json"))


def machine_of(jobs: pathlib.Path, arm: str, task: str, s: int) -> str | None:
    """已經跑完的那一格用的是哪台機器（代理網址裡的 `/up/<名字>/`）；讀不到回 None。"""
    for cfg in (jobs / f"g12-off-{arm}-s{s}").glob(f"*/dabstep-{task}__*/config.json"):
        m = re.search(r"/up/([A-Za-z0-9_.-]+)/", cfg.read_text(errors="replace"))
        if m:
            return m.group(1)
    return None


class Queue:
    """共用佇列＋每台機器已接下的格子。所有狀態都在一把鎖底下。"""

    def __init__(self, us: list[tuple[str, int, list[str]]], machines: list[str],
                 is_done: Callable[[str, str, int], bool], where: Callable[[str, str, int], str | None],
                 deadline: float | None, clock: Callable[[], float] = time.time,
                 started: set[tuple[str, int]] | None = None) -> None:
        self.lock = threading.Lock()
        self.started = set(started or ())
        self.shared = collections.deque(us)
        self.local: dict[str, collections.deque[Cell]] = {m: collections.deque() for m in machines}
        self.is_done, self.where, self.deadline, self.clock = is_done, where, deadline, clock

    def take(self, machine: str) -> Cell | None:
        with self.lock:
            if self.local[machine]:
                return self.local[machine].popleft()
            while self.shared:
                task, s, group = self.shared.popleft()
                if self.deadline is not None and self.clock() > self.deadline and (task, s) not in self.started:
                    continue                            # 過了時間上限：沒開始過的單位不拿
                self.started.add((task, s))
                todo = [a for a in group if not self.is_done(a, task, s)]
                if not todo:
                    continue
                ran = [a for a in group if a not in todo]
                home = next((m for m in (self.where(a, task, s) for a in ran) if m), None) if ran else None
                if home is not None and home in self.local and home != machine:
                    self.local[home].extend((task, a, s, home) for a in todo)
                    continue                            # 交給原來那台；這個位置再拿下一個
                self.local[machine].extend((task, a, s, machine) for a in todo[1:])
                return (task, todo[0], s, machine)
            return None

    def pending(self, machine: str) -> bool:
        with self.lock:
            return bool(self.local[machine])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--harbor", required=True)
    ap.add_argument("--jobs", required=True, type=pathlib.Path)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--arms", nargs="+", required=True, help="名字=wheel（A 用 -）")
    ap.add_argument("--samples", nargs="+", type=int, default=[1])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--tasks", nargs="+")
    g.add_argument("--manifest", type=pathlib.Path, help="{'tasks': [{'task': …}, …]}")
    ap.add_argument("--upstreams", nargs="+", required=True, help="名字:位置數（例：w401:4 1003:4）")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--deadline", help="UTC ISO 時間；過了就不再拿新的單位")
    a = ap.parse_args(argv)
    wheels = dict(x.split("=", 1) for x in a.arms)
    tasks = a.tasks or [x["task"] for x in json.loads(a.manifest.read_text())["tasks"]]
    ups = {u.split(":")[0]: int(u.split(":")[1]) for u in a.upstreams}
    deadline = time.mktime(time.strptime(a.deadline, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone if a.deadline else None
    a.jobs.mkdir(parents=True, exist_ok=True)
    us = units(tasks, list(wheels), a.samples, a.seed)
    started = set()
    if (a.jobs / "progress.jsonl").is_file():
        for ln in (a.jobs / "progress.jsonl").read_text().splitlines():
            try:
                r = json.loads(ln)
                started.add((str(r["task"]), int(r["sample"])))
            except (ValueError, KeyError):
                continue
    q = Queue(us, list(ups), lambda arm, t, s: done(a.jobs, arm, t, s),
              lambda arm, t, s: machine_of(a.jobs, arm, t, s), deadline, started=started)
    left = sum(1 for t, s, grp in us for arm in grp if not done(a.jobs, arm, t, s))
    print(json.dumps({"units": len(us), "runs_to_go": left, "machines": ups, "deadline": a.deadline}), flush=True)
    plock = threading.Lock()

    def run(c: Cell) -> None:
        task, arm, s, up = c
        log = a.jobs / "logs" / f"{task}-{arm}-s{s}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        with log.open("w") as f:
            rc = subprocess.run(["bash", str(RUN), a.harbor, str(a.jobs), wheels[arm], task, arm, up, str(s)],
                                stdout=f, stderr=subprocess.STDOUT,
                                env={**os.environ, "DABSTEP_PINNED": a.dataset, "TAG_PREFIX": a.prefix}).returncode
        rec = {"task": task, "arm": arm, "sample": s, "upstream": up, "rc": rc,
               "seconds": round(time.time() - t0, 1), "has_result": done(a.jobs, arm, task, s),
               "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        with plock:
            with (a.jobs / "progress.jsonl").open("a") as f:
                f.write(json.dumps(rec) + "\n")
            print(json.dumps(rec), flush=True)

    def worker(machine: str) -> None:
        while True:
            c = q.take(machine)
            if c is None:
                if q.pending(machine):                 # 別的位置剛排進來的（續跑的配對）
                    continue
                return
            run(c)

    threads = [threading.Thread(target=worker, args=(m,), daemon=False) for m, n in ups.items() for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
