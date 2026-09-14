#!/usr/bin/env python3
"""R530 的佇列排程器：塊**釘在指定的那顆後端上**，兩台輪流，每台 ≤4 串。

Fable 2026-09-13 的裁決逐條：
「沿用 `schedule_queue.py` 的佇列 JSON：兩台後端、同一題三臂同一台、
 題在兩台輪流、每台 ≤4 串。」

## 與 `schedule_harness_reps.py`／`schedule_queue.py` 的關係

**狀態機、作廢規則、槽表、idempotency 全部 import 那兩支的純函式**，
一個字都不改它們（R460R／R529 的塊正在那兩支底下排隊）。
這支只換兩樣東西，兩樣都是 R530 的實驗設計要求：

  1. **塊自帶端點**（`endpoint` 是佇列 JSON 的必填欄位），不是 first-fit。
     理由不是方便：**同一題的三條臂必須打同一顆後端**，否則後端就從
     task 層級的干擾項變成 arm 層級的混淆項（R460 §二-2 的同一條）。
     R530 的一塊 ＝「一組題 × 三條臂 × 一顆 seed」，整塊在同一顆後端上跑完
     ⇒ 那條性質是**結構性**的，不靠紀律。
  2. **題在兩台輪流**由佇列 JSON 自己表達（奇數題一塊給 A、偶數題一塊給 B），
     `load_queue()` 驗它**真的有輪**——一顆 seed 的所有塊全壓在同一顆卡上
     就拒收（`abort_all_blocks_one_host`）。

## 佇列 JSON

```json
{
  "name": "r530_openwork",
  "decision": "DECISION_20260913_R530_….md",
  "launcher": "ops/gain/r530/run_r530.py",
  "arms": "A-SOLO,A-CONF,A-GATE",
  "backend": "bwrap",
  "request_timeout_s": 900,
  "reasoning_effort": "none",
  "model": "gemma-4-12b-it-qat",
  "backends": {"<endpoint url>": {"host": "1003", …}, …},
  "blocks": [
    {"name": "g_r530_ow_s1_odd", "tasks": ["ow_01_csvjson"],
     "seed": "g-r530-s1", "tag": "r530s1odd",
     "endpoint": "http://100.119.113.56:1234/v1/chat/completions"}
  ]
}
```

驗的每一條都對應一種會安靜跑錯的壞法（`schedule_queue.load_queue` 的同一份紀律）：

  · 塊名唯一          ← 兩塊同名 ⇒ 第二塊撞 `abort_dir_exists`，看起來像發射器壞了
  · tag 唯一          ← tag 決定 flock 檔名，撞了會讓兩塊互相擋
  · `(seed, task)` 不得在兩塊裡出現 ← 重複＝同一格被算兩次，長得跟「跑完了」一樣
  · `endpoint` 必須在 `backends` 與槽表裡都認得
  · 一顆 seed 的塊不得全在同一顆卡上（只有一塊時豁免，並在 `--check` 印出來）
  · 認不得的鍵一律拒收 ← 打錯字的鍵被忽略＝「我以為我設了」

用法（vacant-dev）：
    setsid nohup python3 ops/gain/r530/schedule_r530.py \\
      --queue ops/gain/r530/queues/r530_openwork.json \\
      > ~/vacant/logs/schedule_r530.out 2>&1 < /dev/null &
乾跑（只印計畫、不發射、不碰後端、不寫 runs/）：
    python3 ops/gain/r530/schedule_r530.py --queue … --dry-run
只驗佇列：
    python3 ops/gain/r530/schedule_r530.py --queue … --check
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import json
import os
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from ops.gain.schedule_harness_reps import (  # noqa: E402
    ABORT_KINDS, MAX_ATTEMPTS, POLL_S, Slot, _read_json, abort_block,
    abort_preflight, block_state, occupancy, running_block_names)
from ops.gain.schedule_queue import (ENDPOINT_1003, ENDPOINT_1004,  # noqa: E402
                                     PER_HOST_CAP, QUEUE_SLOTS)

REPO = pathlib.Path(__file__).resolve().parents[3]
LAUNCHER = "ops/gain/r530/run_r530.py"

#: R530 的槽。**名字前綴 `r`**，與 `schedule_queue`（`q…`）與
#: `schedule_harness_reps`（`1004#…`）都不同——三支排程器的 log 不能互相冒充
#: （`schedule_queue` 的同一條理由）。`#` 後面仍是 LM Studio parallel 的那一格。
R530_SLOTS: tuple[Slot, ...] = tuple(
    Slot(f"r{s.host}#{s.slot_id.split('#')[1]}", s.endpoint, s.host)
    for s in QUEUE_SLOTS)

KNOWN_ENDPOINTS = frozenset({ENDPOINT_1003, ENDPOINT_1004})

_BLOCK_REQUIRED = {"name": str, "tasks": list, "seed": str, "tag": str,
                   "endpoint": str}
_BLOCK_OPTIONAL = {"note": str}
_QUEUE_REQUIRED = ("name", "decision", "launcher", "arms", "backend",
                   "request_timeout_s", "reasoning_effort", "model",
                   "backends", "blocks")


def _assert_per_host_cap(slots: tuple[Slot, ...] = R530_SLOTS,
                         cap: int = PER_HOST_CAP) -> None:
    """槽表本身不准違反每張卡 4 串的上限——**import 時就檢查**。

    為什麼是機制不是紀律：多開一格在 log 上長得跟正常一模一樣，
    而它會把「這批資料是在什麼併發條件下量的」變成事後查 `calls.jsonl`
    才知道的事（`schedule_queue._assert_per_host_cap` 的同一條）。
    """
    per: dict[str, int] = {}
    for s in slots:
        per[s.host] = per.get(s.host, 0) + 1
    bad = {h: n for h, n in per.items() if n > cap}
    if bad:
        raise SystemExit(f"槽表違反每張卡 {cap} 串的上限：{bad}。停。")


_assert_per_host_cap()


@dataclasses.dataclass(frozen=True)
class R530Block:
    """佇列裡的一塊。`name`／`out` 兩個屬性讓它能餵進既有的純函式。"""

    name: str
    tasks: tuple[str, ...]
    seed: str
    tag: str
    endpoint: str
    note: str = ""

    @property
    def out(self) -> str:
        return f"runs/{self.name}"

    @property
    def task_set(self) -> str:
        return ",".join(self.tasks)


@dataclasses.dataclass(frozen=True)
class R530Queue:
    name: str
    decision: str
    launcher: str
    arms: str
    backend: str
    request_timeout_s: int
    reasoning_effort: str
    model: str
    backends: dict
    blocks: tuple[R530Block, ...]


def load_queue(path: str | pathlib.Path) -> R530Queue:
    """讀＋驗佇列 JSON。**每一條不成立都 `SystemExit`**——量不到不是通過。"""
    p = pathlib.Path(path)
    if not p.is_file():
        raise SystemExit(f"佇列檔不存在：{p}。停。")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        raise SystemExit(f"佇列檔不是合法 JSON：{p}（{e}）。停。") from e
    if not isinstance(raw, dict):
        raise SystemExit(f"佇列檔的最外層要是 object：{p}。停。")
    missing = [k for k in _QUEUE_REQUIRED if k not in raw]
    if missing:
        raise SystemExit(f"佇列檔缺欄位 {missing}：{p}。停。")
    extra = [k for k in raw if k not in _QUEUE_REQUIRED]
    if extra:
        raise SystemExit(f"佇列檔有認不得的欄位 {extra}：{p}。停。")
    if not isinstance(raw["blocks"], list) or not raw["blocks"]:
        raise SystemExit(f"佇列檔的 blocks 是空的：{p}。停。")
    if not isinstance(raw["backends"], dict) or not raw["backends"]:
        raise SystemExit("backends 要是非空 object。停。")
    if set(raw["backends"]) - KNOWN_ENDPOINTS:
        raise SystemExit(
            f"backends 有認不得的端點：{sorted(set(raw['backends']) - KNOWN_ENDPOINTS)}。停。")

    blocks: list[R530Block] = []
    for i, b in enumerate(raw["blocks"]):
        if not isinstance(b, dict):
            raise SystemExit(f"blocks[{i}] 不是 object。停。")
        for key, typ in _BLOCK_REQUIRED.items():
            if key not in b:
                raise SystemExit(f"blocks[{i}] 缺欄位 {key}。停。")
            if not isinstance(b[key], typ) or isinstance(b[key], bool):
                raise SystemExit(f"blocks[{i}] 的 {key} 型別錯（want {typ}）。停。")
        bad = [k for k in b if k not in _BLOCK_REQUIRED and k not in _BLOCK_OPTIONAL]
        if bad:
            raise SystemExit(f"blocks[{i}] 有認不得的欄位 {bad}。停。")
        tasks = [str(t) for t in b["tasks"]]
        if not tasks:
            raise SystemExit(f"blocks[{i}] 的 tasks 是空的。停。")
        if len(set(tasks)) != len(tasks):
            raise SystemExit(f"blocks[{i}] 的 tasks 有重複。停。")
        if b["endpoint"] not in raw["backends"]:
            raise SystemExit(
                f"blocks[{i}] 的 endpoint {b['endpoint']} 不在 backends 裡。停。")
        if b["endpoint"] not in {s.endpoint for s in R530_SLOTS}:
            raise SystemExit(
                f"blocks[{i}] 的 endpoint {b['endpoint']} 不在槽表裡。停。")
        blocks.append(R530Block(
            name=b["name"], tasks=tuple(tasks), seed=b["seed"], tag=b["tag"],
            endpoint=b["endpoint"], note=b.get("note", "")))

    names = [b.name for b in blocks]
    if len(set(names)) != len(names):
        dup = sorted({n for n in names if names.count(n) > 1})
        raise SystemExit(f"佇列裡有重複的塊名 {dup}。停。")
    tags = [b.tag for b in blocks]
    if len(set(tags)) != len(tags):
        dup = sorted({t for t in tags if tags.count(t) > 1})
        raise SystemExit(f"佇列裡有重複的 tag {dup}（tag 決定 flock 檔名）。停。")
    seen: dict[tuple[str, str], str] = {}
    for b in blocks:
        for t in b.tasks:
            key = (b.seed, t)
            if key in seen:
                raise SystemExit(
                    f"{b.name} 與 {seen[key]} 都含 (seed={b.seed}, task={t})"
                    "——同一格被算兩次，而那長得跟「跑完了」一模一樣。停。")
            seen[key] = b.name
    by_seed: dict[str, set[str]] = {}
    for b in blocks:
        host = next(s.host for s in R530_SLOTS if s.endpoint == b.endpoint)
        by_seed.setdefault(b.seed, set()).add(host)
    for seed, hosts in sorted(by_seed.items()):
        n_blocks = sum(1 for b in blocks if b.seed == seed)
        if n_blocks > 1 and len(hosts) < 2:
            raise SystemExit(
                f"abort_all_blocks_one_host：seed {seed} 的 {n_blocks} 塊全在 "
                f"{sorted(hosts)}——「題在兩台輪流」沒有兌現，"
                "後端就會與題號完全共線。停。")
    for key, typ in (("request_timeout_s", int),):
        if not isinstance(raw[key], typ) or raw[key] <= 0:
            raise SystemExit(f"{key} 要是正整數。停。")
    return R530Queue(
        name=raw["name"], decision=raw["decision"], launcher=raw["launcher"],
        arms=raw["arms"], backend=raw["backend"],
        request_timeout_s=raw["request_timeout_s"],
        reasoning_effort=raw["reasoning_effort"], model=raw["model"],
        backends=raw["backends"], blocks=tuple(blocks))


def registration_line(queue: R530Queue, block: R530Block) -> str:
    """這一塊在 DECISION 裡必須逐字出現的那一行。**與發射器同一個格式。**

    兩邊必須一字不差：`run_r530.registration_line()` 是唯一的真相，
    這裡只是把佇列的欄位餵給它。
    """
    from ops.gain.r530.run_r530 import registration_line as rl
    return rl(out=block.out, task_set=block.task_set, arms=queue.arms,
              seed=block.seed, endpoint_url=block.endpoint)


def check_prereg(queue: R530Queue, repo: pathlib.Path = REPO) -> list[str]:
    """每一塊都要在 DECISION 裡註冊過。回**缺的那幾行**（空＝全過）。"""
    dec = repo / queue.decision
    if not dec.is_file():
        return [f"DECISION 不存在：{dec}"]
    text = dec.read_text(encoding="utf-8")
    return [line for line in (registration_line(queue, b) for b in queue.blocks)
            if line not in text]


def aborted_counts(blocks, root: pathlib.Path) -> dict[str, int]:
    """每一塊被作廢過幾次（兩種戳記都數，`schedule_harness_reps` 的同一條）。"""
    out: dict[str, int] = {}
    ab = root / "runs" / "_aborted"
    for b in blocks:
        out[b.name] = sum(
            len([d for d in ab.glob(f"{b.name}_{k}_*") if d.is_dir()])
            for k in ABORT_KINDS)
    return out


def observe(blocks, root: pathlib.Path) -> tuple[dict, dict]:
    """讀現況：回 `(statuses, endpoints)`。唯一碰檔案系統與 `ps` 的地方。"""
    alive = running_block_names(root)
    statuses: dict[str, str] = {}
    endpoints: dict[str, str] = {}
    for b in blocks:
        d = root / b.out
        summary = _read_json(d / "summary.json") if d.exists() else None
        st, _why = block_state(d.exists(), summary, b.name in alive)
        statuses[b.name] = st
        ep = root / f"{b.out}.endpoint"
        if ep.exists():
            endpoints[b.name] = ep.read_text(encoding="utf-8").strip()
        elif summary and summary.get("endpoint"):
            endpoints[b.name] = summary["endpoint"]
    return statuses, endpoints


def plan_launches_pinned(queue_names: list[str], busy: dict[str, str],
                         by_name: dict[str, R530Block],
                         counts: dict[str, int],
                         slots: tuple[Slot, ...]) -> list[tuple[str, Slot]]:
    """把待發的塊擺進**它自己那顆後端**的空槽。first-fit，但只在同一顆卡上找。

    ⚠ 與 `schedule_harness_reps.plan_launches` 的唯一差別就是這件事，
      而它是 R530 的實驗設計要求不是偏好（見模組 docstring 第 1 點）。
      擺不下就等下一輪——**不准挪到另一顆卡**，那會讓那一塊的三條臂
      跑在與同 seed 其他塊不同的條件下。
    """
    # ⚠ `occupancy()` 回的 `busy` 是 **{slot_id: block_name}**（鍵是槽）。
    #   取錯邊（`.values()`）會讓「槽被佔了」變成「塊名被佔了」⇒ 每一輪都把
    #   同一格再發一次。這一條由 `test_running_blocks_occupy_their_slot` 釘住。
    taken = set(busy.keys())
    out: list[tuple[str, Slot]] = []
    for name in queue_names:
        if counts.get(name, 0) >= MAX_ATTEMPTS:
            continue
        block = by_name[name]
        for s in slots:
            if s.endpoint != block.endpoint or s.slot_id in taken:
                continue
            taken.add(s.slot_id)
            out.append((name, s))
            break
    return out


def plan_tick(blocks, statuses: dict[str, str], endpoints: dict[str, str],
              counts: dict[str, int],
              slots: tuple[Slot, ...] = R530_SLOTS) -> dict:
    """一輪的完整計畫。純函式：觀測進、計畫出，**不改任何東西**。

    順序固定：先收（把 VOID／DEAD 的搬走）再發——反過來的話這一輪剛空出來的
    槽要等下一輪才用得到（`schedule_harness_reps.plan_tick` 的同一條）。
    """
    order = [b.name for b in blocks]
    by_name = {b.name: b for b in blocks}
    abort = [(n, statuses.get(n)) for n in order
             if statuses.get(n) in ("VOID", "DEAD")]
    counts = dict(counts)
    for n, _why in abort:
        counts[n] = counts.get(n, 0) + 1
    eff = {n: ("PENDING" if statuses.get(n) in ("VOID", "DEAD")
               else statuses.get(n, "PENDING")) for n in order}
    running = [n for n in order if eff[n] == "RUNNING"]
    busy, unplaceable, blocked = occupancy(running, endpoints, slots,
                                           KNOWN_ENDPOINTS)
    done = [n for n in order if eff[n] == "DONE"]
    given_up = [n for n in order
                if eff[n] == "PENDING" and counts.get(n, 0) >= MAX_ATTEMPTS]
    queue = [n for n in order
             if eff[n] == "PENDING" and counts.get(n, 0) < MAX_ATTEMPTS]
    usable = tuple(s for s in slots if s.endpoint not in blocked)
    launch = plan_launches_pinned(queue, busy, by_name, counts, usable)
    return {"abort": abort, "launch": launch, "done": done,
            "given_up": given_up, "busy": busy, "queue": queue,
            "unplaceable": unplaceable, "blocked_endpoints": sorted(blocked),
            "attempts_after": {n: counts.get(n, 0) for n in order},
            "finished": not queue and not busy,
            "slots": tuple(slots), "blocks": by_name}


def launch_argv(queue: R530Queue, block: R530Block) -> list[str]:
    """發射一塊的完整指令。**寫成純函式**，好讓測試逐字比對。"""
    return [
        "python3", queue.launcher,
        "--out", block.out,
        "--decision", queue.decision,
        "--task-set", block.task_set,
        "--arms", queue.arms,
        "--seed", block.seed,
        "--backend", queue.backend,
        "--model", queue.model,
        "--reasoning-effort", queue.reasoning_effort,
        "--request-timeout-s", str(queue.request_timeout_s),
    ]


def launch_block(queue: R530Queue, block: R530Block, slot: Slot,
                 root: pathlib.Path, log) -> int:
    """真的發射。`VACANT_GAIN_API` ＝ 這一塊釘住的那顆端點。

    `<out>.endpoint` 先落盤再發射：排程器下一輪要靠它把跑著的塊擺回槽，
    而「先跑起來才寫」會讓剛發出去那一瞬間的塊擺不回去 ⇒ 封鎖端點。
    """
    out_dir = root / block.out
    (root / f"{block.out}.endpoint").parent.mkdir(parents=True, exist_ok=True)
    (root / f"{block.out}.endpoint").write_text(block.endpoint + "\n",
                                                encoding="utf-8")
    env = dict(os.environ)
    env["VACANT_GAIN_API"] = block.endpoint
    lock = pathlib.Path.home() / f".launch_r530_{block.tag}.lock"
    argv = ["flock", "-n", str(lock), *launch_argv(queue, block)]
    log(f"  發射 {block.name} → {slot.slot_id}（{block.endpoint}）")
    logfile = root / f"{block.out}.launch.log"
    logfile.parent.mkdir(parents=True, exist_ok=True)
    with logfile.open("a", encoding="utf-8") as f:
        f.write(f"\n=== {_now()} {' '.join(argv)}\n")
        f.flush()
        proc = subprocess.Popen(argv, cwd=str(root), env=env,
                                stdout=f, stderr=subprocess.STDOUT,
                                start_new_session=True)
    del out_dir
    return proc.pid


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def plan_lines(plan: dict) -> list[str]:
    L = [f"完成 {len(plan['done'])}／佇列 {len(plan['queue'])}"
         f"／佔用 {sorted(plan['busy'].items())}"]
    if plan["blocked_endpoints"]:
        L.append(f"  ⚠ 封鎖端點 {plan['blocked_endpoints']}"
                 f"（有塊擺不回槽：{plan['unplaceable']}）——本輪不加負載")
    for name, why in plan["abort"]:
        L.append(f"  作廢 {name}（{why}）⇒ 重排第 "
                 f"{plan['attempts_after'][name]}/{MAX_ATTEMPTS} 次")
    for name in plan["given_up"]:
        L.append(f"  放棄 {name}（已重排 {MAX_ATTEMPTS} 次）——留給人裁決")
    for name, slot in plan["launch"]:
        L.append(f"  發射 {name} → {slot.slot_id}（{slot.endpoint}）")
    if plan["finished"]:
        L.append("  佇列跑完了")
    return L


def poll_loop(queue: R530Queue, root: pathlib.Path, log, *,
              max_ticks: int | None = None, poll_s: int = POLL_S) -> int:
    tick = 0
    while max_ticks is None or tick < max_ticks:
        tick += 1
        statuses, endpoints = observe(queue.blocks, root)
        counts = aborted_counts(queue.blocks, root)
        plan = plan_tick(queue.blocks, statuses, endpoints, counts)
        for line in plan_lines(plan):
            log(line)
        for name, why in plan["abort"]:
            abort_block(name, why or "UNKNOWN", root, log)
        for name, slot in plan["launch"]:
            rc = launch_block(queue, plan["blocks"][name], slot, root, log)
            if rc is None:                                   # pragma: no cover
                abort_preflight(name, 1, root, log)
        if plan["finished"]:
            log("佇列跑完，排程器退出。")
            return 0
        time.sleep(poll_s)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="R530 佇列排程器")
    ap.add_argument("--queue", required=True)
    ap.add_argument("--root", default=str(REPO))
    ap.add_argument("--dry-run", action="store_true",
                    help="只印計畫，不發射、不碰後端、不寫 runs/")
    ap.add_argument("--check", action="store_true",
                    help="只驗佇列與預註冊，印出每一塊的註冊行")
    ap.add_argument("--max-ticks", type=int, default=None)
    ap.add_argument("--poll-s", type=int, default=POLL_S)
    args = ap.parse_args(argv)

    q = load_queue(args.queue)
    root = pathlib.Path(args.root)
    if args.check:
        print(f"佇列 {q.name}　塊 {len(q.blocks)}　arms={q.arms}　"
              f"backend={q.backend}")
        for b in q.blocks:
            host = next(s.host for s in R530_SLOTS if s.endpoint == b.endpoint)
            print(f"  {b.name:26} host={host} seed={b.seed} "
                  f"tasks={len(b.tasks)}")
            print(f"    {registration_line(q, b)}")
        miss = check_prereg(q, root)
        if miss:
            print("\n⚠ DECISION 裡找不到這幾行（逐字）：")
            for m in miss:
                print(f"  {m}")
            return 1
        print("\n預註冊：每一塊都註冊過。")
        return 0

    def log(msg: str) -> None:
        print(f"[{_now()}] {msg}", flush=True)

    miss = check_prereg(q, root)
    if miss:
        raise SystemExit(
            "abort_not_registered：DECISION 裡找不到這幾行（逐字）：\n  "
            + "\n  ".join(miss) + "\n停。")
    if args.dry_run:
        statuses, endpoints = observe(q.blocks, root)
        counts = aborted_counts(q.blocks, root)
        plan = plan_tick(q.blocks, statuses, endpoints, counts)
        for line in plan_lines(plan):
            print(line)
        return 0
    return poll_loop(q, root, log, max_ticks=args.max_ticks,
                     poll_s=args.poll_s)


if __name__ == "__main__":
    raise SystemExit(main())
