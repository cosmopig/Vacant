#!/usr/bin/env python3
"""多臂預註冊批次的主要比較＋Holm 校正（2026-11-25，rfh4：A／H／R／RF）。

harness 自己的 REPORT 只算 plan["pair"] 一組、未校正。這支照計畫的 analysis.comparisons 逐組配對：
- 每個比較各自配對（題×重複），該比較的兩臂任一臂 infra_void 或沒有 cell，那一對在這個比較裡不計；
- 精確雙尾 McNemar（與 redo.mcnemar_exact 同式），Holm–Bonferroni（family α＝analysis.alpha）；
- state：EFFECTIVE／UNRESOLVED／CONTRADICTS／INCOMPLETE／MIXED_GRADER（定義見計畫 prereg.states）；
- 操作檢查：每臂 hint_bytes>0 的嘗試數（讀 attempt_*/attempt.json），分機器的通過數；
  送出的 hint 有多少到了 400 位元組上限、有多少「看不出期望值」（預註冊的操作定義：hint 本文
  不含 `!=`、`AssertionError`、`expected`／`Expected` 任何一個；需要 harness 記下 hint_text）。
只讀 run root，不寫任何東西（除非給 --json-out）。
用法：python3 ops/redo/analysis/multi_arm.py --root <run root> [--json-out X]
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys

HINT_CAP = 400                     # 與 redo.HINT_CAP 相同
EXPECT_MARKERS = ("!=", "AssertionError", "expected", "Expected")


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / 2.0 ** n)


def holm(ps: dict[str, float], alpha: float) -> dict[str, bool]:
    """回傳每個比較是否被拒絕（Holm 逐步：遞增 p，門檻 α/(m−i)，第一個沒拒絕就全部停）。"""
    order = sorted(ps, key=lambda k: (ps[k], k))
    m, out, go = len(order), {}, True
    for i, k in enumerate(order):
        go = go and ps[k] < alpha / (m - i)
        out[k] = go
    return out


def load(root: pathlib.Path) -> tuple[dict, list[dict]]:
    run = json.loads((root / "RUN.json").read_text())
    cells = []
    for p in sorted((root / "cells").glob("*/r*/*/cell.json")):
        c = json.loads(p.read_text())
        if c.get("plan_sha256") != run["plan_sha256"]:
            continue
        hb, ht = [], []
        for a in sorted(p.parent.glob("attempt_*/attempt.json")):
            try:
                d = json.loads(a.read_text())
                hb.append(int(d.get("hint_bytes") or 0))
                ht.append(d.get("hint_text"))
            except (OSError, ValueError):
                hb.append(None)
                ht.append(None)
        c["_hint_bytes"], c["_hint_text"] = hb, ht
        cells.append(c)
    return run, cells


def analyse(run: dict, cells: list[dict]) -> dict:
    plan = run["plan"]
    an = plan["analysis"]
    alpha = float(an.get("alpha", 0.05))
    planned = len(plan["tasks"]) * int(plan["reps"])
    by = {(c["task"], c["rep"], c["arm"]): c for c in cells}
    comps: dict[str, dict] = {}
    for comp in an["comparisons"]:
        ctrl, treat = comp["control"], comp["treatment"]
        b = c_ = both = neither = 0
        excluded = 0
        kinds = set()
        abw = 0
        per_prov: dict[str, dict] = {}
        for t in plan["tasks"]:
            for r in range(1, int(plan["reps"]) + 1):
                x, y = by.get((t, r, ctrl)), by.get((t, r, treat))
                if x is None or y is None:
                    continue
                if x.get("infra_void") or y.get("infra_void"):
                    excluded += 1
                    continue
                kinds |= {x.get("grader_kind"), y.get("grader_kind")}
                abw += bool(y.get("accepted") and not y.get("pass"))
                xp, yp = bool(x["pass"]), bool(y["pass"])
                b += xp and not yp
                c_ += yp and not xp
                both += xp and yp
                neither += not xp and not yp
                pp = per_prov.setdefault(x.get("provider", "?"), {"pairs": 0, "ctrl": 0, "treat": 0})
                pp["pairs"] += 1
                pp["ctrl"] += xp
                pp["treat"] += yp
        n = b + c_ + both + neither
        comps[comp["name"]] = {"control": ctrl, "treatment": treat, "pairs": n, "excluded_void_pairs": excluded,
                               "complete": n + excluded >= planned, "ctrl_pass": b + both, "treat_pass": c_ + both,
                               "b": b, "c": c_, "p": mcnemar_exact(b, c_), "treat_accepted_but_wrong": abw,
                               "grader_kinds": sorted(k for k in kinds if k), "by_provider": per_prov}
    rej = holm({k: v["p"] for k, v in comps.items()}, alpha)
    for k, v in comps.items():
        v["holm_reject"] = rej[k]
        if not v["complete"]:
            v["state"] = "INCOMPLETE"
        elif len(v["grader_kinds"]) > 1:
            v["state"] = "MIXED_GRADER"
        elif rej[k] and v["c"] > v["b"] and v["treat_accepted_but_wrong"] == 0:
            v["state"] = "EFFECTIVE"
        elif rej[k] and v["b"] > v["c"]:
            v["state"] = "CONTRADICTS"
        else:
            v["state"] = "UNRESOLVED"
    arms = {}
    for arm in plan["arms"]:
        cs = [c for c in cells if c["arm"] == arm]
        hb = [h for c in cs for h in c["_hint_bytes"]]
        texts = [t for c in cs for h, t in zip(c["_hint_bytes"], c.get("_hint_text") or []) if h]
        known = [t for t in texts if isinstance(t, str)]
        arms[arm] = {"cells": len(cs), "infra_void": sum(1 for c in cs if c.get("infra_void")),
                     "pass": sum(1 for c in cs if not c.get("infra_void") and c.get("pass")),
                     "attempts": len(hb), "attempts_with_hint": sum(1 for h in hb if h),
                     "attempts_hint_unknown": sum(1 for h in hb if h is None),
                     "hints_text_known": len(known),
                     "hints_at_cap": sum(1 for t in known if len(t.encode()) >= HINT_CAP - 3),
                     "hints_no_expected_value": sum(1 for t in known if not any(m in t for m in EXPECT_MARKERS)),
                     "mean_attempts": round(sum(c.get("n_attempts", 0) for c in cs) / len(cs), 3) if cs else None}
    return {"plan_id": plan["id"], "plan_sha256": run["plan_sha256"], "alpha": alpha,
            "multiplicity": "holm", "pairs_planned": planned, "comparisons": comps, "arms": arms}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--json-out")
    a = ap.parse_args(argv)
    run, cells = load(pathlib.Path(a.root).expanduser())
    out = analyse(run, cells)
    txt = json.dumps(out, ensure_ascii=False, indent=1)
    if a.json_out:
        pathlib.Path(a.json_out).write_text(txt + "\n")
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
