#!/usr/bin/env python3
"""驗收訊號的增益 vs 選擇的效果：五批四臂資料的事後拆解（非預註冊；稽核用）。

這支在架構裡承重的是「重開臂的成功，有多少來自『用可見測試決定停不停、交哪一版』，
有多少只是『多抽幾次』或『單次時間比較短』」。只讀已存資料，不呼叫任何模型：

- 本機三批（ctl12_q9、ctl12_colab_e4b、ctl34_g12）：稽核包第二版
  `ops/redo/audit/ctl_20261128/<batch>_cells.json`（預設 `git show edf6d323f:`；或 `--audit-dir`）。
  每次嘗試有 acc_passed／acc_total／acc_status（可見那一半）與 hidden_pass（隱藏那一半）。
  逐次嘗試沒有 `accept` 布林欄位，用 `acc_status=="ok" and acc_total>0 and acc_passed==acc_total` 推（和交付版 558 格逐一對得上）。
- 雲端兩批（Haiku×cchard、Devin×cchard16 只取 r1–r2）：run root 的 `cells/*/r*/*/cell.json`
  （`--runs-dir`，預設 `/opt/ctlwork/runs`；每次嘗試有 accept／acc_passed／grade_pass）。
  正式分數是交付版的序列重評分；兩批的 README 都寫與批次內分數不同的格為 0，所以逐次嘗試用批次內的 grade_pass。

輸出：每批 (1) R／B／C 第 1 次 vs 最終的配對比較；(2) 成功來自第幾次、逐次誤收／誤擋；
(3) A、第 1 次、最終三個參考點，以及用三臂各自的第 1 次（互相獨立、無條件）離線模擬
「三次獨立嘗試：取第 1 次／隨機取一份／依可見測試取第一個過的／任一過（上限）」；
(4) 牆鐘與 token；(5) 候選設計的檢定力模擬（以題為單位重抽）。
只用標準函式庫。
"""
from __future__ import annotations

import argparse
import glob
import itertools
import json
import math
import os
import pathlib
import random
import subprocess
import sys
from collections import defaultdict

AUDIT_REV = "edf6d323f"
AUDIT_REL = "ops/redo/audit/ctl_20261128"
LOCAL = ["ctl12_q9", "ctl12_colab_e4b", "ctl34_g12"]
CLOUD = {"haiku_cchard": ("ctl_haiku_cchard_4arm", None), "devin_cchard16": ("ctl_devin_flash_cchard16_4arm", {1, 2})}
SEED = 20261128
BOOT_N = 10000
Z = 1.959963984540054


# ── 讀檔、正規化 ──────────────────────────────────────────────────────────

def norm_local(c: dict) -> dict:
    atts = []
    for a in c["attempts"]:
        acc = a["acc_status"] == "ok" and (a["acc_total"] or 0) > 0 and a["acc_passed"] == a["acc_total"]
        tok = None if a["tokens_in"] is None and a["tokens_out"] is None else (a["tokens_in"] or 0) + (a["tokens_out"] or 0)
        atts.append({"accept": acc, "acc_passed": a["acc_passed"] or 0, "hidden": bool(a["hidden_pass"]),
                     "timed_out": bool(a["timed_out"]), "wall_s": a["wall_s"], "tokens": tok})
    return {"task": c["task"], "rep": c["rep"], "arm": c["arm"], "host": c["host"], "void": bool(c["infra_void"]),
            "final": bool(c["hidden_pass"]) if not c["infra_void"] else None, "delivered": c["delivered_attempt"],
            "accepted": c["accepted"], "wall_s": c["wall_s"], "attempts": atts}


