"""產品臂（`vacant do pi`，usage=none）的模型呼叫數：從每格 vacant-work 底下的 pi JSON 日誌補算。

harness 對 P 臂記 usage=none（外層只看到一個 `vacant do` 行程），預註冊的 known_limits 要求結案時補這個數字。
一次模型呼叫＝pi 日誌裡一個 role=assistant 的 message_end（同一行重複出現只算一次）。

證據不足就說不知道，不補零（2026-11-19 日報 P1）：
- 每一格以 restart 的 result.json 為準：它記了這格實際跑了幾次內層嘗試。找不到 result.json ⇒ 這格 UNKNOWN。
- result.json 記的每一次嘗試都要有自己的 agent_stdout.log；缺檔、或有無法解析的 JSON 行（截斷）⇒ 這格 UNKNOWN。
- 嘗試跑了超過 MIN_WALL_S 秒、日誌裡卻一次呼叫都沒有 ⇒ UNKNOWN（日誌多半沒寫進去，不是真的 0 次）。
平均只算 KNOWN 的格；UNKNOWN 的格數與原因一起印出，讓讀的人自己判斷偏差方向。

用法：python3 ops/redo/analysis/p_model_calls.py ~/dev/ops/redo_runs/confirm1 [--arm P] [--json]
"""
from __future__ import annotations

import glob
import json
import statistics
import sys

MIN_WALL_S = 30.0


def count_log(path: str) -> tuple[int, int]:
    """回傳（assistant 呼叫數, 無法解析的行數）。完全相同的行只算一次（重複寫入的防呆）。"""
    seen: set[str] = set()
    calls = bad = 0
    with open(path, errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except ValueError:
                bad += 1
                continue
            if e.get("type") != "message_end" or (e.get("message") or {}).get("role") != "assistant":
                continue
            if line in seen:
                continue
            seen.add(line)
            calls += 1
    return calls, bad


def cell_calls(cell_dir: str) -> dict:
    """一格 P 臂：{"status": "known"|"unknown", "calls": int|None, "attempts": int|None, "why": str|None}"""
    res = sorted(glob.glob(f"{cell_dir}/attempt_*/logs/vacant-work/restart-*/result.json"))
    if not res:
        return {"status": "unknown", "calls": None, "attempts": None, "why": "沒有 restart result.json"}
    if len(res) > 1:
        return {"status": "unknown", "calls": None, "attempts": None, "why": f"{len(res)} 個 result.json（外層重跑過？）"}
    try:
        r = json.load(open(res[0]))
    except (OSError, ValueError):
        return {"status": "unknown", "calls": None, "attempts": None, "why": "result.json 無法讀取"}
    base = res[0].rsplit("/", 1)[0]
    total = 0
    for a in r.get("attempts", []):
        k = a.get("attempt")
        log = f"{base}/attempt_{k}/logs/agent_stdout.log"
        try:
            n, bad = count_log(log)
        except OSError:
            return {"status": "unknown", "calls": None, "attempts": len(r["attempts"]), "why": f"第 {k} 次嘗試沒有日誌"}
        if bad:
            return {"status": "unknown", "calls": None, "attempts": len(r["attempts"]),
                    "why": f"第 {k} 次嘗試的日誌有 {bad} 行無法解析"}
        if n == 0 and float(a.get("wall_s") or 0) > MIN_WALL_S:
            return {"status": "unknown", "calls": None, "attempts": len(r["attempts"]),
                    "why": f"第 {k} 次嘗試跑了 {a.get('wall_s')}s 卻沒有任何呼叫紀錄"}
        total += n
    return {"status": "known", "calls": total, "attempts": len(r.get("attempts", [])), "why": None}


def summarize(root: str, arm: str = "P") -> dict:
    cells = sorted(glob.glob(f"{root}/cells/*/r*/{arm}/cell.json"))
    rows = {c.rsplit("/", 1)[0].split("/cells/", 1)[-1]: cell_calls(c.rsplit("/", 1)[0]) for c in cells}
    known = [v for v in rows.values() if v["status"] == "known"]
    unknown = {k: v["why"] for k, v in rows.items() if v["status"] == "unknown"}
    out = {"root": root, "arm": arm, "cells": len(rows), "known": len(known), "unknown": len(unknown),
           "unknown_cells": unknown}
    if known:
        out.update(mean_calls=round(statistics.mean(v["calls"] for v in known), 1),
                   median_calls=statistics.median(v["calls"] for v in known),
                   mean_attempts=round(statistics.mean(v["attempts"] for v in known), 3))
    return out


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    arm = argv[argv.index("--arm") + 1] if "--arm" in argv else "P"
    if "--arm" in argv:
        args.remove(arm)
    s = summarize(args[0], arm)
    if "--json" in argv:
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return 0
    if not s["cells"]:
        print("沒有找到格子")
        return 1
    head = f"{s['root']} 臂 {arm}：{s['cells']} 格，可算 {s['known']}、UNKNOWN {s['unknown']}"
    if s["known"]:
        head += (f"；可算的格平均模型呼叫 {s['mean_calls']}（中位數 {s['median_calls']}），"
                 f"平均內層嘗試 {s['mean_attempts']}")
    print(head)
    for k, why in s["unknown_cells"].items():
        print(f"  UNKNOWN {k}: {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
