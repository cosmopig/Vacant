#!/usr/bin/env python3
"""證據式決策控制器三批結論的獨立重算（稽核用；不 import ctl_metrics.py）。

這支在架構裡承重的是「結論檔的每個數字能不能只靠稽核包的逐格表重建」：
讀 `ops/redo/audit/ctl_20261128/` 的 `<batch>_cells.json` 與 `<batch>_controller_events.jsonl`
（預設從提交 8cd6cf1b 用 `git show` 讀，或用 `--dir` 指定一個已展開的目錄），自己重算：

  1. 各臂隱藏評分成功數；C 對 B、C 對 R（與 R/B/C 對 A）的配對比較：
     (a) (題, 重複) 配對的精確 McNemar（雙尾二項）；
     (b) 以題為群集：題內差之和的精確符號翻轉置換檢定（主）、題層級符號檢定、
         題層級 Wilcoxon 符號秩精確檢定（中位秩，DP 枚舉）；
  2. 修正 5 的三個無法區分條件；
  3. 成功率差的 95% 區間：Newcombe 1998 方法 10（配對、Wilson 為底；忽略題內相關）、
     以題為群集的 bootstrap（百分位；固定種子），以及三批／兩批的分層合併；
  4. ctl34 C 臂缺的兩格的敏感度（算失敗／算成功／丟掉配對）；
  5. 決策事件：每條規則次數、依決策文件的順序與門檻從 evidence 重推規則、
     與逐格表的規則欄位對帳、交付版是否等於「第一個驗收通過、否則驗收最多（同分取最新）」；
     修復／續做／重開之後下一次嘗試的驗收通過率變化；C 臂 broken-after-pass 由事件裡的逐測試結果重算；
  6. 逾時與成功率分臂、分主機、分 harness 雜湊。

只用標準函式庫。用法：
    python3 ops/redo/analysis/ctl_audit_recompute.py [--dir DIR | --rev 8cd6cf1b] [--out PATH]
誠實邊界：逐格表是匯出物，不是原始 cell.json；這支驗的是「結論 ↔ 逐格表」一致，
不驗「逐格表 ↔ 原始執行紀錄」一致（鏈檔、attempt.json 不在稽核包裡）。
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import random
import subprocess
import sys
from collections import Counter, defaultdict

REV_DEFAULT = "8cd6cf1ba553e7cd64b44d3657f0ba3524beafef"
AUDIT_REL = "ops/redo/audit/ctl_20261128"
BATCHES = ["ctl12_q9", "ctl12_colab_e4b", "ctl34_g12"]
ARMS = ["A", "R", "B", "C"]
BOOT_N = 20000
BOOT_SEED = 20261128

# 結論檔（8cd6cf1b 的 CONCLUSION_20261128_EVIDENCE_CONTROLLER.md）裡的頭條數字，拿來逐一對照
CLAIMED = {
    "ctl12_q9": {"A": (19, 36), "R": (26, 36), "B": (26, 36), "C": (26, 36),
                 "rules": {1: 31, 2: 5, 3: 1, 4: 3, 5: 0, 6: 7}, "cond2": (20, 108), "cond3": 11},
    "ctl34_g12": {"A": (23, 68), "R": (33, 68), "B": (31, 68), "C": (32, 66),
                  "C_vs_B": {"treat": 32, "ctrl": 30, "delta_pp": 3.0, "p": 0.63},
                  "C_vs_R": {"treat": 32, "ctrl": 32},
                  "rules": {1: 47, 2: 19, 3: 6, 4: 11, 5: 15, 6: 29}, "cond1_pct": 34, "cond2_pct": 50.5, "cond3": 61},
    "ctl12_colab_e4b": {"A": (6, 36), "R": (10, 36), "B": (9, 36), "C": (10, 36),
                        "C_vs_B": {"treat": 10, "ctrl": 9, "delta_pp": 2.8, "p": 1.0},
                        "C_vs_R": {"treat": 10, "ctrl": 10},
                        "rules": {1: 20, 2: 16, 3: 1, 4: 10, 5: 3, 6: 33}, "cond1_pct": 17, "cond2_pct": 67, "cond3": 47},
}


# ── 讀檔 ──────────────────────────────────────────────────────────────────

def read_text(rel: str, src_dir: pathlib.Path | None, rev: str) -> str:
    if src_dir is not None:
        return (src_dir / rel).read_text(encoding="utf-8")
    r = subprocess.run(["git", "show", f"{rev}:{AUDIT_REL}/{rel}"], capture_output=True, text=True, check=True)
    return r.stdout


def load_batch(b: str, src_dir, rev):
    cells = json.loads(read_text(f"{b}_cells.json", src_dir, rev))
    events = [json.loads(l) for l in read_text(f"{b}_controller_events.jsonl", src_dir, rev).splitlines() if l.strip()]
    indist = json.loads(read_text(f"{b}_indistinguishability.json", src_dir, rev))
    tt = json.loads(read_text(f"{b}_token_timeout_by_arm_host.json", src_dir, rev))
    return cells, events, indist, tt


# ── 統計原語 ──────────────────────────────────────────────────────────────

def binom_two_sided(b: int, c: int) -> float:
    """精確 McNemar／符號檢定：n=b+c、p=0.5 的雙尾二項（2×較小尾，上限 1）。"""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / 2.0 ** n)


def signflip_exact(vals: list[int]) -> float:
    """整數值的精確符號翻轉置換檢定（Fisher–Pitman 配對），雙尾：P(|S| >= |s_obs|)。DP 枚舉 2^n。"""
    vals = [v for v in vals if v != 0]
    n = len(vals)
    if n == 0:
        return 1.0
    dist = {0: 1}
    for v in vals:
        nd: dict[int, int] = defaultdict(int)
        for s, w in dist.items():
            nd[s + v] += w
            nd[s - v] += w
        dist = nd
    obs = abs(sum(vals))
    tot = 2 ** n
    return min(1.0, sum(w for s, w in dist.items() if abs(s) >= obs) / tot)


def wilcoxon_exact(diffs: list[float]) -> dict:
    """Wilcoxon 符號秩精確檢定：丟掉 0、中位秩；用「兩倍秩」變整數後 DP 枚舉。雙尾 P(|W+ − E| >= |obs − E|)。"""
    d = [x for x in diffs if abs(x) > 1e-12]
    n = len(d)
    if n == 0:
        return {"n_nonzero": 0, "W_plus": None, "p": 1.0}
    absd = sorted((round(abs(x), 9), i) for i, x in enumerate(d))
    ranks2 = [0] * n  # 兩倍中位秩（整數）
    i = 0
    while i < n:
        j = i
        while j + 1 < n and absd[j + 1][0] == absd[i][0]:
            j += 1
        r2 = (i + 1) + (j + 1)  # 2 × 平均秩
        for k in range(i, j + 1):
            ranks2[absd[k][1]] = r2
        i = j + 1
    wplus2 = sum(r for r, x in zip(ranks2, d) if x > 0)
    dist = {0: 1}
    for r in ranks2:
        nd: dict[int, int] = defaultdict(int)
        for s, w in dist.items():
            nd[s] += w
            nd[s + r] += w
        dist = nd
    E2 = sum(ranks2) / 2.0
    obs = abs(wplus2 - E2)
    p = sum(w for s, w in dist.items() if abs(s - E2) >= obs - 1e-9) / 2 ** n
    return {"n_nonzero": n, "W_plus": wplus2 / 2.0, "p": min(1.0, p)}


def wilson(x: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = x / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def newcombe_paired(a: int, b: int, c: int, d: int) -> tuple[float, float, float]:
    """Newcombe (1998) 方法 10：配對比例差 θ = p1 − p2 的區間。
    a＝兩者皆成功、b＝只有處理成功、c＝只有對照成功、d＝皆失敗；p1＝處理、p2＝對照。
    φ 用 Newcombe 的連續性修正（ad > bc 時用 max(ad − bc − n/2, 0)）。"""
    n = a + b + c + d
    p1, p2 = (a + b) / n, (a + c) / n
    l1, u1 = wilson(a + b, n)
    l2, u2 = wilson(a + c, n)
    num = a * d - b * c
    if num > 0:
        num = max(num - n / 2.0, 0.0)
    den = math.sqrt((a + b) * (c + d) * (a + c) * (b + d))
    phi = num / den if den > 0 else 0.0
    theta = p1 - p2
    dl = math.sqrt(max(0.0, (p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2))
    du = math.sqrt(max(0.0, (u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2))
    return (theta, max(-1.0, theta - dl), min(1.0, theta + du))


def pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    f, cfl = math.floor(k), math.ceil(k)
    if f == cfl:
        return xs[int(k)]
    return xs[f] + (xs[cfl] - xs[f]) * (k - f)


def cluster_boot(strata: list[list[tuple[int, int]]], rng: random.Random, n_boot: int = BOOT_N) -> tuple[float, float, float]:
    """分層群集 bootstrap：每層（批）內對題重抽；統計量＝Σ(處理−對照) / Σ配對數（配對加權的合併差）。
    strata：每層一個 list，元素為該題的 (Σ差, 配對數)。"""
    est_num = sum(s for st in strata for s, _ in st)
    est_den = sum(m for st in strata for _, m in st)
    est = est_num / est_den
    reps = []
    for _ in range(n_boot):
        num = den = 0
        for st in strata:
            k = len(st)
            for _j in range(k):
                s, m = st[rng.randrange(k)]
                num += s
                den += m
        reps.append(num / den if den else 0.0)
    return (est, pct(reps, 0.025), pct(reps, 0.975))


# ── 配對比較 ──────────────────────────────────────────────────────────────

def index_cells(cells):
    return {(c["task"], c["rep"], c["arm"]): c for c in cells}


def paired(cells, treat: str, ctrl: str, void_mode: str = "drop", rng: random.Random | None = None) -> dict:
    """void_mode：drop＝任一臂 void 的那一對不計（預註冊規則）；fail／pass＝void 格當失敗／成功。"""
    idx = index_cells(cells)
    tasks = sorted({c["task"] for c in cells})
    reps = sorted({c["rep"] for c in cells})
    a = b = c_ = d = 0
    per_task: dict[str, list[int]] = {}
    dropped = []
    for t in tasks:
        diffs = []
        for r in reps:
            x, y = idx.get((t, r, treat)), idx.get((t, r, ctrl))
            if x is None or y is None:
                dropped.append((t, r, "missing"))
                continue

            def outcome(z):
                if z["infra_void"]:
                    if void_mode == "drop":
                        return None
                    return void_mode == "pass"
                return bool(z["hidden_pass"])
            xo, yo = outcome(x), outcome(y)
            if xo is None or yo is None:
                dropped.append((t, r, "void"))
                continue
            if xo and yo:
                a += 1
            elif xo:
                b += 1
            elif yo:
                c_ += 1
            else:
                d += 1
            diffs.append(int(xo) - int(yo))
        per_task[t] = diffs
    n = a + b + c_ + d
    task_sums = [sum(v) for v in per_task.values() if v]
    task_means = [sum(v) / len(v) for v in per_task.values() if v]
    tpos = sum(1 for s in task_sums if s > 0)
    tneg = sum(1 for s in task_sums if s < 0)
    theta, lo, hi = newcombe_paired(a, b, c_, d)
    out = {
        "treat": treat, "ctrl": ctrl, "void_mode": void_mode, "pairs": n, "dropped": dropped,
        "both": a, "treat_only": b, "ctrl_only": c_, "neither": d,
        "treat_pass": a + b, "ctrl_pass": a + c_,
        "delta_pp": round(100 * (b - c_) / n, 2) if n else None,
        "mcnemar_exact_p": round(binom_two_sided(b, c_), 6),
        "newcombe95_pp": [round(100 * lo, 1), round(100 * hi, 1)],
        "cluster": {
            "n_tasks": len(task_sums),
            "tasks_treat_better": tpos, "tasks_ctrl_better": tneg, "tasks_tied": len(task_sums) - tpos - tneg,
            "signflip_exact_p": round(signflip_exact(task_sums), 6),
            "sign_test_p": round(binom_two_sided(tpos, tneg), 6),
            "wilcoxon_exact": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in wilcoxon_exact(task_means).items()},
        },
        "_strata": [(sum(v), len(v)) for v in per_task.values() if v],
    }
    if rng is not None and n:
        est, blo, bhi = cluster_boot([out["_strata"]], rng)
        out["cluster_boot95_pp"] = [round(100 * blo, 1), round(100 * bhi, 1)]
    return out


# ── 無法區分條件（修正 5）─────────────────────────────────────────────────

def indist(cells, events) -> dict:
    sc = [c for c in cells if not c["infra_void"]]
    A = [c for c in sc if c["arm"] == "A"]
    a_pass = sum(1 for c in A if c["hidden_pass"])
    rbc = [c for c in sc if c["arm"] in ("R", "B", "C")]
    rbc_all = [c for c in cells if c["arm"] in ("R", "B", "C")]
    ge2 = sum(1 for c in rbc if c["n_attempts"] >= 2)
    ge2_all = sum(1 for c in rbc_all if c["n_attempts"] >= 2)
    rules = Counter(e["rule"] for e in events)
    r36 = sum(rules.get(k, 0) for k in (3, 4, 5, 6))
    # 只算「非 void 格」裡的事件（void 格裡的事件是否算真模型觸發，文件沒說；兩種都報）
    void_cells = {f"{c['task']}/r{c['rep']}/C" for c in cells if c["arm"] == "C" and c["infra_void"]}
    r36_nonvoid = sum(1 for e in events if e["rule"] in (3, 4, 5, 6) and e["cell"] not in void_cells)
    return {
        "cond1_A": [a_pass, len(A)], "cond1_A_rate": round(a_pass / len(A), 4), "cond1_holds(>=0.75)": a_pass / len(A) >= 0.75,
        "cond2_rbc_ge2": [ge2, len(rbc)], "cond2_rate": round(ge2 / len(rbc), 4), "cond2_holds(<0.25)": ge2 / len(rbc) < 0.25,
        "cond2_incl_void": [ge2_all, len(rbc_all)],
        "cond3_rules_3to6": r36, "cond3_rules_3to6_excl_void_cells": r36_nonvoid, "cond3_holds(<10)": r36 < 10,
        "rules": {str(k): rules.get(k, 0) for k in range(1, 7)},
        "verdict_indistinguishable": (a_pass / len(A) >= 0.75) or (ge2 / len(rbc) < 0.25) or (r36 < 10),
    }


# ── 決策事件核對 ──────────────────────────────────────────────────────────

def expected_rule(ev: dict) -> int:
    """只用 evidence 欄位，照決策文件（含第十次稽核補註 3a/3b）的順序與門檻重推規則。"""
    e = ev["evidence"]
    if e["accepted"]:
        return 1
    if e["remaining_attempts"] <= 0 or e["remaining_budget_s"] <= 0 or e["remaining_budget_s"] < e["min_attempt_s"]:
        return 2
    if e["prior_best_passed"] is not None and e["passed"] < e["prior_best_passed"]:
        return 3
    if e.get("_prev_sig") is not None and e["failure_signature"] and e["_prev_sig"] == e["failure_signature"] \
            and e["passed"] <= e["_prev_passed"]:
        return 4
    if e["total"] > 0 and e["passed"] * 10 >= e["total"] * 7:
        return 5
    return 6


def check_events(cells, events) -> dict:
    by_cell = defaultdict(list)
    for e in events:
        by_cell[e["cell"]].append(e)
    idx = index_cells(cells)
    mism_rule, mism_cells, mism_ev_vs_cell, mism_deliver, mism_flags = [], [], [], [], []
    for cell, evs in by_cell.items():
        evs.sort(key=lambda e: e["attempt"])
        t, r, arm = cell.split("/")
        c = idx[(t, int(r[1:]), arm)]
        if [e["attempt"] for e in evs] != list(range(1, len(evs) + 1)) or len(evs) != c["n_attempts"]:
            mism_cells.append({"cell": cell, "events": len(evs), "n_attempts": c["n_attempts"]})
        prev = None
        best_passed, best_acc = None, False
        for e in evs:
            ev = dict(e)
            ev["evidence"] = dict(e["evidence"])
            ev["evidence"]["_prev_sig"] = prev["evidence"]["failure_signature"] if prev else None
            ev["evidence"]["_prev_passed"] = prev["evidence"]["passed"] if prev else None
            exp = expected_rule(ev)
            if exp != e["rule"]:
                mism_rule.append({"cell": cell, "attempt": e["attempt"], "logged": e["rule"], "expected": exp})
            # evidence 內部一致：pass_ratio、mostly_passing、worse_than_best、prior_best
            ev0 = e["evidence"]
            pr = ev0["passed"] / ev0["total"] if ev0["total"] else 0.0
            if abs(pr - ev0["pass_ratio"]) > 1e-5 or ev0["mostly_passing"] != (ev0["total"] > 0 and ev0["passed"] * 10 >= ev0["total"] * 7):
                mism_flags.append({"cell": cell, "attempt": e["attempt"], "what": "pass_ratio/mostly_passing"})
            if ev0["prior_best_passed"] != best_passed:
                mism_flags.append({"cell": cell, "attempt": e["attempt"], "what": "prior_best_passed",
                                   "logged": ev0["prior_best_passed"], "recomputed": best_passed})
            if ev0["passed"] != sum(1 for v in ev0["tests"].values() if v) and ev0["tests"]:
                mism_flags.append({"cell": cell, "attempt": e["attempt"], "what": "passed != count(tests)"})
            # 和逐格表的嘗試對帳
            att = c["attempts"][e["attempt"] - 1] if e["attempt"] - 1 < len(c["attempts"]) else None
            # 逾時／載入錯誤時逐格表寫 None、事件寫 0：視為相同
            if att is None or att["rule"] != e["rule"] or (att["acc_passed"] or 0) != ev0["passed"] or (att["acc_total"] or 0) != ev0["total"]:
                mism_ev_vs_cell.append({"cell": cell, "attempt": e["attempt"]})
            # best 更新（決策文件規則 2 的「最佳」：驗收通過者勝；否則通過數最多、同分取最新）
            if best_passed is None or ev0["accepted"] or (not best_acc and ev0["passed"] >= best_passed):
                best_passed, best_acc = ev0["passed"], ev0["accepted"]
            prev = e
    # 交付版核對（全部臂）：第一個驗收通過；否則驗收通過數最多、同分取最新
    for c in cells:
        if c["infra_void"]:
            continue
        atts = c["attempts"]
        acc = [a["acc_passed"] == a["acc_total"] and a["acc_status"] == "ok" and a["acc_total"] > 0 for a in atts]
        d = None
        for i, ok in enumerate(acc):
            if ok:
                d = i
                break
        if d is None:
            d = max(range(len(atts)), key=lambda i: ((atts[i]["acc_passed"] or 0), i))
        if d + 1 != c["delivered_attempt"] or bool(atts[d]["hidden_pass"]) != bool(c["hidden_pass"]):
            mism_deliver.append({"cell": f"{c['task']}/r{c['rep']}/{c['arm']}", "delivered": c["delivered_attempt"], "recomputed": d + 1})
        # 重開臂：驗收通過後不得再跑
        if c["arm"] in ("R", "B", "C") and any(acc[:-1]):
            mism_deliver.append({"cell": f"{c['task']}/r{c['rep']}/{c['arm']}", "what": "attempt after acceptance"})
    return {"rule_mismatch": mism_rule, "event_count_mismatch": mism_cells, "event_vs_cells_mismatch": mism_ev_vs_cell,
            "evidence_flag_mismatch": mism_flags, "delivery_mismatch": mism_deliver}


def next_attempt_effect(cells, events) -> dict:
    """觸發規則 k（C）或重開（B/R）之後，下一次嘗試的驗收通過率變化。分層：前一次驗收比例 >=70% vs <70%。"""
    out = {}
    by = defaultdict(list)
    idx = index_cells(cells)
    for e in events:
        if e["rule"] in (3, 4, 5, 6):
            t, r, arm = e["cell"].split("/")
            c = idx[(t, int(r[1:]), arm)]
            if c["infra_void"] or e["attempt"] >= len(c["attempts"]):
                continue
            cur, nxt = c["attempts"][e["attempt"] - 1], c["attempts"][e["attempt"]]
            by[f"C_rule{e['rule']}"].append((cur, nxt))
    for c in cells:
        if c["arm"] in ("B", "R") and not c["infra_void"]:
            for i in range(len(c["attempts"]) - 1):
                by[f"{c['arm']}_restart"].append((c["attempts"][i], c["attempts"][i + 1]))

    def ratio(a):
        return (a["acc_passed"] or 0) / a["acc_total"] if a["acc_total"] else 0.0
    for k, lst in sorted(by.items()):
        rec = {}
        for band, f in (("prev>=70%", lambda a: ratio(a) >= 0.7), ("prev<70%", lambda a: ratio(a) < 0.7), ("all", lambda a: True)):
            sub = [(x, y) for x, y in lst if f(x)]
            if not sub:
                continue
            dl = [ratio(y) - ratio(x) for x, y in sub]
            rec[band] = {
                "n": len(sub),
                "mean_delta_acc_ratio": round(sum(dl) / len(dl), 3),
                "next_improved": sum(1 for v in dl if v > 1e-9),
                "next_worse": sum(1 for v in dl if v < -1e-9),
                "next_full_acceptance": sum(1 for x, y in sub if y["acc_total"] and y["acc_passed"] == y["acc_total"]),
                "next_hidden_pass": sum(1 for x, y in sub if y["hidden_pass"]),
                "next_timed_out": sum(1 for x, y in sub if y["timed_out"]),
            }
        out[k] = rec
    return out


def c_broken_after_pass(cells, events) -> dict:
    """C 臂 broken-after-pass：曾在某次嘗試通過、交付版失敗的驗收測試 / 曾通過者（用事件裡的逐測試結果）。"""
    by = defaultdict(dict)
    for e in events:
        by[e["cell"]][e["attempt"]] = e["evidence"]["tests"]
    br = ever = 0
    for c in cells:
        if c["arm"] != "C" or c["infra_void"]:
            continue
        tests = by.get(f"{c['task']}/r{c['rep']}/C", {})
        ep = {t for k, tr in tests.items() for t, ok in tr.items() if ok}
        dl = tests.get(c["delivered_attempt"], {})
        ever += len(ep)
        br += sum(1 for t in ep if not dl.get(t, False))
    return {"broken": br, "ever_passed": ever, "ratio": round(br / ever, 4) if ever else None}


def token_diff(cells, treat: str, ctrl: str, rng: random.Random) -> dict:
    """配對（題, 重複）的每格 token 差（處理 − 對照），以題為群集 bootstrap 的 95% 區間；另報中位數與差為負的對數。"""
    idx = index_cells(cells)
    per_task = defaultdict(list)
    for (t, r, arm), x in idx.items():
        if arm != treat:
            continue
        y = idx.get((t, r, ctrl))
        if y is None or x["infra_void"] or y["infra_void"]:
            continue
        per_task[t].append(x["tokens_total"] - y["tokens_total"])
    allv = [v for vs in per_task.values() for v in vs]
    if not allv:
        return {}
    strata = [(sum(vs), len(vs)) for vs in per_task.values()]
    est, lo, hi = cluster_boot([strata], rng, 5000)
    s = sorted(allv)
    return {"pairs": len(allv), "mean_per_cell": round(est), "cluster_boot95": [round(lo), round(hi)],
            "median_per_cell": s[len(s) // 2], "pairs_treat_fewer": sum(1 for v in allv if v < 0)}


def subset_paired(cells, keep, treat, ctrl) -> dict:
    sub = [c for c in cells if keep(c)]
    p = paired(sub, treat, ctrl, "drop")
    p.pop("_strata")
    return {k: p[k] for k in ("pairs", "treat_pass", "ctrl_pass", "treat_only", "ctrl_only", "delta_pp", "mcnemar_exact_p", "newcombe95_pp")}


def host_breakdown(cells) -> dict:
    out = {}
    for arm in ARMS:
        for host in sorted({c["host"] for c in cells}):
            cs = [c for c in cells if c["arm"] == arm and c["host"] == host]
            sc = [c for c in cs if not c["infra_void"]]
            if not cs:
                continue
            out[f"{arm}@{host}"] = {
                "cells": len(cs), "scored": len(sc),
                "hidden_pass": sum(1 for c in sc if c["hidden_pass"]),
                "attempts": sum(c["n_attempts"] for c in sc),
                "timeouts": sum(c["timeouts"] for c in sc),
                "cells_with_timeout": sum(1 for c in sc if c["timeouts"] > 0),
                "tokens_per_cell": round(sum(c["tokens_total"] for c in sc) / len(sc)) if sc else None,
            }
    # 同一 (題, 重複) 的四臂是否在同一台
    pairs = defaultdict(set)
    for c in cells:
        pairs[(c["task"], c["rep"])].add(c["host"])
    out["_pairs_split_across_hosts"] = sum(1 for v in pairs.values() if len(v) > 1)
    return out


def harness_breakdown(cells) -> dict:
    out = {}
    for h in sorted({c["harness_sha256"][:12] for c in cells}):
        cs = [c for c in cells if c["harness_sha256"][:12] == h]
        out[h] = {arm: [sum(1 for c in cs if c["arm"] == arm and c["hidden_pass"]),
                        sum(1 for c in cs if c["arm"] == arm and not c["infra_void"])] for arm in ARMS}
        out[h]["pairs"] = sorted({f"{c['task']}/r{c['rep']}" for c in cs})
    return out


def leakage_signals(cells) -> dict:
    """可從逐格表看到的、與『讀到隱藏測試』相容的訊號：驗收沒全過但隱藏全過（交付版）。只是相容，不是證據。"""
    out = {}
    for arm in ARMS:
        sc = [c for c in cells if c["arm"] == arm and not c["infra_void"]]
        acc_t = [c for c in sc if c["accepted"]]
        out[arm] = {
            "accepted": len(acc_t),
            "hidden_pass_given_accepted": sum(1 for c in acc_t if c["hidden_pass"]),
            "hidden_pass_given_not_accepted": sum(1 for c in sc if not c["accepted"] and c["hidden_pass"]),
            "not_accepted": sum(1 for c in sc if not c["accepted"]),
        }
    return out


# ── 主程式 ────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", help="已展開的稽核包目錄（含 <batch>_cells.json 等）；不給就用 git show")
    ap.add_argument("--rev", default=REV_DEFAULT)
    ap.add_argument("--out", help="輸出 JSON 路徑")
    a = ap.parse_args()
    src = pathlib.Path(a.dir) if a.dir else None
    rng = random.Random(BOOT_SEED)
    res: dict = {"schema": "vacant.redo.ctl_audit_recompute/1", "source_rev": a.rev if src is None else None,
                 "bootstrap": {"n": BOOT_N, "seed": BOOT_SEED, "method": "percentile, tasks resampled within batch"},
                 "batches": {}}
    strata_all = defaultdict(list)  # comparison -> list of strata
    for b in BATCHES:
        cells, events, indist_theirs, tt = load_batch(b, src, a.rev)
        R: dict = {}
        sc = [c for c in cells if not c["infra_void"]]
        R["n_cells"] = len(cells)
        R["voids"] = [{"cell": f"{c['task']}/r{c['rep']}/{c['arm']}", "host": c["host"], "reason": c["infra_void"],
                       "valid_attempts": [{k: x[k] for k in ("k", "acc_passed", "acc_total", "timed_out", "rule", "action", "hidden_pass")}
                                          for x in c["attempts"]]} for c in cells if c["infra_void"]]
        R["hidden_pass"] = {arm: [sum(1 for c in sc if c["arm"] == arm and c["hidden_pass"]),
                                  sum(1 for c in sc if c["arm"] == arm)] for arm in ARMS}
        # 次要指標：隱藏測試滿足比例（交付版 hidden_passed/hidden_total；total 為 0 的格不計，與 ctl_metrics 同）
        R["hidden_satisfaction"] = {}
        for arm in ARMS:
            xs = [c for c in sc if c["arm"] == arm and c["hidden_total"]]
            R["hidden_satisfaction"][arm] = {
                "macro": round(sum(c["hidden_passed"] / c["hidden_total"] for c in xs) / len(xs), 4),
                "micro": round(sum(c["hidden_passed"] for c in xs) / sum(c["hidden_total"] for c in xs), 4),
                "cells": len(xs), "cells_hidden_total_0": sum(1 for c in sc if c["arm"] == arm and not c["hidden_total"])}
        # 一致性：cells 的 hidden_pass 與 hidden_passed==hidden_total
        R["hidden_flag_inconsistent"] = [f"{c['task']}/r{c['rep']}/{c['arm']}" for c in sc
                                         if bool(c["hidden_pass"]) != bool(c["hidden_total"] and c["hidden_passed"] == c["hidden_total"])]
        comps = {}
        for treat, ctrl in (("C", "B"), ("C", "R"), ("B", "R"), ("R", "A"), ("B", "A"), ("C", "A")):
            p = paired(cells, treat, ctrl, "drop", rng)
            strata_all[f"{treat}_vs_{ctrl}"].append(p["_strata"])
            if b != "ctl12_q9":
                strata_all[f"{treat}_vs_{ctrl}__2batches"].append(p["_strata"])
            p.pop("_strata")
            comps[f"{treat}_vs_{ctrl}"] = p
        R["paired"] = comps
        if any(c["infra_void"] for c in cells):
            sens = {}
            for mode in ("fail", "pass"):
                for ctrl in ("B", "R"):
                    p = paired(cells, "C", ctrl, mode)
                    p.pop("_strata")
                    sens[f"C_vs_{ctrl}__void_as_{mode}"] = {k: p[k] for k in ("pairs", "treat_pass", "ctrl_pass", "treat_only", "ctrl_only",
                                                                         "delta_pp", "mcnemar_exact_p", "newcombe95_pp")}
                    sens[f"C_vs_{ctrl}__void_as_{mode}"]["cluster_signflip_p"] = p["cluster"]["signflip_exact_p"]
            # 不配對的直接比率（C 66 格 vs B 68 格）
            sens["unpaired_rates"] = {arm: R["hidden_pass"][arm] for arm in ARMS}
            R["void_sensitivity"] = sens
        R["indistinguishability"] = indist(cells, events)
        R["indistinguishability_theirs"] = indist_theirs
        R["events"] = {"n": len(events), "cells_with_events": len({e["cell"] for e in events})}
        R["event_checks"] = check_events(cells, events)
        R["after_action_effect"] = next_attempt_effect(cells, events)
        R["C_broken_after_pass_from_events"] = c_broken_after_pass(cells, events)
        R["hosts"] = host_breakdown(cells)
        R["token_timeout_theirs_vs_mine"] = []
        for row in tt:
            mine = R["hosts"].get(f"{row['arm']}@{row['host']}")
            R["token_timeout_theirs_vs_mine"].append({
                "arm": row["arm"], "host": row["host"],
                "theirs": {k: row[k] for k in ("cells", "timeouts", "attempts", "tokens_per_cell")},
                "mine": {"cells": mine["scored"], "timeouts": mine["timeouts"], "attempts": mine["attempts"], "tokens_per_cell": mine["tokens_per_cell"]},
            })
        R["harness"] = harness_breakdown(cells)
        hosts = sorted({c["host"] for c in cells})
        if len(hosts) > 1:
            R["paired_by_host"] = {f"{tr}_vs_{ct}@{h}": subset_paired(cells, lambda c, h=h: c["host"] == h, tr, ct)
                                   for h in hosts for tr, ct in (("C", "B"), ("C", "R"), ("R", "A"))}
        if len({c["harness_sha256"] for c in cells}) > 1:
            R["harness_sensitivity_drop_pairs_touched_by_new_harness"] = {
                "pairs_dropped": sorted({f"{c['task']}/r{c['rep']}" for c in cells
                                         if c["harness_sha256"][:12] != "8ce7d87fbfae"}),
                **{f"{tr}_vs_{ct}": subset_paired(
                    cells, lambda c: f"{c['task']}/r{c['rep']}" not in {f"{x['task']}/r{x['rep']}" for x in cells
                                                                       if x["harness_sha256"][:12] != "8ce7d87fbfae"}, tr, ct)
                   for tr, ct in (("C", "B"), ("C", "R"), ("R", "A"))}}
        R["token_diff"] = {f"{tr}_vs_{ct}": token_diff(cells, tr, ct, rng) for tr, ct in (("C", "B"), ("C", "R"))}
        R["leakage_signals"] = leakage_signals(cells)
        R["timeouts_by_arm"] = {arm: {"cells_with_timeout": sum(1 for c in sc if c["arm"] == arm and c["timeouts"] > 0),
                                      "timeouts": sum(c["timeouts"] for c in sc if c["arm"] == arm),
                                      "attempts": sum(c["n_attempts"] for c in sc if c["arm"] == arm),
                                      "cells": sum(1 for c in sc if c["arm"] == arm)} for arm in ARMS}
        # 和結論頭條逐一對照
        cl = CLAIMED[b]
        diffs = []
        for arm in ARMS:
            if tuple(R["hidden_pass"][arm]) != cl[arm]:
                diffs.append(f"{arm}: 結論 {cl[arm]} vs 重算 {tuple(R['hidden_pass'][arm])}")
        for k in ("C_vs_B", "C_vs_R"):
            if k in cl:
                p = comps[k]
                if p["treat_pass"] != cl[k]["treat"] or p["ctrl_pass"] != cl[k]["ctrl"]:
                    diffs.append(f"{k}: 結論 {cl[k]['treat']} 對 {cl[k]['ctrl']} vs 重算 {p['treat_pass']} 對 {p['ctrl_pass']}")
                if "p" in cl[k] and abs(p["mcnemar_exact_p"] - cl[k]["p"]) > 0.006:
                    diffs.append(f"{k}: p 結論 {cl[k]['p']} vs 重算 {p['mcnemar_exact_p']}")
                if "delta_pp" in cl[k] and abs(p["delta_pp"] - cl[k]["delta_pp"]) > 0.06:
                    diffs.append(f"{k}: Δ 結論 {cl[k]['delta_pp']} vs 重算 {p['delta_pp']}")
        mine_rules = {int(k): v for k, v in R["indistinguishability"]["rules"].items()}
        if mine_rules != cl["rules"]:
            diffs.append(f"rules: 結論 {cl['rules']} vs 重算 {mine_rules}")
        if R["indistinguishability"]["cond3_rules_3to6"] != cl["cond3"]:
            diffs.append(f"cond3: 結論 {cl['cond3']} vs 重算 {R['indistinguishability']['cond3_rules_3to6']}")
        if "cond2" in cl and tuple(R["indistinguishability"]["cond2_rbc_ge2"]) != cl["cond2"]:
            diffs.append(f"cond2: 結論 {cl['cond2']} vs 重算 {R['indistinguishability']['cond2_rbc_ge2']}")
        if "cond2_pct" in cl and abs(100 * R["indistinguishability"]["cond2_rate"] - cl["cond2_pct"]) > 0.6:
            diffs.append(f"cond2%: 結論 {cl['cond2_pct']} vs 重算 {100 * R['indistinguishability']['cond2_rate']:.1f}")
        if "cond1_pct" in cl and abs(100 * R["indistinguishability"]["cond1_A_rate"] - cl["cond1_pct"]) > 0.6:
            diffs.append(f"cond1%: 結論 {cl['cond1_pct']} vs 重算 {100 * R['indistinguishability']['cond1_A_rate']:.1f}")
        R["diffs_vs_conclusion"] = diffs
        res["batches"][b] = R
    pooled = {}
    for k, strata in strata_all.items():
        est, lo, hi = cluster_boot(strata, rng)
        flat = [s for st in strata for s, _ in st]
        pooled[k] = {"pairs": sum(m for st in strata for _, m in st), "delta_pp": round(100 * est, 2),
                     "cluster_boot95_pp": [round(100 * lo, 1), round(100 * hi, 1)],
                     "signflip_exact_p_all_tasks": round(signflip_exact(flat), 6),
                     "n_tasks": len(flat)}
    res["pooled_pair_weighted"] = pooled
    txt = json.dumps(res, ensure_ascii=False, indent=1)
    if a.out:
        pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(a.out).write_text(txt + "\n", encoding="utf-8")
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