def norm_cloud(c: dict) -> dict:
    atts = []
    for a in c.get("attempts") or []:
        u = a.get("usage")
        tok = None
        if isinstance(u, dict) and (u.get("input") is not None or u.get("output") is not None):
            tok = (u.get("input") or 0) + (u.get("output") or 0)
        atts.append({"accept": bool(a["accept"]), "acc_passed": a.get("acc_passed") or 0, "hidden": bool(a.get("grade_pass")),
                     "timed_out": bool(a.get("timed_out")), "wall_s": a.get("wall_s"), "tokens": tok})
    return {"task": c["task"], "rep": c["rep"], "arm": c["arm"], "host": c.get("provider"), "void": bool(c.get("infra_void")),
            "final": bool(c.get("pass")) if not c.get("infra_void") else None, "delivered": c.get("delivered_attempt"),
            "accepted": c.get("accepted"), "wall_s": c.get("wall_s"), "attempts": atts}


def load_local(b, audit_dir, rev):
    rel = f"{b}_cells.json"
    if audit_dir:
        txt = (pathlib.Path(audit_dir) / rel).read_text(encoding="utf-8")
    else:
        txt = subprocess.run(["git", "show", f"{rev}:{AUDIT_REL}/{rel}"], capture_output=True, text=True, check=True).stdout
    return [norm_local(c) for c in json.loads(txt)]


def load_cloud(root: pathlib.Path, reps):
    run = json.loads((root / "RUN.json").read_text())
    out = []
    for p in sorted(glob.glob(str(root / "cells/*/r*/*/cell.json"))):
        c = json.loads(pathlib.Path(p).read_text())
        if c.get("plan_sha256") != run["plan_sha256"]:
            continue
        if reps is not None and c["rep"] not in reps:
            continue
        out.append(norm_cloud(c))
    return out, run["plan_sha256"]


# ── 統計原語 ──────────────────────────────────────────────────────────────

def binom2(b, c):
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def signflip(vals):
    vals = [v for v in vals if v != 0]
    if not vals:
        return 1.0
    dist = {0: 1}
    for v in vals:
        nd = defaultdict(int)
        for s, w in dist.items():
            nd[s + v] += w
            nd[s - v] += w
        dist = nd
    obs = abs(sum(vals))
    return min(1.0, sum(w for s, w in dist.items() if abs(s) >= obs) / 2 ** len(vals))


