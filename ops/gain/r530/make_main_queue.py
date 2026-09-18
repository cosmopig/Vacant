#!/usr/bin/env python3
"""產生 R530 正式佇列 `queues/r530_main.json`。**這支不發射，只寫 JSON。**

規格：預註冊 §三-5（seed 三顆、塊與後端分配）＋ Fable 2026-09-14 第七輪裁決。

180 格 ＝ 20 題 × 3 臂 × 3 seed。切法與每一條約束怎麼被滿足：

| 約束 | 怎麼滿足的 | 由誰擋 |
|---|---|---|
| 同一題三臂同一 seed 同一台 | **一塊 ＝ 一顆 seed × 一組題 × 三臂**，整塊打同一個 endpoint | 結構性（塊自帶 endpoint） |
| 題在兩台輪流 | 第 k 顆 seed 的第 i 題走 `hosts[(i + k) % 2]` ⇒ **同一題在三顆 seed 之間換台** | `load_queue` 的 `abort_all_blocks_one_host` |
| 每台 ≤4 串 | 槽表每台 4 格 | `_assert_per_host_cap`（import 時） |
| tight／loose 交錯 | `loose` 被放到**不同的 (台, 塊)**——散在題序上不夠，因為塊是按位置奇偶＋每 5 個切的 | 下面的 `interleave()` |
| 一格一次 | `(seed, task)` 不得重複 | `load_queue` 逐對檢查 |

⚠ **為什麼「題在兩台輪流」要跨 seed 而不是塊內輪流**：一塊裡的三條臂必須同台
（否則後端從 task 層級的干擾項變成 arm 層級的混淆項），所以塊內沒有輪流的空間。
輪流只能發生在**塊與塊之間**，而讓同一題在三顆 seed 之間換台，
等於把後端的效應打散到 seed 這一層——那正是 §三-0 要的。

用法：
    python3 ops/gain/r530/make_main_queue.py            # 寫檔 ＋ 印 sha256
    python3 ops/gain/r530/make_main_queue.py --stdout   # 只印，不寫
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

#: 預註冊 §三-5 指名的三顆 seed。**逐字**，不准在這裡即興。
SEEDS = ("g-r530-s1", "g-r530-s2", "g-r530-s3")

EP1003 = "http://100.119.113.56:1234/v1/chat/completions"
EP1004 = "http://100.86.226.21:1234/v1/chat/completions"
HOSTS = ((EP1003, "1003"), (EP1004, "1004"))

DECISION = "decisions/DECISION_20260913_R530_OPEN_GOAL_WITH_WITHOUT_VACANT_PREREG.md"
ARMS = "A-SOLO,A-CONF,A-GATE"
#: 一塊幾題。5 題 × 3 臂 ＝ 15 格；一顆 seed 4 塊（每台 2 塊）⇒ 12 塊、180 格。
TASKS_PER_BLOCK = 5


def strata() -> dict[str, str]:
    out = {}
    for d in sorted((HERE / "bank").iterdir()):
        if d.is_dir() and (d / "meta.json").is_file():
            out[d.name] = json.loads(
                (d / "meta.json").read_text(encoding="utf-8")).get("stratum")
    return out


def interleave(ids: list[str], strat: dict[str, str]) -> list[str]:
    """把 `loose` 散到**不同的 (台, 塊)** 去，不只是散在題序上。

    為什麼「散在題序上」不夠：塊是由「位置的奇偶決定台、再每 5 個切一塊」
    切出來的，所以題序上相鄰很遠的兩題**可能落進同一塊**。
    第一版就是這樣——`ow_19` 與 `ow_20` 都掉進 `g_r530_s1_1004_2`。

    塊是**排程的單位**也是**中斷時的可分析單位**：`loose` 只有 3 題，
    兩題擠在同一塊的話，那一塊一旦作廢，`loose` 這一層就剩一題
    ——§六 的逐層報表會少掉一整格，而那不會有任何錯誤訊息。

    ⇒ 位置先均分，再逐個往後挪到 `(奇偶, 第幾塊)` 不撞為止。
      奇偶決定台、`//TASKS_PER_BLOCK` 決定第幾塊，兩者合起來就是「哪一塊」。
      seed 之間奇偶會整體翻轉（`(i+k)%2`），但**塊的成員不變**
      ⇒ 這個保證對三顆 seed 同時成立。
    """
    tight = [t for t in ids if strat.get(t) == "tight"]
    loose = [t for t in ids if strat.get(t) == "loose"]
    total = len(tight) + len(loose)
    if not loose:
        return list(tight)

    def cell(pos: int) -> tuple[int, int]:
        # (奇偶 ⇒ 哪一台, 該台的第幾塊)。同台的位置每隔 2 個排一個。
        return pos % 2, (pos // 2) // TASKS_PER_BLOCK

    used: set[tuple[int, int]] = set()
    slots: list[int] = []
    for j in range(len(loose)):
        pos = int(round((j + 0.5) * total / len(loose)))
        pos = max(0, min(total - 1, pos))
        for _ in range(total):
            if pos not in slots and cell(pos) not in used:
                break
            pos = (pos + 1) % total
        used.add(cell(pos))
        slots.append(pos)

    out: list[str] = []
    ti = li = 0
    for i in range(total):
        if i in slots:
            out.append(loose[li]); li += 1
        else:
            out.append(tight[ti]); ti += 1
    return out


def build() -> dict:
    strat = strata()
    ids = interleave(sorted(strat), strat)
    if len(ids) != 20:
        raise SystemExit(f"題庫有 {len(ids)} 題，預註冊登記的是 20 題。停。")

    blocks = []
    for k, seed in enumerate(SEEDS):
        per_host: dict[str, list[str]] = {h: [] for _ep, h in HOSTS}
        for i, tid in enumerate(ids):
            _ep, host = HOSTS[(i + k) % len(HOSTS)]
            per_host[host].append(tid)
        for ep, host in HOSTS:
            mine = per_host[host]
            for b, start in enumerate(range(0, len(mine), TASKS_PER_BLOCK), 1):
                chunk = mine[start:start + TASKS_PER_BLOCK]
                if not chunk:
                    continue
                sk = seed.split("-")[-1]          # s1 / s2 / s3
                blocks.append({
                    "name": f"g_r530_{sk}_{host}_{b}",
                    "tasks": chunk,
                    "seed": seed,
                    "tag": f"r530{sk}{host}{b}",
                    "endpoint": ep,
                    "note": (f"seed {seed}／{host}／第 {b} 塊；"
                             f"tight {sum(1 for t in chunk if strat[t] == 'tight')}"
                             f"／loose {sum(1 for t in chunk if strat[t] == 'loose')}"),
                })
    return {
        "name": "r530_main",
        "decision": DECISION,
        "launcher": "ops/gain/r530/run_r530.py",
        "arms": ARMS,
        "backend": "unshare",
        "request_timeout_s": 900,
        "reasoning_effort": "none",
        "model": "gemma-4-12b-it-qat",
        "gauge_scope": "bank",
        "tool_protocol": "native",
        "sandbox_uid": 65534,
        "sandbox_gid": 65534,
        "backends": {
            EP1003: {
                "host": "1003",
                "lmstudio_version": "0.4.24.0",
                "version_source": ("人回報（Fable 2026-09-11 在該機上 `lms version`）；"
                                   "runner 查證不到 ⇒ 這是宣稱不是量測"),
                "measured_2026_09_14": {
                    "reasoning_tokens_under_tools": 0,
                    "cold_prefill_ms_per_1k": 1509,
                    "warm_prefill_ms_per_1k": 144,
                    "generation_ms_per_token": 22.6,
                },
            },
            EP1004: {
                "host": "1004",
                "lmstudio_version": "0.4.17.0",
                "version_source": "人回報；runner 查證不到 ⇒ 這是宣稱不是量測",
                "measured_2026_09_14": {
                    "reasoning_tokens_under_tools": 0,
                    "cold_prefill_ms_per_1k": 481,
                    "warm_prefill_ms_per_1k": 78,
                    "generation_ms_per_token": 14.4,
                },
            },
        },
        "blocks": blocks,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="產生 R530 正式佇列（不發射）")
    ap.add_argument("--out", default=str(HERE / "queues" / "r530_main.json"))
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()

    q = build()
    text = json.dumps(q, ensure_ascii=False, indent=2) + "\n"
    if args.stdout:
        print(text)
        return 0
    p = pathlib.Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

    strat = strata()
    cells = sum(len(b["tasks"]) for b in q["blocks"]) * len(ARMS.split(","))
    print(f"blocks={len(q['blocks'])}  tasks/block={TASKS_PER_BLOCK}  "
          f"cells={cells}  seeds={len(SEEDS)}")
    per_host: dict[str, int] = {}
    for b in q["blocks"]:
        h = "1003" if b["endpoint"] == EP1003 else "1004"
        per_host[h] = per_host.get(h, 0) + len(b["tasks"])
    print(f"題格分配 per host: {per_host}")
    seen: dict[str, set] = {}
    for b in q["blocks"]:
        h = "1003" if b["endpoint"] == EP1003 else "1004"
        for t in b["tasks"]:
            seen.setdefault(t, set()).add(h)
    both = sum(1 for v in seen.values() if len(v) == 2)
    print(f"跨 seed 用過兩台的題：{both}/{len(seen)}")
    loose_blocks = {b["name"] for b in q["blocks"]
                    if any(strat[t] == "loose" for t in b["tasks"])}
    print(f"含 loose 的塊：{len(loose_blocks)}（3 題 loose × 3 seed ＝ 9 格，"
          f"散在 {len(loose_blocks)} 塊）")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    print(f"\n{p}\nsha256 = {sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
