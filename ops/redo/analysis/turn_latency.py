"""後端速度與單次上限：每批量三個數字（2026-11-21 起，結論檔都要附）。

1. 每輪模型回應時間：pi 的 session 日誌裡，每則 assistant 訊息的時間戳減去前一則（user／toolResult）的時間戳。
   兩臂分開列，再列合計的中位數、平均與 p90。⚠ 只看中位數會誤導：慢的是長上下文的尾巴
   （Colab 上 confirm2c 中位 10.9 秒、p90 111 秒），牆鐘被尾巴決定，平均與 p90 才看得出來。
2. P 臂內層嘗試撞單次上限的比例：restart 的 result.json 裡 timed_out＝true 的嘗試數／全部嘗試數。
   另列「至少撞一次的格數」與「每次嘗試都撞的格數」。
3. A 臂單次執行：cell.json 的 agent_wall_s 中位數，以及逾時次數（attempts[0].timed_out）。

用法：python3 ops/redo/analysis/turn_latency.py <run_root> [--json]
（stdlib only，也可以在 Colab VM 上跑：在程式前面設 ROOT＝"/srv/redo/run" 後，用 colab exec 餵進去。）
"""
from __future__ import annotations

import datetime as _dt
import glob
import json
import os
import statistics
import sys


def _ts(s: str) -> float:
    return _dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def session_turn_latencies(path: str) -> list[float]:
    out: list[float] = []
    prev = None
    try:
        fh = open(path, errors="replace")
    except OSError:
        return out
    with fh:
        for line in fh:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") != "message" or "timestamp" not in e:
                continue
            role = (e.get("message") or {}).get("role")
            t = _ts(e["timestamp"])
            if role == "assistant":
                if prev is not None:
                    out.append(t - prev)
                prev = None
            elif role in ("user", "toolResult"):
                prev = t
    return out


def _q(xs: list[float], q: float) -> float | None:
    """最近秩分位數：排序後取第 round(q × (n−1)) 個（index 四捨五入）。
    ⚠ n 為偶數時 q＝0.5 取的是**上中位數**（兩個中間值裡較大的那個），不是兩者平均的標準中位數；
    例如 confirm2 的 A 單次牆鐘：這裡 300.1 秒，標準中位數 289.9 秒。所有已寫成結論與總表的「中位」都是這個取法，
    為了和它們可比，這裡不改取法，只在輸出標明（2026-11-24 查證）。"""
    if not xs:
        return None
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(q * (len(xs) - 1) + 0.5))], 1)


def _stats(v: list[float]) -> dict:
    return {"n": len(v), "median": _q(v, 0.5), "mean": round(statistics.fmean(v), 1) if v else None,
            "p90": _q(v, 0.9)}


def measure(root: str) -> dict:
    cells = os.path.join(root, "cells")
    lat: dict[str, list[float]] = {}
    for arm_dir in glob.glob(os.path.join(cells, "*", "r*", "*")):
        arm = os.path.basename(arm_dir)
        for s in glob.glob(os.path.join(arm_dir, "attempt_*", "logs", "sessions", "**", "*.jsonl"), recursive=True):
            lat.setdefault(arm, []).extend(session_turn_latencies(s))
    allv = [x for v in lat.values() for x in v]
    inner = to = cells_any = cells_all = p_cells = 0
    caps: set = set()
    for rj in glob.glob(os.path.join(cells, "*", "r*", "*", "attempt_1", "logs", "vacant-work", "restart-*", "result.json")):
        try:
            r = json.load(open(rj))
        except (OSError, ValueError):
            continue
        att = r.get("attempts") or []
        if not att:
            continue
        p_cells += 1
        n_to = sum(1 for a in att if a.get("timed_out"))
        inner += len(att)
        to += n_to
        cells_any += n_to > 0
        cells_all += n_to == len(att)
    a_walls: list[float] = []
    a_to = a_n = 0
    ctrl = None
    rep = os.path.join(root, "REPORT.json")
    if os.path.exists(rep):
        try:
            ctrl = json.load(open(rep)).get("control")
        except (OSError, ValueError):
            ctrl = None
    ctrl = ctrl or "A"
    for cj in glob.glob(os.path.join(cells, "*", "r*", ctrl, "cell.json")):
        try:
            c = json.load(open(cj))
        except (OSError, ValueError):
            continue
        a_n += 1
        if c.get("agent_wall_s") is not None:
            a_walls.append(float(c["agent_wall_s"]))
        a_to += any(a.get("timed_out") for a in c.get("attempts") or [])
    return {
        "root": root,
        "turn_latency_s": {
            "all": _stats(allv),
            **{arm: _stats(v) for arm, v in sorted(lat.items())},
        },
        "p_inner_cap": {"cells": p_cells, "inner_attempts": inner, "timed_out": to,
                        "rate": round(to / inner, 3) if inner else None,
                        "cells_any_cut": cells_any, "cells_all_cut": cells_all},
        "control_single_run": {"arm": ctrl, "cells": a_n, "median_wall_s": _q(a_walls, 0.5), "timeouts": a_to},
    }


def main(argv: list[str]) -> int:
    root = argv[0] if argv and not argv[0].startswith("--") else globals().get("ROOT")
    if not root:
        print(__doc__)
        return 2
    m = measure(root)
    if "--json" in argv:
        print(json.dumps(m, ensure_ascii=False))
        return 0
    t = m["turn_latency_s"]
    print(f"{root}")
    print("  每輪回應（秒）：" + "；".join(f"{k} 中位（上中位數）{v['median']}／平均 {v['mean']}／p90 {v['p90']}（n={v['n']}）" for k, v in t.items()))
    p = m["p_inner_cap"]
    print(f"  P 內層撞上限：{p['timed_out']}/{p['inner_attempts']}（{p['rate']}）；至少一次 {p['cells_any_cut']}/{p['cells']} 格、每次都撞 {p['cells_all_cut']} 格")
    a = m["control_single_run"]
    print(f"  {a['arm']} 單次：中位牆鐘（上中位數）{a['median_wall_s']} 秒、逾時 {a['timeouts']}/{a['cells']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
elif "ROOT" in globals():
    main([])
