#!/usr/bin/env python3
"""Devin × cchard16（降為 2 重複後）的補充分析：配對區間、題群集檢定、A 高於重做臂的診斷。

讀 devin_batch_analysis.py 產生的 serial_rescore.jsonl（序列重評分＝正式分數）與同一個（r1–r2 視圖）根。
全部是描述性／探索性；Newcombe 區間把 (task, rep) 當獨立配對，同題的兩個重複其實相關，
所以另外給「以題為群集」的符號翻轉檢定與群集 bootstrap 區間（較誠實的那個）。

Usage: devin_cchard16_followup.py --root VIEW_ROOT --rescore serial_rescore.jsonl --out OUTDIR
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
import math
import pathlib
import random
import statistics

ARMS = ["A", "R", "B", "C"]


def wilson(k: int, n: int, z: float = 1.959964):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def newcombe_paired(a: int, b: int, c: int, d: int, z: float = 1.959964):
    """Newcombe 1998 方法 10。a 都過、b 只對照過、c 只處理過、d 都沒過；回傳 (差, 下, 上)，差＝處理−對照。"""
    n = a + b + c + d
    p_ctl, p_trt = (a + b) / n, (a + c) / n
    l1, u1 = wilson(a + c, n, z)  # 處理
    l2, u2 = wilson(a + b, n, z)  # 對照
    A = (a + b) * (c + d) * (a + c) * (b + d)
    if A == 0:
        phi = 0.0
    else:
        C = a * d - b * c
        if C > n / 2:
            C -= n / 2
        elif C >= 0:
            C = 0
        phi = C / math.sqrt(A)
    diff = p_trt - p_ctl
    lo = diff - math.sqrt((p_trt - l1) ** 2 + (u2 - p_ctl) ** 2 - 2 * phi * (p_trt - l1) * (u2 - p_ctl))
    hi = diff + math.sqrt((u1 - p_trt) ** 2 + (p_ctl - l2) ** 2 - 2 * phi * (u1 - p_trt) * (p_ctl - l2))
    return diff, lo, hi


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / 2.0 ** n)


def cluster_tests(tasks, d_by_task, seed=20261128, B=20000):
    """d_by_task：每題的 (處理成功數−對照成功數)/重複數。符號翻轉精確檢定（2^m）＋群集 bootstrap 95% 區間。"""
    vals = [d_by_task[t] for t in tasks]
    m = len(vals)
    obs = sum(vals) / m
    nz = [v for v in vals if v != 0]
    ge = 0
    tot = 0
    for signs in itertools.product((1, -1), repeat=len(nz)):
        s = sum(sg * v for sg, v in zip(signs, nz)) / m
        tot += 1
        if abs(s) >= abs(obs) - 1e-12:
            ge += 1
    p = ge / tot
    rng = random.Random(seed)
    boots = sorted(sum(vals[rng.randrange(m)] for _ in range(m)) / m for _ in range(B))
    return {"mean_diff": obs, "tasks": m, "tasks_nonzero": len(nz), "p_signflip_exact": p,
            "boot_ci95": [boots[int(0.025 * B)], boots[int(0.975 * B) - 1]]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--rescore", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="r1-r2")
    a = ap.parse_args()
    root, out = pathlib.Path(a.root), pathlib.Path(a.out)
    score = {}
    for ln in pathlib.Path(a.rescore).read_text().splitlines():
        r = json.loads(ln)
        score[r["cell"]] = r
    cells = []
    for cp in sorted((root / "cells").glob("*/r*/*/cell.json")):
        c = json.loads(cp.read_text())
        c["_dir"] = cp.parent
        c["_att"] = []
        for k in range(1, int(c.get("n_attempts") or 0) + 1):
            ap_ = cp.parent / f"attempt_{k}" / "attempt.json"
            c["_att"].append(json.loads(ap_.read_text()) if ap_.is_file() else {})
        cells.append(c)
    by = {(c["task"], c["rep"], c["arm"]): c for c in cells}
    ok = lambda c: bool(score.get(c["cell"], {}).get("serial_pass"))  # noqa: E731
    res: dict = {"label": a.label}

    # ---- 配對比較（C 對 B、C 對 R；另列其他）
    pairs_def = [("B", "C"), ("R", "C"), ("A", "R"), ("A", "B"), ("A", "C")]
    cmp_out = []
    for ctl, trt in pairs_def:
        keys = sorted({(t, r) for (t, r, ar) in by if ar in (ctl, trt)})
        both = oc = ot = nei = 0
        per_task = collections.defaultdict(lambda: [0, 0])  # [n, treat-ctl]
        used = 0
        for t, r in keys:
            x, y = by.get((t, r, ctl)), by.get((t, r, trt))
            if not x or not y or x.get("infra_void") or y.get("infra_void") or x["cell"] not in score or y["cell"] not in score:
                continue
            used += 1
            px, py = ok(x), ok(y)
            both += px and py
            oc += px and not py
            ot += py and not px
            nei += (not px) and (not py)
            per_task[t][0] += 1
            per_task[t][1] += int(py) - int(px)
        d, lo, hi = newcombe_paired(both, oc, ot, nei)
        dt = {t: v[1] / v[0] for t, v in per_task.items()}
        ct = cluster_tests(sorted(dt), dt)
        cmp_out.append({"control": ctl, "treatment": trt, "pairs": used, "both": both, "only_control": oc, "only_treatment": ot, "neither": nei,
                        "diff_pp": round(100 * d, 2), "newcombe_ci95_pp": [round(100 * lo, 2), round(100 * hi, 2)],
                        "p_mcnemar_exact": mcnemar_exact(oc, ot),
                        "cluster": {"p_signflip_exact": ct["p_signflip_exact"], "tasks_nonzero": ct["tasks_nonzero"], "tasks": ct["tasks"],
                                    "boot_ci95_pp": [round(100 * ct["boot_ci95"][0], 2), round(100 * ct["boot_ci95"][1], 2)]}})
    res["comparisons"] = cmp_out

    # ---- 缺格敏感度（任一臂 void 的配對排除；算失敗／算成功）
    voids = [c["cell"] for c in cells if c.get("infra_void")]
    res["infra_void_cells"] = voids
    expected = {(t, r, ar) for t in {k[0] for k in by} for r in sorted({k[1] for k in by}) for ar in ARMS}
    res["missing_cells"] = sorted("/".join(map(str, k)) for k in expected - set(by))

    # ---- 診斷
    diag: dict = {}
    for ar in ARMS:
        cs = [c for c in cells if c["arm"] == ar and not c.get("infra_void")]
        atts = [(c, k, at) for c in cs for k, at in enumerate(c["_att"], 1)]
        timed = sum(1 for _, _, at in atts if at.get("timed_out"))
        a1 = [(c, at) for c, k, at in atts if k == 1]
        a1_timed = sum(1 for _, at in a1 if at.get("timed_out"))
        a1_acc = sum(1 for _, at in a1 if (at.get("acc") or {}).get("accept"))
        okc = [c for c in cs if ok(c)]
        acc_cells = [c for c in cs if c.get("accepted")]
        acc_hidden_fail = [c["cell"] for c in acc_cells if not ok(c)]
        # 成功格的歸屬：在第幾次嘗試交付
        deliv = collections.Counter(c.get("delivered_attempt") for c in okc)
        # 非逾時嘗試的牆鐘
        free_w = [at.get("wall_s") for _, _, at in atts if not at.get("timed_out") and at.get("wall_s")]
        succ_attempt_w = [at.get("wall_s") for c, k, at in atts if ok(c) and k == c.get("delivered_attempt") and not at.get("timed_out")]
        tok_in = [((at.get("usage") or {}).get("input") or 0) + ((at.get("usage") or {}).get("output") or 0) for _, _, at in atts if at.get("usage") and not (at["usage"] or {}).get("usage_missing")]
        voided_att = sum(1 for _, _, at in atts if at.get("void"))
        starts = collections.Counter((k > 1, at.get("start_workspace")) for _, k, at in atts)
        # attempt >1 的接受率（冷啟動後）
        later = [(c, at) for c, k, at in atts if k > 1]
        later_acc = sum(1 for _, at in later if (at.get("acc") or {}).get("accept"))
        later_timed = sum(1 for _, at in later if at.get("timed_out"))
        diag[ar] = {
            "cells": len(cs), "success_serial": len(okc), "cell_voids_field_sum": sum(int(c.get("voids") or 0) for c in cs),
            "attempts": len(atts), "attempts_timed_out": timed, "attempts_timed_out_frac": round(timed / len(atts), 3) if atts else None,
            "attempt1_n": len(a1), "attempt1_timed_out": a1_timed, "attempt1_accept": a1_acc,
            "later_attempts": len(later), "later_timed_out": later_timed, "later_accept": later_acc,
            "delivered_attempt_of_successes": dict(sorted((str(k), v) for k, v in deliv.items())),
            "accepted_cells": len(acc_cells), "accepted_but_hidden_fail": len(acc_hidden_fail), "accepted_but_hidden_fail_cells": acc_hidden_fail,
            "attempts_with_void_marker": voided_att,
            "nontimeout_attempt_wall_s_median": round(statistics.median(free_w), 1) if free_w else None,
            "successful_nontimeout_attempt_wall_s": {"n": len(succ_attempt_w), "median": round(statistics.median(succ_attempt_w), 1) if succ_attempt_w else None,
                                                     "max": max(succ_attempt_w) if succ_attempt_w else None,
                                                     "over_600s": sum(1 for w in succ_attempt_w if w > 600)},
            "usage_present_attempts": len(tok_in), "tokens_in_out_median_per_usage_attempt": round(statistics.median(tok_in)) if tok_in else None,
            "start_workspace_counts": {f"later={k[0]},{k[1]}": v for k, v in starts.items()},
            "cell_wall_s_mean": round(statistics.mean(c["wall_s"] for c in cs), 1) if cs else None,
            "cells_hitting_cap": sum(1 for c in cs if c["wall_s"] >= 1799),
        }
    # A 在 600 秒內：A 單次嘗試 agent_wall≤600 且通過的格，對照重做臂第一次嘗試
    a_cells = [c for c in cells if c["arm"] == "A" and not c.get("infra_void")]
    diag["A_pass_within_600s"] = {"A_cells": len(a_cells), "A_success": sum(ok(c) for c in a_cells),
                                  "A_success_agent_wall_le_600": sum(1 for c in a_cells if ok(c) and (c.get("agent_wall_s") or c["wall_s"]) <= 600),
                                  "A_success_agent_wall_gt_600": sum(1 for c in a_cells if ok(c) and (c.get("agent_wall_s") or c["wall_s"]) > 600),
                                  "A_success_agent_walls": sorted(round(c.get("agent_wall_s") or c["wall_s"]) for c in a_cells if ok(c))}
    # 逐題（成功格數／重複）
    tasks = sorted({c["task"] for c in cells})
    res["per_task_success"] = {t: {ar: sum(ok(by[(t, r, ar)]) for r in sorted({k[1] for k in by}) if (t, r, ar) in by) for ar in ARMS} for t in tasks}
    # agent.log 中的限流／錯誤字樣，按臂
    pats = ["rate limit", "Agent error", "resource_exhausted", "Not logged in"]
    logcnt = {ar: collections.Counter() for ar in ARMS}
    for c in cells:
        for p in c["_dir"].glob("attempt_*/agent.log"):
            try:
                txt = p.read_text(errors="replace").lower()
            except OSError:
                continue
            for pt in pats:
                if pt.lower() in txt:
                    logcnt[c["arm"]][pt] += 1
    diag["agent_log_error_strings_by_arm"] = {ar: dict(v) for ar, v in logcnt.items()}
    res["diagnostics"] = diag
    out.mkdir(parents=True, exist_ok=True)
    (out / f"FOLLOWUP_{a.label}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps(res, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