def wilson(x, n):
    if n == 0:
        return (0.0, 1.0)
    p = x / n
    den = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / den
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def newcombe(a, b, c, d):
    """θ = p1 − p2；a 兩者都過、b 只有 1 過、c 只有 2 過、d 都沒過（Newcombe 1998 方法 10）。"""
    n = a + b + c + d
    p1, p2 = (a + b) / n, (a + c) / n
    l1, u1 = wilson(a + b, n)
    l2, u2 = wilson(a + c, n)
    num = a * d - b * c
    if num > 0:
        num = max(num - n / 2, 0.0)
    den = math.sqrt((a + b) * (c + d) * (a + c) * (b + d))
    phi = num / den if den > 0 else 0.0
    t = p1 - p2
    dl = math.sqrt(max(0.0, (p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2))
    du = math.sqrt(max(0.0, (u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2))
    return t, t - dl, t + du


def pct(xs, q):
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    f = math.floor(k)
    cc = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[cc] - xs[f]) * (k - f)


def cluster_boot(strata, rng, n=BOOT_N):
    """strata：每層（批）一個 list，元素為 (該題的差之和, 該題的配對數)；層內對題重抽，統計量＝Σ差/Σ對數。"""
    reps = []
    for _ in range(n):
        num = den = 0.0
        for st in strata:
            k = len(st)
            for _j in range(k):
                s, m = st[rng.randrange(k)]
                num += s
                den += m
        reps.append(num / den if den else 0.0)
    return pct(reps, 0.025), pct(reps, 0.975)


def paired_binary(pairs_by_task: dict, rng) -> dict:
    """pairs_by_task：題 → [(x, y)]（x＝處理、y＝對照，布林）。報 McNemar、Newcombe、題群集置換與 bootstrap。"""
    a = b = c = d = 0
    strata = []
    for t, prs in pairs_by_task.items():
        s = 0
        for x, y in prs:
            if x and y:
                a += 1
            elif x:
                b += 1
            elif y:
                c += 1
            else:
                d += 1
            s += int(x) - int(y)
        if prs:
            strata.append((s, len(prs)))
    n = a + b + c + d
    if n == 0:
        return {"pairs": 0}
    t, lo, hi = newcombe(a, b, c, d)
    blo, bhi = cluster_boot([strata], rng)
    return {"pairs": n, "treat_pass": a + b, "ctrl_pass": a + c, "treat_only": b, "ctrl_only": c,
            "delta_pp": round(100 * t, 1), "mcnemar_p": round(binom2(b, c), 6),
            "newcombe95_pp": [round(100 * lo, 1), round(100 * hi, 1)],
            "cluster_signflip_p": round(signflip([s for s, _ in strata]), 6),
            "cluster_boot95_pp": [round(100 * blo, 1), round(100 * bhi, 1)],
            "tasks_with_discordance": sum(1 for s, _ in strata if s != 0), "_strata": strata}


# ── 1. 第 1 次 vs 最終 ────────────────────────────────────────────────────

def first_vs_final(cells, arm, rng):
    by = defaultdict(list)
    for c in cells:
        if c["arm"] == arm and not c["void"] and c["attempts"]:
            by[c["task"]].append((c["final"], c["attempts"][0]["hidden"]))
    return paired_binary(by, rng)


# ── 2. 成功來自第幾次、誤收／誤擋 ─────────────────────────────────────────

def success_sources(cells, arm):
    sc = [c for c in cells if c["arm"] == arm and not c["void"]]
    src = defaultdict(int)
    lost = 0  # 第 1 次隱藏已過、最終交付卻沒過
    for c in sc:
        if c["final"]:
            src[c["delivered"]] += 1
        if c["attempts"] and c["attempts"][0]["hidden"] and not c["final"]:
            lost += 1
    per_k = {}
    for k in range(1, 4):
        at = [c["attempts"][k - 1] for c in sc if len(c["attempts"]) >= k]
        if not at:
            continue
        acc = [x for x in at if x["accept"]]
        rej = [x for x in at if not x["accept"]]
        per_k[str(k)] = {
            "attempts": len(at), "accepted": len(acc), "hidden_pass": sum(x["hidden"] for x in at),
            "false_accept": sum(1 for x in acc if not x["hidden"]),
            "false_accept_rate_given_accepted": round(sum(1 for x in acc if not x["hidden"]) / len(acc), 3) if acc else None,
            "false_reject": sum(1 for x in rej if x["hidden"]),
            "false_reject_rate_given_rejected": round(sum(1 for x in rej if x["hidden"]) / len(rej), 3) if rej else None,
            "timed_out": sum(x["timed_out"] for x in at),
        }
    return {"cells": len(sc), "successes": sum(1 for c in sc if c["final"]),
            "success_by_delivered_attempt": {str(k): v for k, v in sorted(src.items())},
            "first_attempt_hidden_pass_but_final_fail": lost, "per_attempt": per_k}


# ── 3. 參考點、獨立性檢查、離線三抽一 ─────────────────────────────────────

def deliver_rule(atts):
    """harness 的交付規則：第一個可見全過的；都沒過交可見通過數最多（同分取最後）。"""
    for x in atts:
        if x["accept"]:
            return x
    return max(enumerate(atts), key=lambda ix: (ix[1]["acc_passed"], ix[0]))[1]


def triples(cells):
    """每個 (題, 重複)：R、B、C 三臂各自的第 1 次嘗試（提示相同、工作區相同、彼此不以對方為條件）。"""
    idx = {(c["task"], c["rep"], c["arm"]): c for c in cells}
    out = defaultdict(list)
    for (t, r, arm), c in idx.items():
        if arm != "R":
            continue
        trio = [idx.get((t, r, a)) for a in ("R", "B", "C")]
        if any(x is None or x["void"] or not x["attempts"] for x in trio):
            continue
        out[t].append([x["attempts"][0] for x in trio])
    return out


def offline_selection(trip_by_task, rng):
    """把三臂的第 1 次當成同一題同一重複的三次獨立嘗試，離線套四種取法；取法對 6 種順序平均。"""
    rows = []
    for t, lst in trip_by_task.items():
        for tri in lst:
            perms = list(itertools.permutations(tri))
            sel = sum(deliver_rule(list(p))["hidden"] for p in perms) / len(perms)
            rows.append({"task": t, "first_fixed": tri[0]["hidden"], "sel_fixed": deliver_rule(tri)["hidden"],
                         "random": sum(x["hidden"] for x in tri) / 3, "select_avg": sel,
                         "oracle": any(x["hidden"] for x in tri), "any_accept": any(x["accept"] for x in tri)})
    n = len(rows)
    if not n:
        return {}
    by = defaultdict(list)
    for r_ in rows:
        by[r_["task"]].append((r_["sel_fixed"], r_["first_fixed"]))
    pb = paired_binary(by, rng)
    # 依可見測試取 − 隨機取一份（順序平均；以 1/6 為單位變整數做題群集置換）
    diffs_by_task = defaultdict(list)
    for r_ in rows:
        diffs_by_task[r_["task"]].append(round(6 * (r_["select_avg"] - r_["random"])))
    strata = [(sum(v) / 6, len(v)) for v in diffs_by_task.values()]
    blo, bhi = cluster_boot([strata], rng)
    pb.pop("_strata", None)
    return {"triples": n, "tasks": len(by),
            "rate_random_pick": round(sum(r_["random"] for r_ in rows) / n, 4),
            "rate_select_by_visible_avg_order": round(sum(r_["select_avg"] for r_ in rows) / n, 4),
            "rate_oracle_any_hidden": round(sum(r_["oracle"] for r_ in rows) / n, 4),
            "triples_with_any_accept": sum(r_["any_accept"] for r_ in rows),
            "select_minus_random_pp": round(100 * sum(r_["select_avg"] - r_["random"] for r_ in rows) / n, 1),
            "select_minus_random_cluster_signflip_p": round(signflip([sum(v) for v in diffs_by_task.values()]), 6),
            "select_minus_random_cluster_boot95_pp": [round(100 * blo, 1), round(100 * bhi, 1)],
            "fixed_order_select_vs_first(R1,B1,C1)": pb,
            "_strata_sel_minus_random": strata}


def independence_checks(cells):
    """(a) 同一 (題,重複)，R1 過／沒過時 B1、C1 的通過率（題的難度造成的相關）；
    (b) R 第 2 次的隱藏通過率（以 R1 可見沒過為條件）vs 同條件下 B1、C1 的通過率（同一條件、無重開）
        vs 無條件的第 1 次通過率——條件化讓題目變難多少、重開本身是否像一次新的獨立抽樣。"""
    idx = {(c["task"], c["rep"], c["arm"]): c for c in cells}
    res = {}
    agree = {"r1_pass": [0, 0], "r1_fail": [0, 0]}
    cond = {"R2_hidden": [0, 0], "B1C1_hidden_same_condition": [0, 0], "R3_hidden": [0, 0], "B1C1_hidden_cond_R1R2_fail": [0, 0]}
    first_all = [0, 0]
    for (t, r, arm), c in idx.items():
        if c["void"] or not c["attempts"]:
            continue
        if arm in ("R", "B", "C"):
            first_all[0] += c["attempts"][0]["hidden"]
            first_all[1] += 1
        if arm != "R":
            continue
        r1 = c["attempts"][0]
        others = [idx.get((t, r, a)) for a in ("B", "C")]
        others = [o["attempts"][0]["hidden"] for o in others if o and not o["void"] and o["attempts"]]
        k = "r1_pass" if r1["hidden"] else "r1_fail"
        agree[k][0] += sum(others)
        agree[k][1] += len(others)
        if not r1["accept"] and len(c["attempts"]) >= 2:
            cond["R2_hidden"][0] += c["attempts"][1]["hidden"]
            cond["R2_hidden"][1] += 1
            cond["B1C1_hidden_same_condition"][0] += sum(others)
            cond["B1C1_hidden_same_condition"][1] += len(others)
            if not c["attempts"][1]["accept"] and len(c["attempts"]) >= 3:
                cond["R3_hidden"][0] += c["attempts"][2]["hidden"]
                cond["R3_hidden"][1] += 1
                cond["B1C1_hidden_cond_R1R2_fail"][0] += sum(others)
                cond["B1C1_hidden_cond_R1R2_fail"][1] += len(others)

    def fr(x):
        return {"pass": x[0], "n": x[1], "rate": round(x[0] / x[1], 3) if x[1] else None}
    res["first_attempt_unconditional_RBC"] = fr(first_all)
    res["B1C1_given_R1_hidden_pass"] = fr(agree["r1_pass"])
    res["B1C1_given_R1_hidden_fail"] = fr(agree["r1_fail"])
    res.update({k: fr(v) for k, v in cond.items()})
    res["icc_first_attempts_by_task"] = icc_binary(cells)
    return res


def icc_binary(cells):
    """單因子 ANOVA 的 ICC(1)：R、B、C 第 1 次嘗試的隱藏結果，以題為群組。"""
    g = defaultdict(list)
    for c in cells:
        if c["arm"] in ("R", "B", "C") and not c["void"] and c["attempts"]:
            g[c["task"]].append(int(c["attempts"][0]["hidden"]))
    groups = [v for v in g.values() if len(v) > 1]
    N = sum(len(v) for v in groups)
    k = len(groups)
    if k < 2:
        return None
    mean = sum(sum(v) for v in groups) / N
    ssb = sum(len(v) * (sum(v) / len(v) - mean) ** 2 for v in groups)
    ssw = sum(sum((x - sum(v) / len(v)) ** 2 for x in v) for v in groups)
    msb, msw = ssb / (k - 1), ssw / (N - k)
    n0 = (N - sum(len(v) ** 2 for v in groups) / N) / (k - 1)
    den = msb + (n0 - 1) * msw
    return round((msb - msw) / den, 3) if den > 0 else None


# ── 4. 花費 ──────────────────────────────────────────────────────────────

def cost(cells, arm_x, arm_y="A"):
    idx = {(c["task"], c["rep"], c["arm"]): c for c in cells}
    wall, tok, tok_missing = [], [], 0
    for (t, r, a), x in idx.items():
        if a != arm_x:
            continue
        y = idx.get((t, r, arm_y))
        if y is None or x["void"] or y["void"]:
            continue
        wx = sum(at["wall_s"] or 0 for at in x["attempts"])
        wy = sum(at["wall_s"] or 0 for at in y["attempts"])
        wall.append(wx - wy)
        tx = [at["tokens"] for at in x["attempts"]]
        ty = [at["tokens"] for at in y["attempts"]]
        if None in tx or None in ty:
            tok_missing += 1
        else:
            tok.append(sum(tx) - sum(ty))
    out = {"pairs": len(wall)}
    if wall:
        s = sorted(wall)
        out["agent_wall_diff_s"] = {"mean": round(sum(wall) / len(wall), 1), "median": s[len(s) // 2],
                                    "pairs_more": sum(1 for v in wall if v > 0), "pairs_less": sum(1 for v in wall if v < 0)}
    if tok:
        s = sorted(tok)
        out["tokens_diff"] = {"pairs_with_full_usage": len(tok), "mean": round(sum(tok) / len(tok)), "median": s[len(s) // 2],
                              "pairs_more": sum(1 for v in tok if v > 0), "pairs_less": sum(1 for v in tok if v < 0)}
    out["pairs_missing_usage"] = tok_missing
    return out


def arm_means(cells):
    out = {}
    for arm in ("A", "R", "B", "C"):
        sc = [c for c in cells if c["arm"] == arm and not c["void"]]
        if not sc:
            continue
        w = [sum(at["wall_s"] or 0 for at in c["attempts"]) for c in sc]
        toks = [sum(at["tokens"] for at in c["attempts"]) for c in sc if all(at["tokens"] is not None for at in c["attempts"])]
        first_w = [c["attempts"][0]["wall_s"] or 0 for c in sc if c["attempts"]]
        out[arm] = {"cells": len(sc), "success": sum(1 for c in sc if c["final"]),
                    "first_attempt_success": sum(1 for c in sc if c["attempts"] and c["attempts"][0]["hidden"]),
                    "mean_agent_wall_s": round(sum(w) / len(w), 1), "mean_first_attempt_wall_s": round(sum(first_w) / len(first_w), 1),
                    "mean_attempts": round(sum(len(c["attempts"]) for c in sc) / len(sc), 3),
                    "mean_tokens_cells_with_full_usage": round(sum(toks) / len(toks)) if toks else None,
                    "cells_with_full_usage": len(toks)}
    return out


# ── 5. 檢定力模擬 ────────────────────────────────────────────────────────

def power_sim(trip_by_task, T, K, rng, n_sim=2000):
    """候選設計：T 題 × K 重複 × 每格 3 次獨立 600 秒嘗試。每次模擬：題以放回方式從來源批重抽；
    每個重複從該題的『第 1 次嘗試池』（三臂 × 各重複）不放回抽 3 次。
    主比較：依可見測試取第一個過的 vs 取第 1 次（(題,重複) 配對）；
    報兩種檢定在 α=0.05（雙尾）下的拒絕率：精確 McNemar、以題為群集的符號翻轉置換。"""
    pools = {t: [a for tri in lst for a in tri] for t, lst in trip_by_task.items()}
    pools = {t: v for t, v in pools.items() if len(v) >= 3}
    tasks = list(pools)
    if not tasks:
        return None
    rej_mc = rej_cl = rej_cl_rand = 0
    eff = []
    for _ in range(n_sim):
        b = c = 0
        sums = []
        sums_rand = []
        tot = 0
        for _t in range(T):
            pool = pools[tasks[rng.randrange(len(tasks))]]
            s = 0
            sr = 0
            for _k in range(K):
                tri = rng.sample(pool, 3)
                sel = deliver_rule(tri)["hidden"]
                fst = tri[0]["hidden"]
                if sel and not fst:
                    b += 1
                elif fst and not sel:
                    c += 1
                s += int(sel) - int(fst)
                sr += 3 * int(sel) - sum(x["hidden"] for x in tri)
                tot += int(sel) - int(fst)
            sums.append(s)
            sums_rand.append(sr)
        eff.append(tot / (T * K))
        rej_mc += binom2(b, c) < 0.05
        rej_cl += signflip(sums) < 0.05
        rej_cl_rand += signflip(sums_rand) < 0.05
    return {"T": T, "K": K, "n_sim": n_sim, "mean_effect_pp": round(100 * sum(eff) / n_sim, 1),
            "power_mcnemar": round(rej_mc / n_sim, 3), "power_cluster_signflip": round(rej_cl / n_sim, 3),
            "power_cluster_signflip_vs_mean_of_three": round(rej_cl_rand / n_sim, 3)}


# ── 主程式 ────────────────────────────────────────────────────────────────

def analyse_batch(name, cells, rng, src):
    R = {"source": src, "cells": len(cells), "voids": sum(1 for c in cells if c["void"])}
    R["first_vs_final"] = {}
    for arm in ("R", "B", "C"):
        R["first_vs_final"][arm] = first_vs_final(cells, arm, rng)
    R["success_sources"] = {arm: success_sources(cells, arm) for arm in ("A", "R", "B", "C")}
    R["arm_means"] = arm_means(cells)
    idx = {(c["task"], c["rep"], c["arm"]): c for c in cells}
    # 參考點配對：R 最終 vs A、R 第 1 次 vs A
    for lab, f in (("R_final_vs_A", lambda c: c["final"]), ("R_first_vs_A", lambda c: c["attempts"][0]["hidden"])):
        by = defaultdict(list)
        for (t, r, a), x in idx.items():
            y = idx.get((t, r, "A"))
            if a == "R" and y and not x["void"] and not y["void"] and x["attempts"]:
                by[t].append((f(x), y["final"]))
        p = paired_binary(by, rng)
        p.pop("_strata", None)
        R[lab] = p
    trip = triples(cells)
    R["offline_three_independent_first_attempts"] = offline_selection(trip, rng)
    R["independence"] = independence_checks(cells)
    R["cost_vs_A"] = {arm: cost(cells, arm) for arm in ("R", "B", "C")}
    return R, trip


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-dir")
    ap.add_argument("--rev", default=AUDIT_REV)
    ap.add_argument("--runs-dir", default="/opt/ctlwork/runs")
    ap.add_argument("--out")
    ap.add_argument("--power-sims", type=int, default=2000)
    a = ap.parse_args()
    rng = random.Random(SEED)
    res = {"schema": "vacant.redo.acceptance_signal_offline/1", "post_hoc": True,
           "local_audit_rev": a.rev if not a.audit_dir else None, "seed": SEED, "batches": {}}
    trips = {}
    data = {}
    for b in LOCAL:
        data[b] = (load_local(b, a.audit_dir, a.rev), f"audit {a.rev}:{AUDIT_REL}/{b}_cells.json")
    for name, (root, reps) in CLOUD.items():
        p = pathlib.Path(a.runs_dir) / root
        if p.is_dir():
            cells, sha = load_cloud(p, reps)
            data[name] = (cells, f"run root {root} (plan {sha[:12]}" + (f", reps {sorted(reps)})" if reps else ")"))
    for name, (cells, src) in data.items():
        R, trip = analyse_batch(name, cells, rng, src)
        trips[name] = trip
        res["batches"][name] = R
    # 分層合併（每批一層、層內對題重抽；配對加權）
    pooled = {}
    groups = {"local3": LOCAL, "all5": list(data), "local_distinguishable2": ["ctl12_colab_e4b", "ctl34_g12"]}
    for gname, members in groups.items():
        members = [m for m in members if m in res["batches"]]
        for arm in ("R", "B", "C"):
            strata = [res["batches"][m]["first_vs_final"][arm]["_strata"] for m in members]
            num = sum(s for st in strata for s, _ in st)
            den = sum(n for st in strata for _, n in st)
            lo, hi = cluster_boot(strata, rng)
            pooled[f"{gname}:{arm}_final_minus_first"] = {
                "batches": members, "pairs": den, "delta_pp": round(100 * num / den, 1),
                "cluster_boot95_pp": [round(100 * lo, 1), round(100 * hi, 1)],
                "cluster_signflip_p_all_tasks": round(signflip([s for st in strata for s, _ in st]), 6)}
        strata = [res["batches"][m]["offline_three_independent_first_attempts"]["_strata_sel_minus_random"] for m in members]
        num = sum(s for st in strata for s, _ in st)
        den = sum(n for st in strata for _, n in st)
        lo, hi = cluster_boot(strata, rng)
        pooled[f"{gname}:offline_select_minus_random"] = {"batches": members, "triples": den, "delta_pp": round(100 * num / den, 1),
                                                         "cluster_boot95_pp": [round(100 * lo, 1), round(100 * hi, 1)]}
    res["pooled"] = pooled
    for R in res["batches"].values():
        for arm in ("R", "B", "C"):
            R["first_vs_final"][arm].pop("_strata", None)
        R["offline_three_independent_first_attempts"].pop("_strata_sel_minus_random", None)
    # 檢定力：以 ctl34（12B）與 ctl12_q9（9B）的第 1 次嘗試池為母體
    power = {}
    for src in ("ctl34_g12", "ctl12_q9", "ctl12_colab_e4b"):
        for T, K in ((34, 2), (34, 3), (34, 6), (40, 3), (48, 3), (48, 4), (60, 3)):
            power[f"{src}:T{T}xK{K}"] = power_sim(trips[src], T, K, rng, a.power_sims)
    res["power_candidate_design"] = power
    txt = json.dumps(res, ensure_ascii=False, indent=1)
    if a.out:
        pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(a.out).write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    sys.exit(main())
