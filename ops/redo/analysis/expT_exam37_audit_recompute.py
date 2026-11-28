#!/usr/bin/env python3
"""獨立複核：實驗 T 與 exam37 的數字，從稽核包的原始逐格表／逐行狀態自己重算（只用標準函式庫）。

這支在架構裡承重的是「第二雙手」：不 import 對方任何分析腳本（`ops/d2/expT_metrics.py`、
`ops/d2/expT_te_sensitivity.py`、`ops/redo/analysis/exam_metrics.py`），定義只取自預註冊文字
（`ops/d2/plans/expT_qwen9b.json` 的 `prereg`、`ops/redo/plans/exam37_colab_e4b_part{1,2}.json` 的 `prereg`），
算完才把對方輸出（`expT_metrics.json`、`expT_te_sensitivity_nonprereg.json`、`exam37_metrics.json`）讀進來逐項比對。

資料來源：預設 `git show 3b60ef24a:<path>`（稽核包 `ops/redo/audit/expT_exam37_20261128/`）；或 `--dir <稽核包根目錄>`。

方法（以組為群集）：
- (a) 每格 final_correct/n_lines，組內兩次平均，再對組平均（＝預註冊「per-set correct-line proportion」）。
- 配對差：同一 (組, 次) 兩臂相減，組內平均成 d_s，總差＝mean(d_s)。
- 區間：(1) 群集 bootstrap（重抽組，10,000 次，種子 7，百分位）；(2) 群集 t（t_{0.975, n−1}·sd/√n）；
  (3) 組層級符號翻轉置換檢定（雙尾，100,000 次隨機翻轉）。對方用的是群集 bootstrap 2,000 次、種子 20261127。
- 傷害區間：每組傷害行數差（兩次合計）做同樣的群集 bootstrap，換算成總行數差。

誠實邊界：
- 逐行檔只有狀態與值的 sha256，沒有值與答案；所以「狀態」本身是對方評分器給的，這裡驗的是**彙總與比較**，
  不是評分器本身。評分器要在私有教材上另驗。
- 回饋鏈只有 payload 的 sha256：只能驗串接（prev_hash＝上一筆 entry_hash、stream_id、鏈頭、公鑰對得上），
  entry_hash 與簽章都覆蓋 payload 原文，在公開檔上**驗不了**。
- 稽核包沒有 agent 紀錄（工具呼叫、讀檔路徑）⇒ 越界讀取在這裡**定位不了**；只能做「最壞情況」的排除界。

用法：python3 ops/redo/analysis/expT_exam37_audit_recompute.py [--rev 3b60ef24a | --dir D] [--out J]
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import pathlib
import random
import statistics
import subprocess
import sys
from typing import Any, Callable

PKG = "ops/redo/audit/expT_exam37_20261128"
ARMS = ["A", "G", "T", "TB", "TO", "TE", "TER"]
BOOT = 10_000
BOOT_SEED = 7
PERM = 100_000
DEFAULT_OUT = "ops/redo/audit/expT_exam37_20261128_review/recompute_output.json"


# ───────────────────────────── 讀檔 ─────────────────────────────
class Src:
    def __init__(self, rev: str | None, d: str | None, repo: pathlib.Path):
        self.rev, self.dir, self.repo = rev, pathlib.Path(d) if d else None, repo

    def text(self, rel: str) -> str:
        if self.dir is not None:
            return (self.dir / rel).read_text(encoding="utf-8")
        return subprocess.run(["git", "-C", str(self.repo), "show", f"{self.rev}:{PKG}/{rel}"],
                              check=True, capture_output=True).stdout.decode("utf-8")

    def json(self, rel: str) -> Any:
        return json.loads(self.text(rel))

    def jsonl(self, rel: str) -> list[dict]:
        return [json.loads(x) for x in self.text(rel).splitlines() if x.strip()]

    def listdir(self, rel: str) -> list[str]:
        if self.dir is not None:
            return sorted(p.name for p in (self.dir / rel).iterdir())
        out = subprocess.run(["git", "-C", str(self.repo), "ls-tree", "--name-only", f"{self.rev}:{PKG}/{rel}"],
                             check=True, capture_output=True).stdout.decode()
        return sorted(x for x in out.splitlines() if x)

    def chain_files(self) -> dict[str, tuple[str, str]]:
        """{cell: (ndjson_text, pub_text)}；git 模式一次 cat-file --batch 讀完 1,036 個檔。"""
        cells = self.listdir("expT/expT_chains")
        if self.dir is not None:
            return {c: ((self.dir / f"expT/expT_chains/{c}/feedback_chain_hashed.ndjson").read_text(),
                        (self.dir / f"expT/expT_chains/{c}/feedback_chain.pub.json").read_text()) for c in cells}
        specs = []
        for c in cells:
            specs += [f"{self.rev}:{PKG}/expT/expT_chains/{c}/feedback_chain_hashed.ndjson",
                      f"{self.rev}:{PKG}/expT/expT_chains/{c}/feedback_chain.pub.json"]
        p = subprocess.run(["git", "-C", str(self.repo), "cat-file", "--batch"], input="\n".join(specs).encode() + b"\n",
                           check=True, capture_output=True).stdout
        out, i, blobs = {}, 0, []
        while i < len(p):
            nl = p.index(b"\n", i)
            hdr = p[i:nl].split()
            size = int(hdr[2])
            blobs.append(p[nl + 1:nl + 1 + size].decode())
            i = nl + 1 + size + 1
        for j, c in enumerate(cells):
            out[c] = (blobs[2 * j], blobs[2 * j + 1])
        return out


# ───────────────────────────── 統計 ─────────────────────────────
def _t_pdf(x: float, df: int) -> float:
    return math.exp(math.lgamma((df + 1) / 2) - math.lgamma(df / 2)) / math.sqrt(df * math.pi) * (1 + x * x / df) ** (-(df + 1) / 2)


def t_quantile(p: float, df: int) -> float:
    def cdf(x: float) -> float:  # Simpson on [0, x]
        n = 2000
        h = x / n
        s = _t_pdf(0, df) + _t_pdf(x, df) + sum((4 if k % 2 else 2) * _t_pdf(k * h, df) for k in range(1, n))
        return 0.5 + s * h / 3
    lo, hi = 0.0, 50.0
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if cdf(mid) < p else (lo, mid)
    return (lo + hi) / 2


_TQ: dict[int, float] = {}


def cluster_summary(d: dict[str, float], scale: float = 100.0, seed: int = BOOT_SEED) -> dict:
    """d: {set: 組層級差}。回傳點估計、bootstrap／t 區間、符號翻轉 p（都乘 scale）。"""
    keys = sorted(d)
    xs = [d[k] for k in keys]
    n = len(xs)
    m = statistics.fmean(xs)
    rng = random.Random(seed)
    bs = sorted(statistics.fmean(rng.choice(xs) for _ in range(n)) for _ in range(BOOT))
    sd = statistics.stdev(xs) if n > 1 else 0.0
    if n - 1 not in _TQ:
        _TQ[n - 1] = t_quantile(0.975, n - 1)
    half = _TQ[n - 1] * sd / math.sqrt(n)
    rng2 = random.Random(seed + 1)
    obs = abs(sum(xs))
    ge = sum(1 for _ in range(PERM) if abs(sum(x if rng2.random() < 0.5 else -x for x in xs)) >= obs - 1e-12)
    return {"n_sets": n, "diff": round(scale * m, 2),
            "boot95": [round(scale * bs[int(0.025 * BOOT)], 2), round(scale * bs[int(0.975 * BOOT) - 1], 2)],
            "t95": [round(scale * (m - half), 2), round(scale * (m + half), 2)],
            "signflip_p": round((ge + 1) / (PERM + 1), 4)}


# ───────────────────────────── 實驗 T ─────────────────────────────
def expT(src: Src) -> dict:
    R: dict[str, Any] = {}
    cells = src.json("expT/expT_cells.json")
    lines = src.jsonl("expT/expT_lines.jsonl")
    C = {(c["set"], c["rep"], c["arm"]): c for c in cells}
    sets = sorted({c["set"] for c in cells})
    pairs = sorted({(c["set"], c["rep"]) for c in cells})
    LB: dict[tuple, list[dict]] = collections.defaultdict(list)
    for x in lines:
        LB[(x["set"], x["rep"], x["arm"])].append(x)

    # ── 完整性 ──
    integ: dict[str, Any] = {"cells": len(cells), "lines": len(lines), "sets": len(sets), "pairs": len(pairs),
                             "cells_per_arm": dict(collections.Counter(c["arm"] for c in cells)),
                             "infra_void": sum(bool(c["infra_void"]) for c in cells)}
    mism = []
    for k, c in C.items():
        L = LB[k]
        chk = {"n_lines": len(L), "final_correct": sum(x["after_status"] == "correct" for x in L),
               "c0_correct": sum(x["before_status"] == "correct" for x in L),
               "final_filled": sum(x["after_status"] != "missing" for x in L),
               "c0_filled": sum(x["before_status"] != "missing" for x in L),
               "harm_c2w_or_d": sum(x["harm_c2w_or_d"] for x in L), "harm_b2w": sum(x["harm_b2w"] for x in L),
               "sent_back": sum(x["sent_back"] for x in L)}
        for f, v in chk.items():
            if c[f] != v:
                mism.append({"cell": k, "field": f, "cells": c[f], "lines": v})
        # harm 定義自己重算：C→W/D ＝ before correct 且 after≠correct；B→W ＝ before missing 且 after wrong
        for x in L:
            h1 = x["before_status"] == "correct" and x["after_status"] != "correct"
            h2 = x["before_status"] == "missing" and x["after_status"] == "wrong"
            if h1 != x["harm_c2w_or_d"] or h2 != x["harm_b2w"]:
                mism.append({"cell": k, "claim": x["claim_id"], "field": "harm_flag_def"})
    integ["cells_vs_lines_mismatches"] = mism[:20]
    integ["cells_vs_lines_mismatch_count"] = len(mism)
    # 配對：同一 (組, 次) 七臂的 c0 報告雜湊與逐行 before 值雜湊相同
    c0_sha_diff, before_diff = [], []
    for s, r in pairs:
        shas = {C[(s, r, a)]["c0_report_sha256"] for a in ARMS}
        if len(shas) != 1:
            c0_sha_diff.append((s, r))
        ref = {x["claim_id"]: (x["before_value_sha256"], x["before_status"]) for x in LB[(s, r, "A")]}
        for a in ARMS:
            for x in LB[(s, r, a)]:
                if ref.get(x["claim_id"]) != (x["before_value_sha256"], x["before_status"]):
                    before_diff.append((s, r, a, x["claim_id"]))
    integ["pairs_with_c0_sha_disagreement"] = c0_sha_diff
    integ["lines_with_before_disagreement"] = len(before_diff)
    a_changed = [(s, r) for s, r in pairs if C[(s, r, "A")]["final_report_sha256"] != C[(s, r, "A")]["c0_report_sha256"]]
    integ["A_final_ne_c0"] = a_changed
    integ["A_lines_changed"] = {f"{s}/r{r}": sum(x["before_value_sha256"] != x["after_value_sha256"] for x in LB[(s, r, "A")])
                                for s, r in a_changed}
    integ["A_lines_status_changed"] = {f"{s}/r{r}": [(x["claim_id"], x["before_status"], x["after_status"])
                                                     for x in LB[(s, r, "A")] if x["before_status"] != x["after_status"]]
                                       for s, r in a_changed}
    R["integrity"] = integ

    # ── 七臂主指標 ──
    def prop(c: dict) -> float:
        return c["final_correct"] / c["n_lines"]

    def fprec(c: dict) -> float | None:
        return c["final_correct"] / c["final_filled"] if c["final_filled"] else None

    by_arm = {}
    for a in ARMS:
        cs = [C[(s, r, a)] for s, r in pairs]
        setmean = statistics.fmean(statistics.fmean(prop(C[(s, r, a)]) for r in (1, 2) if (s, r) in pairs) for s in sets)
        pooled = sum(c["final_correct"] for c in cs) / sum(c["n_lines"] for c in cs)
        fp_pool = sum(c["final_correct"] for c in cs) / sum(c["final_filled"] for c in cs)
        fp_set = []
        for s in sets:
            v = [fprec(C[(s, r, a)]) for r in (1, 2)]
            v = [x for x in v if x is not None]
            if v:
                fp_set.append(statistics.fmean(v))
        L = [x for s, r in pairs for x in LB[(s, r, a)]]
        by_arm[a] = {
            "a_setmean_pct": round(100 * setmean, 2), "a_pooled_pct": round(100 * pooled, 2),
            "b_filled_precision_pooled_pct": round(100 * fp_pool, 2),
            "b_filled_precision_setmean_pct": round(100 * statistics.fmean(fp_set), 2), "b_sets_with_filled": len(fp_set),
            "harm_c2w_or_d": sum(c["harm_c2w_or_d"] for c in cs), "harm_b2w": sum(c["harm_b2w"] for c in cs),
            "tokens_mean": round(statistics.fmean(c["tokens_total"] for c in cs)),
            "wall_mean_s": round(statistics.fmean(c["wall_s_total"] for c in cs), 1),
            "after_etype": dict(collections.Counter(x["after_etype"] for x in L)),
            "before_etype": dict(collections.Counter(x["before_etype"] for x in L)),
            "cells_all_correct_after": sum(c["final_correct"] == c["n_lines"] for c in cs),
        }
    R["by_arm"] = by_arm

    # ── 配對比較 ──
    def comp(t: str, c: str, metric: Callable[[dict], float | None] = prop, keep: set | None = None) -> dict:
        d: dict[str, list[float]] = collections.defaultdict(list)
        for s, r in pairs:
            if keep is not None and (s, r) not in keep:
                continue
            vt, vc = metric(C[(s, r, t)]), metric(C[(s, r, c)])
            if vt is None or vc is None:
                continue
            d[s].append(vt - vc)
        return cluster_summary({s: statistics.fmean(v) for s, v in d.items() if v})

    def harm_comp(t: str, c: str, keep: set | None = None) -> dict:
        d: dict[str, float] = collections.defaultdict(float)
        for s, r in pairs:
            if keep is not None and (s, r) not in keep:
                continue
            d[s] += (C[(s, r, t)]["harm_c2w_or_d"] + C[(s, r, t)]["harm_b2w"]) - (C[(s, r, c)]["harm_c2w_or_d"] + C[(s, r, c)]["harm_b2w"])
        cs = cluster_summary(dict(d), scale=float(len(d)))  # 每組平均差 × 組數 ＝ 總行數差
        return {"total_lines_diff": cs["diff"], "boot95_total": cs["boot95"], "t95_total": cs["t95"], "signflip_p": cs["signflip_p"]}

    def comp_pairweighted(t: str, c: str, keep: set) -> dict:
        """對照用：對 (組, 次) 直接平均（拿掉一對時該組只剩一次、權重減半），群集 bootstrap 重抽組。"""
        byset: dict[str, list[float]] = collections.defaultdict(list)
        for s, r in pairs:
            if (s, r) in keep:
                byset[s].append(prop(C[(s, r, t)]) - prop(C[(s, r, c)]))
        ks = sorted(byset)
        allv = [v for k_ in ks for v in byset[k_]]
        rng = random.Random(BOOT_SEED)
        bs = []
        for _ in range(BOOT):
            vs = [v for _k in range(len(ks)) for v in byset[rng.choice(ks)]]
            bs.append(statistics.fmean(vs))
        bs.sort()
        return {"pairs": len(allv), "diff": round(100 * statistics.fmean(allv), 2),
                "boot95": [round(100 * bs[int(0.025 * BOOT)], 2), round(100 * bs[int(0.975 * BOOT) - 1], 2)]}

    COMPS = [("T", "G"), ("T", "TB"), ("T", "TO"), ("TE", "TER"), ("T", "A"), ("G", "A"), ("TB", "A"), ("TO", "A"),
             ("TE", "A"), ("TER", "A")]
    comps = {}
    for t, c in COMPS:
        comps[f"{t}_vs_{c}"] = {"a": comp(t, c), "b_filled_precision": comp(t, c, fprec), "harm_total": harm_comp(t, c)}
    R["comparisons"] = comps

    # 預註冊判讀，照文字
    tg, ttb, tete = comps["T_vs_G"], comps["T_vs_TB"], comps["TE_vs_TER"]
    harm_T = by_arm["T"]["harm_c2w_or_d"] + by_arm["T"]["harm_b2w"]
    harm_G = by_arm["G"]["harm_c2w_or_d"] + by_arm["G"]["harm_b2w"]
    R["readout"] = {
        "T_vs_G_pass": tg["a"]["diff"] >= 10 and tg["a"]["boot95"][0] > 0 and harm_T <= harm_G,
        "T_vs_G_pass_t_interval": tg["a"]["diff"] >= 10 and tg["a"]["t95"][0] > 0 and harm_T <= harm_G,
        "T_vs_TB_pass_on_a": ttb["a"]["diff"] >= 5 and ttb["a"]["boot95"][0] > 0,
        "T_vs_TB_pass_on_filled_precision": ttb["b_filled_precision"]["diff"] >= 5 and ttb["b_filled_precision"]["boot95"][0] > 0,
        "TE_vs_TER_pass": tete["a"]["diff"] >= 10 and tete["a"]["boot95"][0] > 0,
        "harm_T": harm_T, "harm_G": harm_G,
        "harm_clearly_above_A_ci_lower_gt0": {a: comps[f"{a}_vs_A"]["harm_total"]["boot95_total"][0] > 0
                                              for a in ["G", "T", "TB", "TO", "TE", "TER"]},
    }
    tcells = [C[(s, r, "T")] for s, r in pairs]
    R["indistinguishable"] = {
        "A_a_setmean_pct": by_arm["A"]["a_setmean_pct"],
        "T_cells_sent_feedback": sum(c["sent_back"] > 0 for c in tcells), "T_cells": len(tcells),
        "T_cells_c0_flagged_gt0": sum(c["c0_flagged"] > 0 for c in tcells),
        "T_cells_rounds_gt0": sum(c["rounds_run"] > 0 for c in tcells),
    }
    R["indistinguishable"]["condition_met"] = (by_arm["A"]["a_setmean_pct"] > 85 or by_arm["A"]["a_setmean_pct"] < 10
                                              or R["indistinguishable"]["T_cells_sent_feedback"] < len(tcells) / 4)

    # ── 退化初稿：c0 全空 ──
    empty = sorted((s, r) for s, r in pairs if C[(s, r, "A")]["c0_filled"] == 0)
    nonempty = set(pairs) - set(empty)
    R["empty_c0"] = {
        "pairs": [f"{s}/r{r}" for s, r in empty], "n": len(empty),
        "c0_calls": {f"{s}/r{r}": C[(s, r, "A")]["calls_total"] for s, r in empty},
        "c0_wall_s": {f"{s}/r{r}": C[(s, r, "A")]["wall_s_total"] for s, r in empty},
        "final_correct_by_arm": {a: {f"{s}/r{r}": f'{C[(s, r, a)]["final_correct"]}/{C[(s, r, a)]["n_lines"]}' for s, r in empty}
                                 for a in ["T", "TB", "TO", "G", "TE", "TER"]},
        "excluding_empty_c0": {f"{t}_vs_{c}": comp(t, c, keep=nonempty) for t, c in COMPS},
        "only_empty_c0": {f"{t}_vs_{c}": comp(t, c, keep=set(empty)) for t, c in COMPS[:6]},
    }

    # ── 項目 2：T 與 TB 退回的行 ──
    def lineset(a: str, cond: Callable[[dict], bool]) -> set:
        return {(x["set"], x["rep"], x["claim_id"]) for s, r in pairs for x in LB[(s, r, a)] if cond(x)}

    Lidx = {(x["set"], x["rep"], x["arm"], x["claim_id"]): x for x in lines}
    T_sent, TB_sent = lineset("T", lambda x: x["sent_back"]), lineset("TB", lambda x: x["sent_back"])
    TO_sent = lineset("TO", lambda x: x["sent_back"])
    only_T = T_sent - TB_sent

    def outcome(keys: set, arm: str) -> dict:
        cnt = collections.Counter((Lidx[(s, r, arm, c)]["before_status"], Lidx[(s, r, arm, c)]["after_status"]) for s, r, c in keys)
        return {f"{b}->{a}": n for (b, a), n in sorted(cnt.items())}

    def net(keys: set, arm: str) -> int:
        return sum((Lidx[(s, r, arm, c)]["after_status"] == "correct") - (Lidx[(s, r, arm, c)]["before_status"] == "correct")
                   for s, r, c in keys)

    a_lines = {(x["set"], x["rep"], x["claim_id"]): x for x in lines if x["arm"] == "A"}
    flag_valued = {k for k in T_sent if a_lines[k]["before_status"] != "missing"}
    R["item2_T_vs_TB_lines"] = {
        "T_sent_c0": len(T_sent), "TB_sent_c0": len(TB_sent), "overlap": len(T_sent & TB_sent),
        "TB_not_in_T": len(TB_sent - T_sent), "T_only": len(only_T),
        "T_only_before_status": dict(collections.Counter(a_lines[k]["before_status"] for k in only_T)),
        "T_only_outcome_in_T": outcome(only_T, "T"), "T_only_net_correct_in_T": net(only_T, "T"),
        "T_only_outcome_in_TB": outcome(only_T, "TB"), "T_only_net_correct_in_TB": net(only_T, "TB"),
        "T_only_outcome_in_TO": outcome(only_T, "TO"), "T_only_net_correct_in_TO": net(only_T, "TO"),
        "T_only_outcome_in_G": outcome(only_T, "G"), "T_only_net_correct_in_G": net(only_T, "G"),
        "overlap_outcome_in_T": outcome(T_sent & TB_sent, "T"), "overlap_net_in_T": net(T_sent & TB_sent, "T"),
        "overlap_outcome_in_TB": outcome(T_sent & TB_sent, "TB"), "overlap_net_in_TB": net(T_sent & TB_sent, "TB"),
        "not_sent_by_T_net_in_T": net({k for k in a_lines} - T_sent, "T"),
        "not_sent_by_TB_net_in_TB": net({k for k in a_lines} - TB_sent, "TB"),
        "record_flag_precision_on_valued_lines": {
            "flagged_with_value": len(flag_valued),
            "of_which_wrong": sum(a_lines[k]["before_status"] == "wrong" for k in flag_valued),
            "of_which_correct": sum(a_lines[k]["before_status"] == "correct" for k in flag_valued)},
        "record_flag_recall_of_wrong_valued": {
            "wrong_valued_lines": sum(x["before_status"] == "wrong" for x in a_lines.values()),
            "flagged": sum(a_lines[k]["before_status"] == "wrong" for k in T_sent)},
        "wrong_read_flag_recall": {
            "wrong_read_lines": sum(x["before_etype"] == "wrong_read" for x in a_lines.values()),
            "flagged": sum(a_lines[k]["before_etype"] == "wrong_read" for k in T_sent)},
        "TO_sent_c0": len(TO_sent), "TO_outcome": outcome(TO_sent, "TO"), "TO_net": net(TO_sent, "TO"),
        "TO_on_wrong_valued_T_only": outcome({k for k in only_T if a_lines[k]["before_status"] == "wrong"}, "TO"),
        "T_on_wrong_valued_T_only": outcome({k for k in only_T if a_lines[k]["before_status"] == "wrong"}, "T"),
        "TB_overlap_lines_outcome_in_T_vs_TB_note": "overlap＝c0 空白而且兩臂都退回的行",
    }
    # 第 1 輪 T 退回行中 T 自己計的 sent_back_fixed
    R["item2_T_vs_TB_lines"]["sent_back_fixed_cells_sum"] = {a: sum(C[(s, r, a)]["sent_back_fixed"] for s, r in pairs) for a in ["T", "TB", "TO", "TE", "TER"]}
    R["item2_T_vs_TB_lines"]["sent_back_cells_sum"] = {a: sum(C[(s, r, a)]["sent_back"] for s, r in pairs) for a in ["T", "TB", "TO", "TE", "TER"]}

    # ── 項目 3：G 的傷害、對齊 ──
    yoke = {"G_rounds_eq_T": 0, "G_rounds_ne_T": [], "G_runs_where_T_sent_none": [], "T_sent_but_G_zero_rounds": []}
    for s, r in pairs:
        g, t = C[(s, r, "G")], C[(s, r, "T")]
        if g["rounds_run"] == t["rounds_run"]:
            yoke["G_rounds_eq_T"] += 1
        else:
            yoke["G_rounds_ne_T"].append((s, r, g["rounds_run"], t["rounds_run"]))
        if t["sent_back"] == 0 and g["rounds_run"] > 0:
            yoke["G_runs_where_T_sent_none"].append((s, r))
        if t["sent_back"] > 0 and g["rounds_run"] == 0:
            yoke["T_sent_but_G_zero_rounds"].append((s, r))
    gh_set = collections.Counter()
    for s, r in pairs:
        gh_set[s] += C[(s, r, "G")]["harm_c2w_or_d"] + C[(s, r, "G")]["harm_b2w"]
    tot = sum(gh_set.values())
    top = gh_set.most_common()
    G_lines = [x for s, r in pairs for x in LB[(s, r, "G")]]
    T_lines = [x for s, r in pairs for x in LB[(s, r, "T")]]
    gpairs_harm = sorted(((C[(s, r, "G")]["harm_c2w_or_d"], f"{s}/r{r}", C[(s, r, "G")]["final_filled"], C[(s, r, "G")]["c0_filled"]) for s, r in pairs), reverse=True)

    def harm_split(L: list[dict]) -> dict:
        out = {}
        for key in ("before_etype", "digit_bucket", "c0_flagged"):
            out[key] = dict(collections.Counter(str(x[key]) for x in L if x["harm_c2w_or_d"] or x["harm_b2w"]))
        out["c2w_to"] = dict(collections.Counter(x["after_status"] for x in L if x["harm_c2w_or_d"]))
        return out

    # 同一批行（T 第一輪退回的行）上，G（沒被指出）與 T（被指出）的結果
    sent_keys = T_sent
    R["item3_G"] = {
        "yoking": yoke,
        "G_harm_by_set_top": top[:8], "G_harm_total": tot,
        "G_harm_share_top5_sets": round(sum(n for _, n in top[:5]) / tot, 3) if tot else None,
        "G_harm_share_by_domain": {"sc": sum(n for s, n in gh_set.items() if s.startswith("sc")),
                                   "fb": sum(n for s, n in gh_set.items() if s.startswith("fb"))},
        "G_c2w_top_pairs": gpairs_harm[:10],
        "G_pairs_with_any_c2w": sum(1 for h, *_ in gpairs_harm if h > 0),
        "G_harm_split": harm_split(G_lines), "T_harm_split": harm_split(T_lines),
        "same_lines_T_sent": {"G_outcome": outcome(sent_keys, "G"), "G_net": net(sent_keys, "G"),
                              "T_outcome": outcome(sent_keys, "T"), "T_net": net(sent_keys, "T")},
        "lines_T_did_not_send": {"G_net": net(set(a_lines) - sent_keys, "G"), "T_net": net(set(a_lines) - sent_keys, "T"),
                                 "G_harm": sum(Lidx[(s, r, "G", c)]["harm_c2w_or_d"] for s, r, c in set(a_lines) - sent_keys),
                                 "T_harm": sum(Lidx[(s, r, "T", c)]["harm_c2w_or_d"] for s, r, c in set(a_lines) - sent_keys)},
        "G_final_filled_drop_pairs": sum(C[(s, r, "G")]["final_filled"] < C[(s, r, "G")]["c0_filled"] for s, r in pairs),
        "G_c2w_after_missing_share": None,
        "G_wipe_pairs": [f"{s}/r{r}" for s, r in pairs if C[(s, r, "G")]["final_filled"] == 0 and C[(s, r, "G")]["c0_filled"] > 0],
        "G_wipe_c2w": sum(C[(s, r, "G")]["harm_c2w_or_d"] for s, r in pairs if C[(s, r, "G")]["final_filled"] == 0 and C[(s, r, "G")]["c0_filled"] > 0),
        "T_wipe_pairs": [f"{s}/r{r}" for s, r in pairs if C[(s, r, "T")]["final_filled"] == 0 and C[(s, r, "T")]["c0_filled"] > 0],
        "TO_wipe_pairs": [f"{s}/r{r}" for s, r in pairs if C[(s, r, "TO")]["final_filled"] == 0 and C[(s, r, "TO")]["c0_filled"] > 0],
    }
    c2w = [x for x in G_lines if x["harm_c2w_or_d"]]
    R["item3_G"]["G_c2w_after_missing_share"] = round(sum(x["after_status"] == "missing" for x in c2w) / len(c2w), 3) if c2w else None
    # 只在 G 有跑的配對上比 T 對 G
    gran = {(s, r) for s, r in pairs if C[(s, r, "G")]["rounds_run"] > 0}
    R["item3_G"]["T_vs_G_only_pairs_where_G_ran"] = comp("T", "G", keep=gran)
    R["item3_G"]["T_vs_G_excluding_empty_c0"] = comp("T", "G", keep=nonempty)

    # ── 項目 4：TE／TER ──
    hk = src.jsonl("expT/expT_haiku.jsonl")
    te = {}
    for a in ("TE", "TER"):
        rows = [h for h in hk if h["arm"] == a]
        called = [h for h in rows if h["called"]]
        sentL = [Lidx[(s, r, a, c)] for s, r in pairs for c in [x["claim_id"] for x in LB[(s, r, a)] if x["sent_back"]]]
        te[a] = {"rows": len(rows), "called": len(called),
                 "cost_usd": round(sum(h["cost_usd"] or 0 for h in called), 4),
                 "max_tokens_stops": sum(h["stop_reason"] == "max_tokens" for h in called),
                 "max_tokens_cells": sorted(f'{h["set"]}/r{h["rep"]}' for h in called if h["stop_reason"] == "max_tokens"),
                 "escalated_lines_haiku": sum(h["escalated_lines"] or 0 for h in rows),
                 "sent_lines_lines_file": len(sentL),
                 "sent_after_missing": sum(x["after_status"] == "missing" for x in sentL),
                 "sent_outcome": dict(collections.Counter(f'{x["before_status"]}->{x["after_status"]}' for x in sentL)),
                 "unsent_lines_changed": sum(1 for s, r in pairs for x in LB[(s, r, a)] if not x["sent_back"] and x["before_value_sha256"] != x["after_value_sha256"]),
                 "haiku_cells_without_call_but_flags": sum(1 for h in rows if not h["called"] and (h["escalated_lines"] or 0) > 0)}
    te["total_cost_usd"] = round(te["TE"]["cost_usd"] + te["TER"]["cost_usd"], 4)
    te["mean_cost_per_call"] = round(te["total_cost_usd"] / (te["TE"]["called"] + te["TER"]["called"]), 4)
    # 同一 (組,次) TE 與 TER 送的行數一樣嗎
    te_keys = {(s, r, x["claim_id"]) for s, r in pairs for x in LB[(s, r, "TE")] if x["sent_back"]}
    ter_keys = {(s, r, x["claim_id"]) for s, r in pairs for x in LB[(s, r, "TER")] if x["sent_back"]}
    exp_overlap = 0.0
    for s, r in pairs:
        n = len(LB[(s, r, "TE")])
        f = sum(x["sent_back"] for x in LB[(s, r, "TE")])
        exp_overlap += f * f / n
    te["TE_TER_sent_overlap"] = {"overlap_lines": len(te_keys & ter_keys), "of": len(te_keys),
                                 "expected_under_uniform": round(exp_overlap, 1),
                                 "pairs_identical_line_sets": sum(1 for s, r in pairs if {k for k in te_keys if k[:2] == (s, r)} and
                                                                  {k for k in te_keys if k[:2] == (s, r)} == {k for k in ter_keys if k[:2] == (s, r)})}
    te["n_lines_equal_TE_TER"] = sum(C[(s, r, "TE")]["sent_back"] == C[(s, r, "TER")]["sent_back"] for s, r in pairs)
    # 自己的保留原值重建：送出的行 after=missing ⇒ 退回 before 狀態（不碰答案鍵以外任何東西：狀態本來就由評分器給）
    def rebuilt_prop(c_: dict, arm: str, s: str, r: int, mode: str) -> float:
        L = LB[(s, r, arm)]
        ok = 0
        for x in L:
            st = x["after_status"]
            if mode == "keep" and x["sent_back"] and st == "missing":
                st = x["before_status"]
            ok += st == "correct"
        return ok / len(L)

    def rebuilt_comp(t: str, c: str, mode: str, keep: set | None = None, pooled: bool = False) -> dict:
        d: dict[str, list] = collections.defaultdict(list)
        for s, r in pairs:
            if keep is not None and (s, r) not in keep:
                continue
            vt = rebuilt_prop(C[(s, r, t)], t, s, r, mode) if t in ("TE", "TER") else prop(C[(s, r, t)])
            vc = rebuilt_prop(C[(s, r, c)], c, s, r, mode) if c in ("TE", "TER") else prop(C[(s, r, c)])
            d[s].append(vt - vc)
        return cluster_summary({s: statistics.fmean(v) for s, v in d.items()})

    trunc = set()
    for h in hk:
        if h["called"] and h["stop_reason"] == "max_tokens":
            trunc.add((h["set"], h["rep"]))
    keepset = set(pairs) - trunc
    te["sensitivity_auditor"] = {
        "method": "送出的行若 after_status＝missing 就還原成 before_status（等於假設所有 missing 結果都是 Haiku 沒給值）；組平均",
        "keep_on_null_TE_vs_TER": rebuilt_comp("TE", "TER", "keep"),
        "keep_on_null_TE_vs_A": rebuilt_comp("TE", "A", "keep"),
        "keep_on_null_TER_vs_A": rebuilt_comp("TER", "A", "keep"),
        "keep_on_null_harm_c2w": {a: sum(1 for s, r in pairs for x in LB[(s, r, a)]
                                         if x["before_status"] == "correct" and not (x["sent_back"] and x["after_status"] == "missing")
                                         and x["after_status"] != "correct") for a in ("TE", "TER")},
        "keep_on_null_setmean_pct": {a: round(100 * statistics.fmean(statistics.fmean(rebuilt_prop(None, a, s, r, "keep") for r in (1, 2)) for s in sets), 2) for a in ("TE", "TER")},
        "drop_truncated_pairs": len(keepset), "drop_truncated_sets": len({s for s, _ in keepset}),
        "drop_truncated_TE_vs_TER": rebuilt_comp("TE", "TER", "asrun", keep=keepset),
        "drop_truncated_keep_TE_vs_TER": rebuilt_comp("TE", "TER", "keep", keep=keepset),
    }
    # 只看送出的行：TE 與 TER 每行改對率（as-run 與 keep）
    for a in ("TE", "TER"):
        sentL = [x for s, r in pairs for x in LB[(s, r, a)] if x["sent_back"]]
        te[a]["sent_wrong_or_missing_before"] = sum(x["before_status"] != "correct" for x in sentL)
        te[a]["sent_fixed"] = sum(x["before_status"] != "correct" and x["after_status"] == "correct" for x in sentL)
    R["item4_TE_TER"] = te

    # ── 項目 5：次要分析（只用紀錄挑初稿）──
    sec = {}
    picks = {"record": [], "random_expect": [], "oracle": [], "fewest_blanks": [], "record_minus_random": {}, "blank_minus_random": {}}
    agree = 0
    for s in sets:
        drafts = []
        for r in (1, 2):
            c = C[(s, r, "A")]
            L = LB[(s, r, "A")]
            n = len(L)
            flagged = sum(x["c0_flagged"] for x in L)  # 紀錄算的標記（缺值或讀過的內容裡找不到）
            blanks = n - c["c0_filled"]  # 空白：看報告本身就知道，不需要答案
            score = (n - flagged) - flagged
            drafts.append({"rep": r, "score": score, "blanks": blanks, "prop": c["c0_correct"] / n})
        rec = sorted(drafts, key=lambda d: (-d["score"], d["blanks"], d["rep"]))[0]
        fb = sorted(drafts, key=lambda d: (d["blanks"], d["rep"]))[0]
        fb_tie = drafts[0]["blanks"] == drafts[1]["blanks"]
        rnd = statistics.fmean(d["prop"] for d in drafts)
        fbv = rnd if fb_tie else fb["prop"]  # 空白一樣多 ⇒ 隨機（期望值）
        picks["record"].append(rec["prop"])
        picks["random_expect"].append(rnd)
        picks["oracle"].append(max(d["prop"] for d in drafts))
        picks["fewest_blanks"].append(fbv)
        picks["record_minus_random"][s] = rec["prop"] - rnd
        picks["blank_minus_random"][s] = fbv - rnd
        if not fb_tie and rec["rep"] == fb["rep"]:
            agree += 1
    sec["record_pick_pct"] = round(100 * statistics.fmean(picks["record"]), 2)
    sec["random_expect_pct"] = round(100 * statistics.fmean(picks["random_expect"]), 2)
    sec["oracle_pct"] = round(100 * statistics.fmean(picks["oracle"]), 2)
    sec["fewest_blanks_pct"] = round(100 * statistics.fmean(picks["fewest_blanks"]), 2)
    sec["record_minus_random"] = cluster_summary(picks["record_minus_random"])
    sec["fewest_blanks_minus_random"] = cluster_summary(picks["blank_minus_random"])
    sec["record_minus_fewest_blanks"] = cluster_summary({s: picks["record_minus_random"][s] - picks["blank_minus_random"][s] for s in sets})
    sec["sets_where_blanks_differ_and_record_pick_equals_fewest_blank_pick"] = agree
    sec["sets_where_blank_counts_differ"] = sum(1 for s in sets if C[(s, 1, "A")]["c0_filled"] != C[(s, 2, "A")]["c0_filled"])
    R["item5_secondary"] = sec

    # ── 項目 6：fb-s11/r1、撞埠時窗 ──
    k = ("fb-s11", 1)
    order = sorted((C[(*k, a)]["ts"], a, C[(*k, a)]["extra_wall_s"], C[(*k, a)]["final_report_sha256"][:12]) for a in ARMS)
    keep_no11 = set(pairs) - {k}
    R["item6"] = {
        "fb_s11_r1_completion_order": order,
        "fb_s11_r1_A_vs_c0_lines": integ["A_lines_status_changed"].get("fb-s11/r1"),
        "excluding_fb_s11_r1": {f"{t}_vs_{c}": comp(t, c, keep=keep_no11) for t, c in COMPS[:4]},
        "excluding_fb_s11_r1_pairweighted": {f"{t}_vs_{c}": comp_pairweighted(t, c, keep_no11) for t, c in COMPS[:4]},
        "full_pairweighted": {f"{t}_vs_{c}": comp_pairweighted(t, c, set(pairs)) for t, c in COMPS[:4]},
        "excluding_fb_s10_r1_port_collision": {f"{t}_vs_{c}": comp(t, c, keep=set(pairs) - {("fb-s10", 1)}) for t, c in COMPS[:4]},
        "fb_s10_r1_cells": {a: f'{C[("fb-s10", 1, a)]["final_correct"]}/{C[("fb-s10", 1, a)]["n_lines"]}' for a in ARMS},
    }
    # 撞埠：2026-11-28T00:36Z 前後 lms1003q9 在跑的格（開始≈完成−該臂自己的牆鐘）
    import datetime as dt

    def ts(x: str) -> float:
        return dt.datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp()
    t0 = ts("2026-11-28T00:36:00Z")
    run_at = []
    for c in cells:
        if c["host"] != "lms1003q9":
            continue
        end = ts(c["ts"])
        start = end - (c["extra_wall_s"] or 0) - 0
        if start - 120 <= t0 + 60 and end >= t0 - 60:
            run_at.append((c["set"], c["rep"], c["arm"], c["ts"], c["extra_wall_s"]))
    last_1003 = max(c["ts"] for c in cells if c["host"] == "lms1003q9")
    last_1004 = max(c["ts"] for c in cells if c["host"] == "lms1004q9")
    after = [(c["set"], c["rep"], c["arm"], c["ts"]) for c in cells if ts(c["ts"]) >= t0 - 60]
    R["item6"]["port_collision"] = {"window_utc": "2026-11-28T00:35–00:37Z", "cells_running_on_1003_near_window": run_at,
                                    "cells_completed_at_or_after_00_35Z": after, "last_ts_1003": last_1003, "last_ts_1004": last_1004}

    # ── 越界（待新包）：最壞情況排除界 ──
    # 對方說越界在 TO 25、G 11、TB 6、T 4 次 agent 執行（449 次）。稽核包沒有 agent 紀錄，定位不了；
    # 這裡做對 T 最不利的排除：把 T−X 差最大的 k 對整對拿掉（k＝兩臂越界次數上限，假設每次越界落在不同對）。
    rounds = {a: sum(C[(s, r, a)]["rounds_run"] for s, r in pairs) for a in ("G", "T", "TB", "TO")}
    agent_runs = len(pairs) + sum(rounds.values())

    def worst_case(t: str, c: str, kx: int) -> dict:
        eligible = [(s, r) for s, r in pairs if C[(s, r, t)]["rounds_run"] > 0 or C[(s, r, c)]["rounds_run"] > 0]
        ranked = sorted(eligible, key=lambda p: -(prop(C[(*p, t)]) - prop(C[(*p, c)])))
        drop = set(ranked[:kx])
        return {"k_pairs_dropped": kx, "dropped": [f"{s}/r{r}" for s, r in sorted(drop)], **comp(t, c, keep=set(pairs) - drop)}

    def worst_case_t_only(t: str, c: str, kx: int) -> dict:
        """只有 t 臂的越界算對 t 有利：在 t 臂有跑回合的配對裡，拿掉 t−c 最大的 kx 對。"""
        eligible = [(s, r) for s, r in pairs if C[(s, r, t)]["rounds_run"] > 0]
        ranked = sorted(eligible, key=lambda p: -(prop(C[(*p, t)]) - prop(C[(*p, c)])))
        drop = set(ranked[:kx])
        return {"k_pairs_dropped": kx, "dropped": [f"{s}/r{r}" for s, r in sorted(drop)], **comp(t, c, keep=set(pairs) - drop)}

    def min_k_flip(t: str, c: str, thr: float) -> dict:
        ranked = sorted(pairs, key=lambda p: -(prop(C[(*p, t)]) - prop(C[(*p, c)])))
        for kx in range(0, 20):
            r_ = comp(t, c, keep=set(pairs) - set(ranked[:kx]))
            if not (r_["diff"] >= thr and r_["boot95"][0] > 0):
                return {"k": kx, "dropped": [f"{s}/r{r}" for s, r in ranked[:kx]], **r_}
        return {"k": None}

    def drop_favorable(t: str, c: str, kx: int, favor: str, ran: str) -> dict:
        """在 ran 臂有跑回合的配對裡，拿掉對 favor 臂最有利的 kx 對（favor＝c 時是 t−c 最小的）。"""
        eligible = [(s, r) for s, r in pairs if C[(s, r, ran)]["rounds_run"] > 0]
        sign = -1 if favor == t else 1
        ranked = sorted(eligible, key=lambda p: sign * (prop(C[(*p, t)]) - prop(C[(*p, c)])))
        drop = set(ranked[:kx])
        return {"k_pairs_dropped": kx, "eligible": len(eligible), "dropped": [f"{s}/r{r}" for s, r in sorted(drop)], **comp(t, c, keep=set(pairs) - drop)}

    R["out_of_bounds_bounds"] = {
        "T_vs_TB_drop_top6_TB_favorable": drop_favorable("T", "TB", 6, "TB", "TB"),
        "T_vs_G_drop_top11_G_favorable": drop_favorable("T", "G", 11, "G", "G"),
        "T_vs_TO_drop_top25_TO_favorable": drop_favorable("T", "TO", 25, "TO", "TO"),
        "T_vs_TO_drop_top25_T_favorable_among_TO_ran": drop_favorable("T", "TO", 25, "T", "TO"),
        "T_vs_G_drop_top4_T_favorable": worst_case_t_only("T", "G", 4),
        "T_vs_TB_drop_top4_T_favorable": worst_case_t_only("T", "TB", 4),
        "T_vs_G_min_pairs_to_lose_pass": min_k_flip("T", "G", 10.0),
        "agent_runs_recount": {"c0": len(pairs), **rounds, "total": agent_runs},
        "note": "稽核包沒有工具呼叫紀錄 ⇒ 46／8 對不上也否證不了；下面是最壞情況界",
        "T_vs_G_drop_top15": worst_case("T", "G", 15),
        "T_vs_TB_drop_top10": worst_case("T", "TB", 10),
        "T_vs_TO_drop_top29": worst_case("T", "TO", 29),
    }

    # ── 鏈：串接驗證 ──
    anchors = {(a["set"], a["rep"], a["arm"]): a for a in src.json("expT/expT_chain_anchors.json")}
    files = src.chain_files()
    bad = []
    ev_by_arm = collections.Counter()
    types_by_arm: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for name, (nd, pub) in files.items():
        s, r, a = name.split("__")
        key = (s, int(r[1:]), a)
        ents = [json.loads(x) for x in nd.splitlines() if x.strip()]
        pubj = json.loads(pub)
        an = anchors.get(key)
        prob = []
        if an is None:
            prob.append("no_anchor")
        else:
            if an["pub_hex"] != pubj["pub_hex"]:
                prob.append("pub")
            if an["events"] != len(ents):
                prob.append("events")
            if not an.get("verify_chain"):
                prob.append("verify_chain_false")
        z = "0" * 64
        for i, e in enumerate(ents):
            if e["seq"] != i + 1:
                prob.append(f"seq{i}")
            if i == 0:
                if e["prev_hash"] != z or e["stream_id"] != z:
                    prob.append("genesis")
            else:
                if e["prev_hash"] != ents[i - 1]["entry_hash"]:
                    prob.append(f"link{i}")
                if e["stream_id"] != ents[0]["entry_hash"]:
                    prob.append(f"stream{i}")
                if e["ts_ms"] < ents[i - 1]["ts_ms"]:
                    prob.append(f"ts{i}")
        if ents and an:
            if an["head"] != ents[-1]["entry_hash"]:
                prob.append("head")
            if an["stream_id"] != ents[0]["entry_hash"]:
                prob.append("anchor_stream")
        if len({e["sig"] for e in ents}) != len(ents):
            prob.append("dup_sig")
        ev_by_arm[a] += len(ents)
        for e in ents:
            types_by_arm[a][e["type"]] += 1
        if prob:
            bad.append((name, prob[:5]))
    pubs = collections.Counter(json.loads(p)["pub_hex"] for _, p in files.values())
    import datetime as dt2
    lag = []
    for name, (nd, _) in files.items():
        s, r, a = name.split("__")
        ents = [json.loads(x) for x in nd.splitlines() if x.strip()]
        cell_end = dt2.datetime.fromisoformat(C[(s, int(r[1:]), a)]["ts"].replace("Z", "+00:00")).timestamp()
        lag.append(cell_end - ents[-1]["ts_ms"] / 1000)
    # 每格回饋事件數 vs 輪數
    fb_vs_rounds = collections.Counter()
    for name, (nd, _) in files.items():
        s, r, a = name.split("__")
        n_fb = sum(1 for x in nd.splitlines() if x.strip() and json.loads(x)["type"] == "EXPT_FEEDBACK")
        fb_vs_rounds[(a, C[(s, int(r[1:]), a)]["rounds_run"], n_fb)] += 1
    R["chains"] = {"files": len(files), "anchors": len(anchors), "linkage_problems": bad[:20], "linkage_problem_count": len(bad),
                   "cell_ts_minus_last_event_s": {"min": round(min(lag), 1), "median": round(statistics.median(lag), 1), "max": round(max(lag), 1)},
                   "distinct_pubkeys": len(pubs), "max_cells_per_pubkey": max(pubs.values()),
                   "events_by_arm": dict(ev_by_arm), "types_by_arm": {a: dict(v) for a, v in types_by_arm.items()},
                   "feedback_events_vs_rounds": sorted([list(k) + [v] for k, v in fb_vs_rounds.items()]),
                   "not_verifiable_here": "entry_hash 與 Ed25519 簽章都覆蓋 payload 原文；公開檔只有 payload_sha256 ⇒ 只驗串接"}
    return R


def compare_expT(R: dict, src: Src) -> list[dict]:
    """拿對方輸出比對；只列差異 > 容差的。"""
    theirs = src.json("expT/expT_metrics.json")
    sens = src.json("expT/expT_te_sensitivity_nonprereg.json")
    out = []

    def chk(label: str, mine: float, their: float, tol: float) -> None:
        out.append({"item": label, "mine": mine, "theirs": their, "ok": abs(mine - their) <= tol})

    for a in ARMS:
        ba = theirs["by_arm"][a]
        chk(f"{a} (a) set-mean pct", R["by_arm"][a]["a_setmean_pct"], 100 * ba["correct_line_proportion_per_set"], 0.06)
        chk(f"{a} C->W/D", R["by_arm"][a]["harm_c2w_or_d"], ba["harm"]["correct_to_wrong_or_deleted"], 0)
        chk(f"{a} B->W", R["by_arm"][a]["harm_b2w"], ba["harm"]["blank_to_wrong"], 0)
        chk(f"{a} (b) filled precision per-set pct", R["by_arm"][a]["b_filled_precision_setmean_pct"], 100 * ba["filled_precision_per_set"], 0.06)
    for name, c in theirs["comparisons"].items():
        if name in R["comparisons"]:
            mine = R["comparisons"][name]["a"]
            chk(f"{name} diff pp", mine["diff"], 100 * c["per_set_correct_prop_diff"], 0.06)
            chk(f"{name} CI low pp (boot, different seed/B)", mine["boot95"][0], 100 * c["per_set_correct_prop_diff_ci95"][0], 1.0)
            chk(f"{name} CI high pp (boot, different seed/B)", mine["boot95"][1], 100 * c["per_set_correct_prop_diff_ci95"][1], 1.0)
            chk(f"{name} filled-precision diff pp", R["comparisons"][name]["b_filled_precision"]["diff"], 100 * c["per_set_filled_precision_diff"], 0.06)
    sec = theirs["secondary_offline_draft_selection"]
    chk("secondary record pick pct", R["item5_secondary"]["record_pick_pct"], 100 * sec["record_pick_correct_prop"], 0.06)
    chk("secondary random pick pct (mine=expectation)", R["item5_secondary"]["random_expect_pct"], 100 * sec["random_pick_correct_prop"], 0.06)
    chk("secondary oracle pct", R["item5_secondary"]["oracle_pct"], 100 * sec["oracle_best_correct_prop"], 0.06)
    s = R["item4_TE_TER"]["sensitivity_auditor"]
    chk("keep_on_null TE-TER pp (mine set-mean vs theirs pooled)", s["keep_on_null_TE_vs_TER"]["diff"], sens["keep_on_null"]["TE_minus_TER_pp"][0], 0.6)
    chk("keep_on_null TE harm C->W/D", s["keep_on_null_harm_c2w"]["TE"], sens["keep_on_null"]["TE"]["harm_c2w_or_d"], 0)
    chk("keep_on_null TER harm C->W/D", s["keep_on_null_harm_c2w"]["TER"], sens["keep_on_null"]["TER"]["harm_c2w_or_d"], 0)
    return out


# ───────────────────────────── exam37 ─────────────────────────────
def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def exam37(src: Src) -> dict:
    cells = src.json("exam37/exam37_part1_cells.json") + src.json("exam37/exam37_part2_cells.json")
    C = {(c["task"], c["rep"], c["arm"]): c for c in cells}
    arms = ["A", "N3", "GT", "XM", "PB", "XMT", "XMV"]
    tasks = sorted({c["task"] for c in cells})
    R: dict[str, Any] = {"cells": len(cells), "tasks": len(tasks), "cells_per_arm": dict(collections.Counter(c["arm"] for c in cells)),
                         "infra_void": sum(bool(c.get("infra_void")) for c in cells)}
    per = {}
    for a in arms:
        cs = [c for c in cells if c["arm"] == a and not c.get("infra_void")]
        succ = sum(bool(c["hidden_pass"]) for c in cs)
        gated = a not in ("A", "N3")
        acc = [c for c in cs if c["accepted"]]
        fa = [c for c in acc if not c["hidden_pass"]]
        # 誤擋（格）：某次嘗試能過隱藏評分卻被閘門退回
        fb_cells = 0
        fb_att = 0
        atts = 0
        hid_pass_atts = 0
        for c in cs:
            hit = False
            for t in c["attempts"]:
                atts += 1
                if t["hidden_pass"]:
                    hid_pass_atts += 1
                if gated and t["hidden_pass"] and not (t["acc_status"] == "ok" and t["acc_passed"] is not None and
                                                      _accepted_attempt(t, a)):
                    # 被退回：有下一次嘗試，或是最後一次但沒放行
                    fb_att += 1
                    hit = True
            fb_cells += hit
        per[a] = {"cells": len(cs), "success": succ, "rate_pct": round(100 * succ / len(cs), 2),
                  "accepted": len(acc) if gated else None, "false_accept_cells": len(fa) if gated else None,
                  "fa_rate_all_cells_pct": round(100 * len(fa) / len(cs), 2) if gated else None,
                  "fa_rate_among_accepted_pct": round(100 * len(fa) / len(acc), 2) if gated and acc else None,
                  "false_block_cells": fb_cells if gated else None,
                  "fb_cell_rate_pct": round(100 * fb_cells / len(cs), 2) if gated else None,
                  "false_block_attempts": fb_att if gated else None, "attempts": atts,
                  "fb_among_hidden_pass_attempts_pct": round(100 * fb_att / hid_pass_atts, 2) if gated and hid_pass_atts else None,
                  "mean_tokens": round(statistics.fmean(c["tokens_total"] for c in cs)),
                  "accepted_by_last_attempt_inconsistency": sum(1 for c in cs if gated and c["accepted"] and not _accepted_attempt(c["attempts"][c["delivered_attempt"] - 1], a))}
    R["per_arm"] = per
    gt, n3 = per["GT"]["success"] / per["GT"]["cells"], per["N3"]["success"] / per["N3"]["cells"]
    R["gt_minus_n3_pp"] = round(100 * (gt - n3), 2)
    gs = {}
    for a in arms:
        r = per[a]["success"] / per[a]["cells"]
        gs[a] = round((r - n3) / (gt - n3), 3)
    R["gain_share_rates"] = gs
    # 配對版增益比例：只用該臂有的 (題, 次)，N3 與 GT 也限同一批
    gsp = {}
    for a in arms:
        keys = [(t, r) for t in tasks for r in (1, 2) if (t, r, a) in C and (t, r, "N3") in C and (t, r, "GT") in C]
        sa = sum(C[(t, r, a)]["hidden_pass"] for t, r in keys)
        sn = sum(C[(t, r, "N3")]["hidden_pass"] for t, r in keys)
        sg = sum(C[(t, r, "GT")]["hidden_pass"] for t, r in keys)
        gsp[a] = {"pairs": len(keys), "arm": sa, "N3": sn, "GT": sg, "gain_share": round((sa - sn) / (sg - sn), 3) if sg != sn else None}
    R["gain_share_matched"] = gsp
    qual = {}
    gtfa = per["GT"]["fa_rate_all_cells_pct"]
    gtfa_acc = per["GT"]["fa_rate_among_accepted_pct"]
    for a in ("XM", "PB", "XMT", "XMV"):
        qual[a] = {"gain_share": gs[a], "fa_all": per[a]["fa_rate_all_cells_pct"], "limit_all": round(2 * gtfa, 2),
                   "qualifies_all_cells": gs[a] >= 0.5 and per[a]["fa_rate_all_cells_pct"] <= 2 * gtfa,
                   "fa_among_accepted": per[a]["fa_rate_among_accepted_pct"], "limit_among_accepted": round(2 * gtfa_acc, 2),
                   "qualifies_among_accepted": gs[a] >= 0.5 and per[a]["fa_rate_among_accepted_pct"] <= 2 * gtfa_acc}
    R["qualification"] = qual
    mc = {}
    for ctrl in ("N3", "A"):
        for a in arms:
            if a == ctrl:
                continue
            keys = [(t, r) for t in tasks for r in (1, 2) if (t, r, a) in C and (t, r, ctrl) in C]
            b = sum(1 for k in keys if C[(*k, ctrl)]["hidden_pass"] and not C[(*k, a)]["hidden_pass"])
            c_ = sum(1 for k in keys if C[(*k, a)]["hidden_pass"] and not C[(*k, ctrl)]["hidden_pass"])
            mc[f"{a}_vs_{ctrl}"] = {"pairs": len(keys), "b_ctrl_only": b, "c_arm_only": c_, "delta_pp": round(100 * (c_ - b) / len(keys), 2),
                                    "p": round(mcnemar_exact(b, c_), 4)}
    R["mcnemar"] = mc
    # 以題為群集的 GT−N3 區間（兩次重複相關）
    d = {}
    for t in tasks:
        v = [C[(t, r, "GT")]["hidden_pass"] - C[(t, r, "N3")]["hidden_pass"] for r in (1, 2)]
        d[t] = statistics.fmean(v)
    R["GT_minus_N3_task_cluster"] = cluster_summary(d)
    # 增益比例的 bootstrap（以題為群集）：PB 與 XM
    rng = random.Random(BOOT_SEED)
    bs = {a: [] for a in ("XM", "PB", "XMT", "XMV")}
    undefined = 0
    for _ in range(BOOT):
        pick = [rng.choice(tasks) for _ in tasks]
        sn = sum(C[(t, r, "N3")]["hidden_pass"] for t in pick for r in (1, 2))
        sg = sum(C[(t, r, "GT")]["hidden_pass"] for t in pick for r in (1, 2))
        if sg <= sn:
            undefined += 1
            continue
        for a in bs:
            ks = [(t, r) for t in pick for r in (1, 2) if (t, r, a) in C]
            sa = sum(C[(t, r, a)]["hidden_pass"] for t, r in ks) / len(ks)
            bs[a].append((sa - sn / (2 * len(pick))) / (sg / (2 * len(pick)) - sn / (2 * len(pick))))
    R["gain_share_bootstrap"] = {"draws_with_GT_le_N3_pct": round(100 * undefined / BOOT, 1),
                                 **{a: {"p2.5": round(sorted(v)[int(0.025 * len(v))], 2), "median": round(statistics.median(v), 2),
                                        "p97.5": round(sorted(v)[int(0.975 * len(v)) - 1], 2), "share_ge_0.5_pct": round(100 * sum(x >= 0.5 for x in v) / len(v), 1)}
                                    for a, v in bs.items()}}
    # 越界掃描檔
    R["leak_scan"] = {"part1": src.json("exam37/exam37_colab_e4b_part1_20261127T131909Z_n11.json"),
                      "part2": src.json("exam37/exam37_colab_e4b_part2_20261127T121517Z_n8.json")}
    R["leak_scan_attempts_recount"] = {"part1_attempts": sum(len(c["attempts"]) for c in cells if c["batch"].endswith("part1")),
                                       "part2_attempts": sum(len(c["attempts"]) for c in cells if c["batch"].endswith("part2"))}
    R["run_windows"] = {b: [min(c["started"] for c in cells if c["batch"] == b), max(c["ended"] for c in cells if c["batch"] == b)]
                        for b in sorted({c["batch"] for c in cells})}
    return R


def _accepted_attempt(t: dict, arm: str) -> bool:
    """嘗試是否被閘門放行：嚴格臂要全過；XMT 是通過比例 ≥0.85。load_error／逾時／0 測試不放行。"""
    if t.get("acc_status") != "ok" or not t.get("acc_total"):
        return False
    if arm == "XMT":
        return t["acc_passed"] / t["acc_total"] >= 0.85
    return t["acc_passed"] == t["acc_total"]


def compare_exam(R: dict, src: Src) -> list[dict]:
    th = src.json("exam37/exam37_metrics.json")
    out = []
    for a, m in R["per_arm"].items():
        ta = th["per_arm"][a]
        out.append({"item": f"{a} success", "mine": m["success"], "theirs": ta["hidden_pass"], "ok": m["success"] == ta["hidden_pass"]})
        if m["false_accept_cells"] is not None:
            out.append({"item": f"{a} FA cells", "mine": m["false_accept_cells"], "theirs": ta["false_accept_cells"], "ok": m["false_accept_cells"] == ta["false_accept_cells"]})
            out.append({"item": f"{a} FB cells", "mine": m["false_block_cells"], "theirs": ta["false_block_cells"], "ok": m["false_block_cells"] == ta["false_block_cells"]})
            out.append({"item": f"{a} FB attempts", "mine": m["false_block_attempts"], "theirs": ta["false_block_attempts"], "ok": m["false_block_attempts"] == ta["false_block_attempts"]})
        out.append({"item": f"{a} gain share", "mine": R["gain_share_rates"][a], "theirs": ta.get("gain_share"),
                    "ok": ta.get("gain_share") is None or abs(R["gain_share_rates"][a] - ta["gain_share"]) < 0.002})
    for k, v in R["mcnemar"].items():
        a, ctrl = k.split("_vs_")
        tv = (th["paired_vs_N3"] if ctrl == "N3" else th["paired_vs_A"]).get(a)
        if tv:
            tp = tv.get("mcnemar_exact_p")
            out.append({"item": f"McNemar {k} p", "mine": v["p"], "theirs": tp, "ok": tp is not None and abs(v["p"] - tp) < 0.001})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rev", default="3b60ef24a")
    ap.add_argument("--dir")
    ap.add_argument("--out", default=DEFAULT_OUT)
    a = ap.parse_args()
    repo = pathlib.Path(__file__).resolve().parents[3]
    src = Src(None if a.dir else a.rev, a.dir, repo)
    out: dict[str, Any] = {"schema": "vacant.audit.expT_exam37_recompute/1", "source": a.dir or f"git:{a.rev}:{PKG}",
                           "method": {"boot": BOOT, "boot_seed": BOOT_SEED, "perm": PERM, "cluster": "set (expT) / task (exam37)"}}
    out["expT"] = expT(src)
    out["expT_vs_theirs"] = compare_expT(out["expT"], src)
    out["exam37"] = exam37(src)
    out["exam37_vs_theirs"] = compare_exam(out["exam37"], src)
    out["mismatches"] = [x for x in out["expT_vs_theirs"] + out["exam37_vs_theirs"] if not x["ok"]]
    p = repo / a.out
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=list) + "\n")
    print(json.dumps({"mismatches": out["mismatches"], "out": a.out}, ensure_ascii=False, indent=1, default=list))


if __name__ == "__main__":
    sys.exit(main())
