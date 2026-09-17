#!/usr/bin/env python3
"""R531 佇列產生器：72 題 × 2 臂 × seed-1，**只用 1004 的四串**。

這支在架構裡承重什麼（`DECISION_20260915_R531_…_PREREG.md` §五）：
`ops/gain/r530/schedule_r530.py` 吃的是一份 JSON 佇列（`blocks` 陣列），
R531 沿用**同一支排程器、同一個格式**——Fable 2026-09-15 裁決第 1 點：
「不准改 openwork_arms.py／sandbox.py／receipts.py 任何一行；
要改的只有題庫轉換器與新的佇列。」這支就是「新的佇列」那一半。

## 為什麼四塊要**跨族交錯**而不是一族一塊

一塊 ＝ 一條串 ＝ 一個行程。四塊如果按族切（pbf 一塊、pbc 一塊…），
那麼「族」就與「串」完全共線：某一串剛好遇到後端變慢、或剛好被
R530 的殘塊擠到，那個減速會整包記在某一族頭上，而**分不開**。
交錯之後每一塊都含四族，族間的比較不再吃串的差異。
（同一題的兩條臂本來就在同一塊裡跑，所以臂間比較不受這件事影響——
這一條沿用 R530「同題三臂同台」的同一個保證。）

## 1003 一格都不准碰

R530 的補跑在 1004 上（2026-09-16 01:45Z 改的），而 1003 被人類的
qwen 27B 佔著。R531 **只寫 1004 的端點**，而且要等 1004 空出來才發射。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[3]
TASKLIST = REPO / "ops" / "gain" / "r531" / "tasks_r531.json"
OUT = REPO / "ops" / "gain" / "r531" / "queues" / "r531_main.json"

EP_1004 = "http://100.86.226.21:1234/v1/chat/completions"
DECISION = "DECISION_20260915_R531_PUBLIC_BENCH_PLAIN_VS_VACANT_PREREG.md"
N_STREAMS = 4


def interleave(ids: list[str], n: int) -> list[list[str]]:
    """依族輪流發牌 ⇒ 每一塊的族組成盡可能相同，且**與輸入順序無關**。"""
    fams: dict[str, list[str]] = {}
    for t in sorted(ids):
        fams.setdefault(t.split("_")[0], []).append(t)
    blocks: list[list[str]] = [[] for _ in range(n)]
    k = 0
    for fam in sorted(fams):
        for t in fams[fam]:
            blocks[k % n].append(t)
            k += 1
    return [sorted(b) for b in blocks]


PRECHECK_PER_FAM = 3          # Fable 2026-09-15 裁決第 5 點：每族 3 題，共 12
PRECHECK_SEED = "g-r531-pre"


def registration_line(*, out: str, task_set: str, arms: str, seed: str, endpoint: str) -> str:
    """**與 `ops/gain/r530/run_r530.py::registration_line` 逐字同形。**

    runner 會在 DECISION 檔裡整組比對這一行，找不到就 `abort_not_registered`。
    ⇒ 這支印出來的東西必須原封不動貼進 DECISION，一個空格都不能差。
    """
    #: ⚠ `out` 這裡要放的是 **basename 不是路徑**——runner 那一支寫的是
    #:   `pathlib.Path(out).name`。放 `runs/_probe/g_r531_pre_1` 會比對不上，
    #:   而失敗訊息是 `abort_not_registered`（看起來像沒註冊，其實是格式差一段路徑）。
    return (f"R530_BLOCK: {pathlib.Path(out).name} tasks={task_set} "
            f"arms={arms} seed={seed} endpoint={endpoint}")


def build_precheck(ids: list[str]) -> list[dict]:
    """污染預檢：每族前 3 題（決定性），**只跑 `A-SOLO`**，四塊平行。

    量的是「第一次就通過全部可見測試」的比例——`A-SOLO` 宣告完成即交付，
    所以它的 `visible_all_pass` 就是那個比例，**不需要任何新指標**。
    """
    fams: dict[str, list[str]] = {}
    for t in sorted(ids):
        fams.setdefault(t.split("_")[0], []).append(t)
    picked = [t for f in sorted(fams) for t in fams[f][:PRECHECK_PER_FAM]]
    return [{"name": f"g_r531_pre_{i + 1}", "tasks": picked[i::4], "seed": PRECHECK_SEED,
             "tag": f"r531pre{i + 1}", "endpoint": EP_1004,
             "note": "污染預檢（A-SOLO 一輪）；runs/_probe 底下，不是證據"}
            for i in range(4) if picked[i::4]]


def main() -> int:
    ap = argparse.ArgumentParser(description="R531 佇列產生（零模型呼叫）")
    ap.add_argument("--seed", default="g-r531-s1")
    ap.add_argument("--streams", type=int, default=N_STREAMS)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    ids = json.loads(TASKLIST.read_text(encoding="utf-8"))["tasks"]
    blocks = interleave(ids, args.streams)
    q = {
        "name": "r531_main",
        "decision": DECISION,
        "launcher": "ops/gain/r530/run_r530.py",
        "arms": "A-SOLO,A-GATE",
        "backend": "unshare",
        "request_timeout_s": 900,
        "reasoning_effort": "none",
        "model": "gemma-4-12b-it-qat",
        "gauge_scope": "none",
        "gauge_scope_note": (
            "R531 的 E-3 走 `ops/gain/r530/gauge.py --task-set <r531 ids>`（本檔外，"
            "發射前跑一次並落盤），**不是** `gauge_r530.py --check`——後者量的是 "
            "`ops/gain/r530/bank/`（R530 自己的題庫資料），與 R531 的 templates/hidden/gauge "
            "無關。寫 `bank` 會讓 R531 的發射去驗 R530 的題庫，綠了也不代表 R531 的量具過。"),
        "tool_protocol": "native",
        "sandbox_uid": 65534,
        "sandbox_gid": 65534,
        "backends": {EP_1004: {"host": "1004", "streams": args.streams,
                               "note": "R531 只用 1004。1003 被人類的 qwen 27B 佔著，一格都不碰。"}},
        "blocks": [
            {"name": f"g_r531_s1_1004_{i + 1}",
             "tasks": b,
             "seed": args.seed,
             "tag": f"r531s11004{i + 1}",
             "endpoint": EP_1004,
             "note": (f"seed {args.seed}／1004／第 {i + 1} 塊；"
                      + "／".join(f"{f}×{sum(1 for t in b if t.startswith(f))}"
                                 for f in ("pbf", "pbc", "pba", "pbd")))}
            for i, b in enumerate(blocks)],
    }
    p = pathlib.Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(q, ensure_ascii=False, indent=2) + "\n"
    p.write_text(blob, encoding="utf-8")
    print(f"queue → {p}")
    for b in q["blocks"]:
        print(f"  {b['name']}: {len(b['tasks'])} 題  {b['note'].split('；')[1]}")
    print(f"queue sha256 = {hashlib.sha256(blob.encode('utf-8')).hexdigest()}")

    # ── 註冊行：預檢四塊 ＋ 正式 run 四塊。逐字貼進 DECISION。 ───────────
    lines = []
    for b in build_precheck(ids):
        lines.append(registration_line(
            out=f"runs/_probe/{b['name']}", task_set=",".join(b["tasks"]),
            arms="A-SOLO", seed=b["seed"], endpoint=b["endpoint"]))
    for b in q["blocks"]:
        lines.append(registration_line(
            out=f"runs/{b['name']}", task_set=",".join(b["tasks"]),
            arms=q["arms"], seed=b["seed"], endpoint=b["endpoint"]))
    rp = p.parent / "REGISTRATION.txt"
    rp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"registration lines ({len(lines)}) → {rp}")

    pcq = dict(q, name="r531_precheck", arms="A-SOLO",
               blocks=[dict(b, name=b["name"]) for b in build_precheck(ids)])
    pp = p.parent / "r531_precheck.json"
    pblob = json.dumps(pcq, ensure_ascii=False, indent=2) + "\n"
    pp.write_text(pblob, encoding="utf-8")
    print(f"precheck queue → {pp}  sha256 = {hashlib.sha256(pblob.encode('utf-8')).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
