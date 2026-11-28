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

補核（0dd266544）：讀新包的 `expT_escape_calls.jsonl` 自己判定越界的對，重算排除後的比較（`escape_review`）。

名單核對（2e99dd9a1）：`list_v2_review` 讀新名單 `expT_escape_v2_runs.jsonl`、`expT_hmac_supplement/`（HMAC，只比相等）。

用法：python3 ops/redo/analysis/expT_exam37_audit_recompute.py [--rev 3b60ef24a --escape-rev 0dd266544 --list-rev 2e99dd9a1 | --dir D] [--out J]
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import pathlib
import random
import re
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

    def jsonl_rel(self, repo_rel: str) -> list[dict]:
        """以 repo 根為基準的路徑（給稽核包以外的子目錄，例如 expT_hmac_supplement）。"""
        if self.dir is not None:
            t = (self.dir.parent / pathlib.Path(repo_rel).relative_to(PKG).as_posix()).read_text() if repo_rel.startswith(PKG) else (self.dir / repo_rel).read_text()
        else:
            t = subprocess.run(["git", "-C", str(self.repo), "show", f"{self.rev}:{repo_rel}"], check=True, capture_output=True).stdout.decode()
        return [json.loads(x) for x in t.splitlines() if x.strip()]

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


# ───────────────────────────── 補核：越界（0dd266544）─────────────────────────────
STRONG_B = {"pair_flags", "other_flags", "mat_future", "mat_answer"}  # 對方 (b) 的定義


def escape_review(src: Src, esc_calls: list[dict], their_summary: dict) -> dict:
    """用逐筆越界紀錄自己判定排除集合，重算四個預註冊比較；和對方 (a)／(b) 對照，再加兩個版本：
    (b′)＝(b)＋讀了同一對別臂（非 c0／A）產出的對＋被別格寫入的對；以及各版本再拿掉 13 份空白初稿。"""
    cells = src.json("expT/expT_cells.json")
    C = {(c["set"], c["rep"], c["arm"]): c for c in cells}
    pairs = sorted({(c["set"], c["rep"]) for c in cells})
    R: dict[str, Any] = {}

    def prop(c: dict) -> float:
        return c["final_correct"] / c["n_lines"]

    def comp(t: str, c: str, keep: set) -> dict:
        d: dict[str, list[float]] = collections.defaultdict(list)
        for s, r in pairs:
            if (s, r) in keep:
                d[s].append(prop(C[(s, r, t)]) - prop(C[(s, r, c)]))
        out = cluster_summary({k: statistics.fmean(v) for k, v in d.items()})
        out["pairs"] = sum(len(v) for v in d.values())
        return out

    runs: dict[tuple, set] = collections.defaultdict(set)
    for x in esc_calls:
        runs[(x["set"], x["rep"], x["arm"], x["round"])].add(x["kind"])
    R["calls"] = len(esc_calls)
    R["kinds"] = dict(collections.Counter(x["kind"] for x in esc_calls))
    R["tools"] = dict(collections.Counter(x["tool"] for x in esc_calls))
    R["runs_with_escape"] = len(runs)
    R["runs_by_arm"] = dict(collections.Counter(k[2] for k in runs))
    R["runs_by_round"] = dict(collections.Counter(k[3] for k in runs))
    R["c0_runs"] = sum(1 for k in runs if k[3] == "c0")
    R["writes"] = [x for x in esc_calls if x["tool"] == "write"]
    R["cross_arm_reads"] = [x for x in esc_calls if x["kind"] in ("pair_other", "other_cell")]
    excl_a = {(k[0], k[1]) for k in runs}
    excl_b = {(k[0], k[1]) for k, v in runs.items() if v & STRONG_B}
    extra = set()
    for x in esc_calls:
        if x["kind"] == "pair_other":
            tarm = x["detail"].split("/")[2]
            if tarm not in ("c0", "A"):
                extra.add((x["set"], x["rep"]))
        if x["tool"] == "write":
            ts_, tr_ = x["detail"].split("/")[:2]
            extra.add((ts_, int(tr_[1:])))
    excl_bp = excl_b | extra
    R["excluded"] = {"a": len(excl_a), "b": len(excl_b), "b_prime": len(excl_bp),
                     "b_prime_added": sorted(f"{s}/r{r}" for s, r in excl_bp - excl_b),
                     "match_theirs_a": sorted(map(tuple, their_summary["excluded_pairs_a"])) == sorted(excl_a),
                     "match_theirs_b": sorted(map(tuple, their_summary["excluded_pairs_b"])) == sorted(excl_b),
                     "by_arm_a": dict(collections.Counter(k[2] for k in runs)),
                     "by_arm_b": dict(collections.Counter(k[2] for k, v in runs.items() if v & STRONG_B))}
    empty = {(s, r) for s, r in pairs if C[(s, r, "A")]["c0_filled"] == 0}
    watch = [("fb-s01", 1), ("fb-s06", 2)]
    R["watch_pairs"] = {f"{s}/r{r}": {"in_a": (s, r) in excl_a, "in_b": (s, r) in excl_b,
                                      "escapes": sorted([k[2], k[3], sorted(v)] for k, v in runs.items() if (k[0], k[1]) == (s, r))}
                        for s, r in watch}
    R["empty_c0_in_a"] = sorted(f"{s}/r{r}" for s, r in empty & excl_a)
    R["empty_c0_in_b"] = sorted(f"{s}/r{r}" for s, r in empty & excl_b)
    R["T_escape_runs"] = sorted([k[0], k[1], k[3], sorted(v)] for k, v in runs.items() if k[2] == "T")
    versions = {"all": set(pairs), "a": set(pairs) - excl_a, "b": set(pairs) - excl_b, "b_prime": set(pairs) - excl_bp,
                "a_minus_empty": set(pairs) - excl_a - empty, "b_minus_empty": set(pairs) - excl_b - empty,
                "b_prime_minus_empty": set(pairs) - excl_bp - empty}
    COMPS = [("T", "G"), ("T", "TB"), ("T", "TO"), ("TE", "TER"), ("T", "A"), ("G", "A"), ("TB", "A"), ("TO", "A")]
    R["comparisons"] = {v: {f"{t}_vs_{c}": comp(t, c, keep) for t, c in COMPS} for v, keep in versions.items()}
    # (b) 版本下，拿掉幾對 T 最有利的就不過
    for v in ("b", "b_prime"):
        keep = versions[v]
        ranked = sorted(keep, key=lambda p: -(prop(C[(*p, "T")]) - prop(C[(*p, "G")])))
        for kx in range(0, 25):
            r_ = comp("T", "G", keep - set(ranked[:kx]))
            if not (r_["diff"] >= 10 and r_["boot95"][0] > 0):
                R[f"T_vs_G_{v}_min_pairs_to_lose_pass"] = {"k": kx, "dropped": [f"{s}/r{r}" for s, r in ranked[:kx]], **r_}
                break
        top = ranked[:5]
        R[f"T_vs_G_{v}_top5_pairs"] = [(f"{s}/r{r}", round(100 * (prop(C[(s, r, "T")]) - prop(C[(s, r, "G")])), 1),
                                        C[(s, r, "A")]["c0_filled"]) for s, r in top]
    # 被排除的對是不是隨機的：比初稿與各臂特性（描述）
    def describe(keys: set) -> dict:
        ks = sorted(keys)
        return {"pairs": len(ks),
                "c0_correct_prop_mean": round(100 * statistics.fmean(C[(*k, "A")]["c0_correct"] / C[(*k, "A")]["n_lines"] for k in ks), 1),
                "c0_empty": sum(k in empty for k in ks),
                "fb_share": round(sum(k[0].startswith("fb") for k in ks) / len(ks), 2),
                "T_rounds_mean": round(statistics.fmean(C[(*k, "T")]["rounds_run"] for k in ks), 2),
                "TO_rounds_mean": round(statistics.fmean(C[(*k, "TO")]["rounds_run"] for k in ks), 2),
                "c0_flagged_mean": round(statistics.fmean(C[(*k, "A")]["c0_flagged"] for k in ks), 1),
                "host_1003_share": round(sum(C[(*k, "A")]["host"] == "lms1003q9" for k in ks) / len(ks), 2),
                **{f"{a}_final_prop_mean": round(100 * statistics.fmean(prop(C[(*k, a)]) for k in ks), 1) for a in ("A", "G", "T", "TB", "TO")}}
    R["selection"] = {"excluded_a": describe(excl_a), "kept_a": describe(set(pairs) - excl_a),
                      "excluded_b": describe(excl_b), "kept_b": describe(set(pairs) - excl_b)}
    # 同一格自己有越界時，該臂在該對的成績 vs 沒越界的對（描述）
    arm_esc = collections.defaultdict(set)
    for k in runs:
        arm_esc[k[2]].add((k[0], k[1]))
    own = {}
    for a in ("G", "T", "TB", "TO"):
        e = arm_esc[a]
        if e:
            own[a] = {"pairs_with_own_escape": len(e),
                      "arm_minus_A_on_those_pp": round(100 * statistics.fmean(prop(C[(*k, a)]) - prop(C[(*k, "A")]) for k in e), 1),
                      "arm_minus_A_elsewhere_pp": round(100 * statistics.fmean(prop(C[(*k, a)]) - prop(C[(*k, "A")]) for k in set(pairs) - e), 1),
                      "rounds_on_those": round(statistics.fmean(C[(*k, a)]["rounds_run"] for k in e), 2),
                      "rounds_elsewhere_where_ran": round(statistics.fmean([C[(*k, a)]["rounds_run"] for k in set(pairs) - e if C[(*k, a)]["rounds_run"] > 0] or [0]), 2)}
    R["own_escape_vs_arm_result"] = own
    # 他們的數字
    th = their_summary["sensitivity"]
    cmp_ = []
    for v_m, v_t in (("all", "all"), ("a", "a_exclude_any_escape_pairs"), ("b", "b_exclude_flags_future_pairs")):
        for name, x in th[v_t].items():
            if name in R["comparisons"][v_m]:
                mine = R["comparisons"][v_m][name]
                cmp_.append({"version": v_m, "comp": name, "mine": [mine["diff"], *mine["boot95"]],
                             "theirs": [round(100 * x["per_set_correct_prop_diff"], 2)] + [round(100 * y, 2) for y in x["per_set_correct_prop_diff_ci95"]],
                             "pairs_mine": mine["pairs"], "pairs_theirs": x["paired_cells"],
                             "ok_point": abs(mine["diff"] - 100 * x["per_set_correct_prop_diff"]) <= 0.06})
    R["vs_theirs"] = cmp_
    return R


# ───────────────────────────── 補掃：越界擴大＋未來值對照 ─────────────────────────────
HAIKU_MARKER_SHA = hashlib.sha256(b"not found in sources").hexdigest()  # TE/TER 寫回時唯一會出現的字串


def extra_scans(src: Src, esc_calls: list[dict], base_keep_bprime: set) -> dict:
    """(1) 擴大越界掃描：包裡只有原正規式命中的 422 筆、沒有指令原文 ⇒ 路徑類別逐一說明判斷不了；
    改用「資料指紋」找沒被路徑掃描抓到的跨臂抄寫：Haiku 寫回標記字串出現在 agent 臂、整份報告位元相同、
    TB 動到有值的行。(2) 未來值對照：包裡沒有後續修訂真值 ⇒ 只能給上界（新寫進且判錯的行），並列缺檔規格。"""
    cells = src.json("expT/expT_cells.json")
    lines = src.jsonl("expT/expT_lines.jsonl")
    C = {(c["set"], c["rep"], c["arm"]): c for c in cells}
    pairs = sorted({(c["set"], c["rep"]) for c in cells})
    LB: dict[tuple, list[dict]] = collections.defaultdict(list)
    for x in lines:
        LB[(x["set"], x["rep"], x["arm"])].append(x)
    R: dict[str, Any] = {}
    R["escape_record_fields"] = sorted({k for x in esc_calls for k in x})
    R["escape_detail_shapes"] = dict(collections.Counter(
        "/".join("<set>" if re.fullmatch(r"(sc|fb)-s\d+", t) else "<rep>" if re.fullmatch(r"r\d", t) else
                 "<realrev>" if t.startswith("realrev") else "<sNN>" if re.fullmatch(r"s\d+", t) else t
                 for t in x["detail"].split("/")) for x in esc_calls))
    agent = ["G", "T", "TB", "TO"]
    # 指紋 1：Haiku 寫回標記出現在 agent 臂
    R["haiku_marker_in_agent_arms"] = [
        {"cell": f"{s}/r{r}/{a}", "lines": n} for (s, r, a), n in sorted(collections.Counter(
            (x["set"], x["rep"], x["arm"]) for x in lines if x["arm"] in agent and x["after_value_sha256"] == HAIKU_MARKER_SHA).items())]
    # 指紋 2：整份報告位元相同（排除和 c0 相同、以及全對——全對時照模板寫的報告本來就會相同）
    same = []
    for s, r in pairs:
        for i, x in enumerate(agent + ["TE", "TER"]):
            for y in (agent + ["TE", "TER"])[i + 1:]:
                if x in ("TE", "TER") and y in ("TE", "TER"):
                    continue
                cx, cy = C[(s, r, x)], C[(s, r, y)]
                if cx["final_report_sha256"] == cy["final_report_sha256"] != cx["c0_report_sha256"]:
                    import datetime as _dt
                    end = {a: _dt.datetime.fromisoformat(C[(s, r, a)]["ts"].replace("Z", "+00:00")).timestamp() for a in (x, y)}
                    start = {a: end[a] - (C[(s, r, a)]["extra_wall_s"] or 0) for a in (x, y)}
                    same.append({"pair": f"{s}/r{r}", "arms": [x, y], "all_correct": cx["final_correct"] == cx["n_lines"],
                                 "correct": f'{cx["final_correct"]}/{cx["n_lines"]}',
                                 "later_started_after_other_ended": (start[y] >= end[x]) or (start[x] >= end[y])})
    R["identical_reports"] = same
    R["identical_reports_not_all_correct"] = [z for z in same if not z["all_correct"]]
    # 指紋 3：TB 只被告知空白行；動到有值的行 ⇒ 可能有別的資訊
    R["TB_changed_valued_lines"] = {f"{s}/r{r}": n for (s, r), n in sorted(collections.Counter(
        (x["set"], x["rep"]) for x in lines if x["arm"] == "TB" and x["before_status"] != "missing"
        and x["after_value_sha256"] != x["before_value_sha256"]).items())}
    # 讀 flags.json 的那幾次：當時那份初稿的 flags 有沒有比「空白行」多的資訊
    fl = []
    for x in esc_calls:
        if x["kind"] in ("pair_flags", "other_flags"):
            ts_, tr_ = x["detail"].split("/")[:2]
            src_pair = (ts_, int(tr_[1:]))
            A = C[(*src_pair, "A")]
            fl.append({"reader": f'{x["set"]}/r{x["rep"]}/{x["arm"]}/{x["round"]}', "flags_of": f"{ts_}/{tr_}",
                       "flags_of_c0_empty": A["c0_filled"] == 0,
                       "valued_flagged_lines": sum(1 for z in LB[(*src_pair, "A")] if z["c0_flagged"] and z["before_status"] != "missing")})
    R["flags_reads"] = list({json.dumps(z, sort_keys=True): z for z in fl}.values())
    # 可疑但定不了的對（不是全對、而且後跑的那一臂開始於先跑的結束之後）加進 (b′) 再算 T−G
    susp = {tuple([z["pair"].split("/")[0], int(z["pair"].split("/")[1][1:])]) for z in R["identical_reports_not_all_correct"]}

    def prop(c: dict) -> float:
        return c["final_correct"] / c["n_lines"]

    def comp(t: str, c: str, keep: set) -> dict:
        d: dict[str, list[float]] = collections.defaultdict(list)
        for s, r in pairs:
            if (s, r) in keep:
                d[s].append(prop(C[(s, r, t)]) - prop(C[(s, r, c)]))
        out = cluster_summary({k: statistics.fmean(v) for k, v in d.items()})
        out["pairs"] = sum(len(v) for v in d.values())
        return out
    keep2 = base_keep_bprime - susp
    R["b_prime_plus_fingerprint_pairs"] = {"added": sorted(f"{s}/r{r}" for s, r in susp & base_keep_bprime),
                                           **{f"{t}_vs_{c}": comp(t, c, keep2) for t, c in (("T", "G"), ("T", "TB"), ("T", "TO"), ("TE", "TER"))}}
    # (2) 未來值對照：上界
    fut_calls = collections.Counter((x["set"], x["rep"], x["arm"]) for x in esc_calls if x["kind"] == "mat_future")
    own_any = {(x["set"], x["rep"], x["arm"]) for x in esc_calls}

    def ub(keys: list[tuple]) -> dict:
        new_wrong = sum(1 for k in keys for z in LB[k] if z["after_status"] == "wrong" and z["after_value_sha256"] != z["before_value_sha256"])
        all_wrong = sum(1 for k in keys for z in LB[k] if z["after_status"] == "wrong")
        n = sum(len(LB[k]) for k in keys)
        return {"cells": len(keys), "lines": n, "upper_bound_new_wrong": new_wrong, "upper_bound_all_wrong": all_wrong,
                "new_wrong_per_100_lines": round(100 * new_wrong / n, 2) if n else None}
    tab = {}
    for a in agent:
        ks = [(s, r, a) for s, r in pairs]
        tab[a] = {"read_future": ub([k for k in ks if k in fut_calls]),
                  "other_escape": ub([k for k in ks if k in own_any and k not in fut_calls]),
                  "no_escape": ub([k for k in ks if k not in own_any])}
    R["future_upper_bound_by_arm"] = tab
    R["future_read_cells"] = [{"cell": f"{s}/r{r}/{a}", "mat_future_calls": n,
                               "final": f'{C[(s, r, a)]["final_correct"]}/{C[(s, r, a)]["n_lines"]}',
                               "new_wrong_lines": sum(1 for z in LB[(s, r, a)] if z["after_status"] == "wrong" and z["after_value_sha256"] != z["before_value_sha256"]),
                               "c0_correct": C[(s, r, a)]["c0_correct"]}
                              for (s, r, a), n in sorted(fut_calls.items())]
    R["future_read_calls_total"] = sum(fut_calls.values())
    # 上界對主比較的影響：假設讀過未來頁面的格裡「新寫進且判錯」的行全部是未來值、本來會是對的，
    # 那一臂的 (a) 最多少算多少（組平均：每對權重 1/(該組對數×組數)）
    nsets = len({s for s, _ in pairs})
    bound = collections.defaultdict(float)
    for (s, r, a), _n in fut_calls.items():
        nw = sum(1 for z in LB[(s, r, a)] if z["after_status"] == "wrong" and z["after_value_sha256"] != z["before_value_sha256"])
        bound[a] += 100 * nw / C[(s, r, a)]["n_lines"] / 2 / nsets
    R["future_max_effect_on_arm_a_pp"] = {a: round(v, 2) for a, v in bound.items()}
    R["missing_for_exact_future_check"] = {
        "file": "expT_future_truth.jsonl（或在 expT_lines.jsonl 加欄）",
        "fields_per_set_claim_revision": ["set", "claim_id", "k（0..K，與教材 cycle_k 對應）", "truth_canon_sha256＝sha256(canon_strict(truth_k))"],
        "fields_per_line": ["after_canon_sha256＝sha256(canon_strict(after_value))（現有 after_value_sha256 是原字串的雜湊，評分卻用 canon_strict，直接比會漏掉格式不同的同值）",
                            "（或直接給）after_matches_k：canon_strict 相符的修訂編號清單"],
        "already_implemented": "auto/redo 的 ops/d2/expTc_confirm_analysis.py score_fb() 已有同一算法（future_truth_match_lines），可直接用在探索 root 匯出逐行旗標",
    }
    return R


# ───────────────────────────── 補掃二：直連外網（等執行方名單）─────────────────────────────
def network_fingerprint(src: Src, esc_calls: list[dict], bprime_excl: set) -> dict:
    """包裡沒有工具呼叫參數 ⇒ 掃不了網址。改用 c0 的資料指紋找「來源沒被 egress 記到」的初稿：
    有值的行幾乎全被紀錄標成『讀過的內容裡找不到』（≥80%）——若值來自 https 直連（不經代理、不進 egress），
    紀錄就會這樣標。這只是候選名單，不是越界判定（也可能是那一格的 egress 紀錄缺漏）。"""
    cells = src.json("expT/expT_cells.json")
    lines = src.jsonl("expT/expT_lines.jsonl")
    hk = {(h["set"], h["rep"]): h for h in src.jsonl("expT/expT_haiku.jsonl") if h["arm"] == "TE"}
    C = {(c["set"], c["rep"], c["arm"]): c for c in cells}
    pairs = sorted({(c["set"], c["rep"]) for c in cells})
    LB: dict[tuple, list[dict]] = collections.defaultdict(list)
    for x in lines:
        LB[(x["set"], x["rep"], x["arm"])].append(x)
    rows, cand = [], set()
    ratio_hist = collections.Counter()
    for s, r in pairs:
        A = LB[(s, r, "A")]
        V = [x for x in A if x["before_status"] != "missing"]
        FV = [x for x in V if x["c0_flagged"]]
        if V:
            ratio_hist[round(len(FV) / len(V), 1)] += 1
        if V and len(FV) / len(V) >= 0.8:
            cand.add((s, r))
            rows.append({"pair": f"{s}/r{r}", "valued": len(V), "valued_flagged": len(FV),
                         "flagged_but_correct": sum(x["before_status"] == "correct" for x in FV),
                         "flagged_and_wrong_fabricated": sum(x["before_status"] == "wrong" and x["before_etype"] == "fabricated" for x in FV),
                         "pages_in_egress_for_c0": hk[(s, r)]["fetched_pages"] if (s, r) in hk and hk[(s, r)]["called"] else None,
                         "T_c2w": C[(s, r, "T")]["harm_c2w_or_d"]})
    R: dict[str, Any] = {"c0_flag_ratio_hist": dict(sorted(ratio_hist.items())), "candidates": rows, "n": len(cand),
                         "share_of_flagged_correct_lines": round(sum(z["flagged_but_correct"] for z in rows) / 312, 3),
                         "T_c2w_in_candidates": sum(z["T_c2w"] for z in rows), "T_c2w_total": sum(C[(s, r, "T")]["harm_c2w_or_d"] for s, r in pairs),
                         "fabricated_in_candidates": sum(z["flagged_and_wrong_fabricated"] for z in rows)}

    def prop(c: dict) -> float:
        return c["final_correct"] / c["n_lines"]

    def comp(t: str, c: str, keep: set) -> dict:
        d: dict[str, list[float]] = collections.defaultdict(list)
        for s_, r_ in pairs:
            if (s_, r_) in keep:
                d[s_].append(prop(C[(s_, r_, t)]) - prop(C[(s_, r_, c)]))
        out = cluster_summary({k: statistics.fmean(v) for k, v in d.items()})
        out["pairs"] = sum(len(v) for v in d.values())
        return out
    empty = {(s, r) for s, r in pairs if C[(s, r, "A")]["c0_filled"] == 0}
    allp = set(pairs)
    vers = {"all_minus_fp": allp - cand, "b_prime_minus_fp": allp - bprime_excl - cand,
            "b_prime_minus_fp_minus_empty": allp - bprime_excl - cand - empty, "only_fp": cand}
    R["comparisons"] = {v: {f"{t}_vs_{c}": comp(t, c, k) for t, c in (("T", "G"), ("T", "TB"), ("T", "TO"), ("TE", "TER"), ("T", "A"))}
                        for v, k in vers.items()}
    R["fp_in_b_prime_excluded"] = sorted(f"{s}/r{r}" for s, r in cand & bprime_excl)
    R["c0_path_escapes_in_0dd266544"] = sum(1 for x in esc_calls if x["round"] == "c0")
    # 回饋輪寫進的「捏造」值（錯、而且不在第 0 修訂任何頁面裡）＝線上現行版本值的候選上界；分臂（逐輪做不了：包裡只有最終值）
    own_any = {(x["set"], x["rep"], x["arm"]) for x in esc_calls}
    fab = {}
    for a in ("G", "T", "TB", "TO"):
        ks = [(s, r, a) for s, r in pairs]
        ran = [k for k in ks if C[k]["rounds_run"] > 0]

        def cnt(keys: list) -> int:
            return sum(1 for k in keys for z in LB[k] if z["after_etype"] == "fabricated" and z["after_value_sha256"] != z["before_value_sha256"])
        fab[a] = {"cells_with_rounds": len(ran), "rounds_total": sum(C[k]["rounds_run"] for k in ks),
                  "new_fabricated_lines": cnt(ran),
                  "new_fabricated_in_path_escape_cells": cnt([k for k in ran if k in own_any]),
                  "new_fabricated_in_other_cells": cnt([k for k in ran if k not in own_any]),
                  "cells_with_ge3_new_fabricated": sorted(f"{k[0]}/r{k[1]}" for k in ran if cnt([k]) >= 3)}
    R["feedback_new_fabricated_by_arm"] = fab
    return R


# ───────────────────────────── 名單核對（2e99dd9a1）─────────────────────────────
def list_v2_review(src_old: Src, src_new: Src, esc_old: list[dict]) -> dict:
    """新名單（expT_escape_v2_runs.jsonl，108 次）對我的名單（舊路徑命中 45 次 ∪ 網路紀錄裡非本對來源主機的指令）；
    直連分「指令」與「回傳像 HTML」；用新名單重算 (a)(b)(b′)＋拿掉空白初稿；HMAC 匯出做未來值對照（只比相等，不碰值）。"""
    cells = src_old.json("expT/expT_cells.json")
    lines = src_old.jsonl("expT/expT_lines.jsonl")
    C = {(c["set"], c["rep"], c["arm"]): c for c in cells}
    pairs = sorted({(c["set"], c["rep"]) for c in cells})
    LB: dict[tuple, list[dict]] = collections.defaultdict(list)
    for x in lines:
        LB[(x["set"], x["rep"], x["arm"])].append(x)
    V = src_new.jsonl("expT/expT_escape_v2_runs.jsonl")
    N = src_new.jsonl_rel("ops/redo/audit/expT_exam37_20261128/expT_hmac_supplement/expT_net_calls.jsonl")
    LH = src_new.jsonl_rel("ops/redo/audit/expT_exam37_20261128/expT_hmac_supplement/expT_lines_hmac.jsonl")
    TH = src_new.jsonl_rel("ops/redo/audit/expT_exam37_20261128/expT_hmac_supplement/expT_truth_hmac.jsonl")
    key = lambda x: (x["set"], x["rep"], x["arm"], x["round"])  # noqa: E731
    R: dict[str, Any] = {"v2_runs": len(V), "v2_escape_runs": sum(v["escape"] for v in V)}
    R["v2_escape_by_arm_round"] = {f"{a}/{r}": n for (a, r), n in sorted(collections.Counter((v["arm"], v["round"]) for v in V if v["escape"]).items())}
    R["v2_kinds_in_escape_runs"] = dict(collections.Counter(k for v in V if v["escape"] for k in v["escape_kinds"]))
    rule = lambda v: bool(set(v["escape_kinds"]) - {"path_pattern"}) or v["unlogged_server_200"] > 0  # noqa: E731
    R["v2_rule_inferred"] = "escape ⇔ 有 path_pattern 以外的任一類，或 unlogged_server_200>0"
    R["v2_rule_exceptions"] = [list(key(v)) + [sorted(v["escape_kinds"])] for v in V if rule(v) != v["escape"]]
    c0 = [v for v in V if v["round"] == "c0" and v["escape"]]
    R["c0_escape"] = [{"pair": f'{v["set"]}/r{v["rep"]}', "kinds": v["escape_kinds"], "unlogged_server_200": v["unlogged_server_200"],
                       "server_200": v["server_200"]} for v in c0]
    # 我的名單
    old = {key(x) for x in esc_old}
    ext_any = {key(n) for n in N if not n["own_source_host"]}
    mine = old | ext_any
    v2 = {key(v) for v in V if v["escape"]}
    R["mine_runs"] = len(mine)
    R["mine_not_v2"] = sorted(map(list, mine - v2))
    R["v2_not_mine"] = {"runs": len(v2 - mine),
                        "by_kinds": {"+".join(k) or "(none: unlogged_server_200)": n for k, n in collections.Counter(
                            tuple(sorted(set(v["escape_kinds"]) - {"path_pattern"})) for v in V if key(v) in v2 - mine).items()},
                        "by_arm_round": dict(collections.Counter(f"{k[2]}/{k[3]}" for k in v2 - mine))}
    R["old45_subset_of_v2"] = old <= v2
    pv2 = {(k[0], k[1]) for k in v2}
    pmine = {(k[0], k[1]) for k in mine}
    R["pairs"] = {"v2": len(pv2), "mine": len(pmine), "v2_not_mine": sorted(f"{s}/r{r}" for s, r in pv2 - pmine),
                  "mine_not_v2": sorted(f"{s}/r{r}" for s, r in pmine - pv2)}
    # 直連：指令 vs 回傳像 HTML，逐臂逐輪
    ext = [n for n in N if not n["own_source_host"]]
    R["net"] = {"calls_total": len(N), "own_source_host_calls": sum(n["own_source_host"] for n in N),
                "own_source_unmatched": sum(1 for n in N if n["own_source_host"] and not n["matched_egress_or_server"]),
                "external_commands": len(ext),
                "external_commands_matched_server": sum(n["matched_egress_or_server"] for n in ext),
                "external_html_returned": sum(n["output_looks_like_html"] for n in ext),
                "by_host_commands": dict(collections.Counter(n["target_host"] for n in ext).most_common()),
                "by_host_html": dict(collections.Counter(n["target_host"] for n in ext if n["output_looks_like_html"]).most_common()),
                "by_arm_round_commands": {f"{a}/{r}": c for (a, r), c in sorted(collections.Counter((n["arm"], n["round"]) for n in ext).items())},
                "by_arm_round_html": {f"{a}/{r}": c for (a, r), c in sorted(collections.Counter((n["arm"], n["round"]) for n in ext if n["output_looks_like_html"]).items())},
                "runs_with_external_command": len({key(n) for n in ext}),
                "runs_with_external_html": sorted(map(list, {key(n) for n in ext if n["output_looks_like_html"]})),
                "command_class": dict(collections.Counter(n["command_class"] for n in ext)),
                "c0_external": sum(1 for n in ext if n["round"] == "c0")}
    # 重算排除版本
    def prop(c: dict) -> float:
        return c["final_correct"] / c["n_lines"]

    def comp(t: str, c: str, keep: set) -> dict:
        d: dict[str, list[float]] = collections.defaultdict(list)
        for s_, r_ in pairs:
            if (s_, r_) in keep:
                d[s_].append(prop(C[(s_, r_, t)]) - prop(C[(s_, r_, c)]))
        out = cluster_summary({k: statistics.fmean(v) for k, v in d.items()})
        out["pairs"] = sum(len(v) for v in d.values())
        return out
    empty = {(s, r) for s, r in pairs if C[(s, r, "A")]["c0_filled"] == 0}
    c0pairs = {(v["set"], v["rep"]) for v in c0}
    old_strong = {(x["set"], x["rep"]) for x in esc_old if x["kind"] in STRONG_B}
    ext_pairs = {(n["set"], n["rep"]) for n in ext if not n["matched_egress_or_server"]}
    ext_html_pairs = {(n["set"], n["rep"]) for n in ext if n["output_looks_like_html"]}
    cross = set()
    for x in esc_old:
        if x["kind"] == "pair_other" and x["detail"].split("/")[2] not in ("c0", "A"):
            cross.add((x["set"], x["rep"]))
        if x["tool"] == "write":
            t_, r_ = x["detail"].split("/")[:2]
            cross.add((t_, int(r_[1:])))
    excl = {"a_v2": pv2 | c0pairs,
            "b_v2": old_strong | ext_pairs | c0pairs,
            "b_v2_html_only": old_strong | ext_html_pairs | c0pairs,
            "b_prime_v2": old_strong | ext_pairs | c0pairs | cross}
    R["exclusion_definitions"] = {
        "a_v2": "新名單任一臂任一輪越界的對（含 c0 那一對）",
        "b_v2": "舊 (b)（flags.json／未來頁面／答案）∪ 有直連外站指令（非本對來源主機、沒進伺服器紀錄）的對 ∪ c0 那一對",
        "b_v2_html_only": "同上，但直連只算回傳像 HTML 的",
        "b_prime_v2": "b_v2 ∪ 讀同一對別臂（非 c0／A）產出 ∪ 被別格寫入的對"}
    R["excluded_counts"] = {k: len(v) for k, v in excl.items()}
    vers = {"all": set(pairs)}
    for k, v in excl.items():
        vers[k] = set(pairs) - v
        vers[k + "_minus_empty"] = set(pairs) - v - empty
    COMPS = [("T", "G"), ("T", "TB"), ("T", "TO"), ("TE", "TER"), ("T", "A"), ("TO", "A")]
    R["comparisons"] = {v: {f"{t}_vs_{c}": comp(t, c, k) for t, c in COMPS} for v, k in vers.items()}
    R["T_vs_G_pass_by_version"] = {v: (r["T_vs_G"]["diff"] >= 10 and r["T_vs_G"]["boot95"][0] > 0) for v, r in R["comparisons"].items()}
    R["fb_s10_r2_in_12_football_candidates"] = False  # 候選名單只有 fb-s10/r1（見 network_fingerprint）
    # HMAC 未來值對照
    T = {(t["set"], t["claim"], t["k"]): t["truth_hmac"] for t in TH}
    chk = 0
    for x in LH:
        K = len(x["after_matches_k"])
        calc = [x["after_hmac"] is not None and x["after_hmac"] == T.get((x["set"], x["claim"], k)) for k in range(K)]
        chk += calc != x["after_matches_k"]
    I = {(x["set"], x["rep"], x["arm"], x["claim_id"]): x for x in lines}
    st_mis = sum(1 for x in LH if (I[(x["set"], x["rep"], x["arm"], x["claim"])]["after_status"] == "correct") != x["after_matches_k"][0])
    R["hmac_checks"] = {"lines": len(LH), "revisions_per_claim": dict(collections.Counter(collections.Counter((t["set"], t["claim"]) for t in TH).values())),
                        "after_matches_k_vs_truth_hmac_mismatch": chk, "after_status_correct_vs_k0_mismatch": st_mis,
                        "latest_is_last_k": all(x["after_matches_latest"] == x["after_matches_k"][-1] for x in LH),
                        "note": "after_matches_latest 是教材裡最後一個修訂，不是直連當下的線上版本；線上版本的真值沒有匯出"}
    fut = lambda m: (not m[0]) and any(m[1:])  # noqa: E731
    v2_cell = {(k[0], k[1], k[2]) for k in v2}
    ext_cell = {(n["set"], n["rep"], n["arm"]) for n in ext}
    ext_html_cell = {(n["set"], n["rep"], n["arm"]) for n in ext if n["output_looks_like_html"]}
    fut_cell = {(x["set"], x["rep"], x["arm"]) for x in esc_old if x["kind"] == "mat_future"}
    by = {}
    for a in ["A", "G", "T", "TB", "TO", "TE", "TER"]:
        rows = [x for x in LH if x["arm"] == a]

        def cnt(cond: Callable[[dict], bool]) -> dict:
            rs = [x for x in rows if cond(x)]
            return {"lines": len(rs), "after_future_not_rev0": sum(fut(x["after_matches_k"]) for x in rs),
                    "introduced": sum(fut(x["after_matches_k"]) and not fut(x["before_matches_k"]) and x["after_hmac"] != x["before_hmac"] for x in rs),
                    "before_future_not_rev0": sum(fut(x["before_matches_k"]) for x in rs)}
        ck = lambda x: (x["set"], x["rep"], x["arm"])  # noqa: E731
        by[a] = {"all": cnt(lambda x: True),
                 "v2_escape_cells": cnt(lambda x: ck(x) in v2_cell),
                 "external_command_cells": cnt(lambda x: ck(x) in ext_cell),
                 "external_html_cells": cnt(lambda x: ck(x) in ext_html_cell),
                 "read_future_page_cells": cnt(lambda x: ck(x) in fut_cell),
                 "no_v2_escape_cells": cnt(lambda x: ck(x) not in v2_cell)}
    R["future_match_by_arm"] = by
    # 引入的未來值對 (a) 的影響（組平均，pp）：每對權重 1/(2×組數)
    nsets = len({s for s, _ in pairs})
    eff = {}
    for a in ["G", "T", "TB", "TO", "TE", "TER"]:
        tot = 0.0
        for x in LH:
            if x["arm"] == a and fut(x["after_matches_k"]) and not fut(x["before_matches_k"]) and x["after_hmac"] != x["before_hmac"]:
                tot += 100 / C[(x["set"], x["rep"], a)]["n_lines"] / 2 / nsets
        eff[a] = round(tot, 2)
    R["introduced_future_max_effect_pp"] = eff
    # 各版本：把 G 與 T「引入的未來值」行改算成對（＝假設沒有污染就會寫對），T−G 最多移動多少
    intro = collections.defaultdict(int)
    for x in LH:
        if fut(x["after_matches_k"]) and not fut(x["before_matches_k"]) and x["after_hmac"] != x["before_hmac"]:
            intro[(x["set"], x["rep"], x["arm"])] += 1

    def comp_adj(keep: set, fix_arm: str) -> dict:
        d: dict[str, list[float]] = collections.defaultdict(list)
        for s_, r_ in pairs:
            if (s_, r_) in keep:
                ct = C[(s_, r_, "T")]["final_correct"] + (intro[(s_, r_, "T")] if fix_arm == "T" else 0)
                cg = C[(s_, r_, "G")]["final_correct"] + (intro[(s_, r_, "G")] if fix_arm == "G" else 0)
                d[s_].append((ct - cg) / C[(s_, r_, "T")]["n_lines"])
        return cluster_summary({k: statistics.fmean(v) for k, v in d.items()})
    sig = sorted({(k[0], k[1], k[2]) for k, n in intro.items() if n > 0 and k not in v2_cell})
    R["future_lines_in_cells_without_v2_escape"] = [[f"{a_}/r{b_}/{c_}", intro[(a_, b_, c_)],
                                                     sorted({kk for v in V if (v["set"], v["rep"], v["arm"]) == (a_, b_, c_) for kk in v["escape_kinds"]})]
                                                    for a_, b_, c_ in sig]
    sigp = {(a_, b_) for a_, b_, _ in sig}
    vers["b_prime_v2_plus_future_signature"] = set(pairs) - excl["b_prime_v2"] - sigp
    vers["b_v2_plus_future_signature"] = set(pairs) - excl["b_v2"] - sigp
    for v in ("b_prime_v2_plus_future_signature", "b_v2_plus_future_signature"):
        R["comparisons"][v] = {f"{t}_vs_{c}": comp(t, c, vers[v]) for t, c in COMPS}
        R["T_vs_G_pass_by_version"][v] = R["comparisons"][v]["T_vs_G"]["diff"] >= 10 and R["comparisons"][v]["T_vs_G"]["boot95"][0] > 0
    R["T_vs_G_future_adjusted"] = {v: {"G_fixed_worst_for_T": comp_adj(k, "G"), "T_fixed_best_for_T": comp_adj(k, "T")}
                                   for v, k in vers.items()}
    # 各版本：拿掉 T−G 最大的幾對就不過
    mk = {}
    for v, keep in vers.items():
        ranked = sorted(keep, key=lambda p_: -(prop(C[(*p_, "T")]) - prop(C[(*p_, "G")])))
        for kx in range(0, 15):
            r_ = comp("T", "G", keep - set(ranked[:kx]))
            if not (r_["diff"] >= 10 and r_["boot95"][0] > 0):
                mk[v] = {"k": kx, "dropped": [f"{s_}/r{r_2}" for s_, r_2 in ranked[:kx]], "diff": r_["diff"], "boot95": r_["boot95"]}
                break
    R["T_vs_G_min_pairs_to_lose_pass"] = mk
    R["n_sets_by_version"] = {v: len({s_ for s_, _ in k}) for v, k in vers.items()}
    R["introduced_future_cells"] = sorted(
        [f"{s}/r{r}/{a}", n] for (s, r, a), n in collections.Counter(
            (x["set"], x["rep"], x["arm"]) for x in LH
            if fut(x["after_matches_k"]) and not fut(x["before_matches_k"]) and x["after_hmac"] != x["before_hmac"]).items())
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
    ap.add_argument("--escape-rev", default="0dd266544", help="越界逐筆結果所在的提交（新包）")
    ap.add_argument("--list-rev", default="2e99dd9a1", help="新越界名單＋HMAC 補充匯出所在的提交；空字串跳過")
    a = ap.parse_args()
    repo = pathlib.Path(__file__).resolve().parents[3]
    src = Src(None if a.dir else a.rev, a.dir, repo)
    out: dict[str, Any] = {"schema": "vacant.audit.expT_exam37_recompute/1", "source": a.dir or f"git:{a.rev}:{PKG}",
                           "method": {"boot": BOOT, "boot_seed": BOOT_SEED, "perm": PERM, "cluster": "set (expT) / task (exam37)"}}
    out["expT"] = expT(src)
    out["expT_vs_theirs"] = compare_expT(out["expT"], src)
    out["exam37"] = exam37(src)
    out["exam37_vs_theirs"] = compare_exam(out["exam37"], src)
    esrc = Src(None if a.dir else a.escape_rev, a.dir, repo)
    out["escape_review"] = escape_review(src, esrc.jsonl("expT/expT_escape_calls.jsonl"), esrc.json("expT/expT_escape_summary.json"))
    out["source_escape"] = a.dir or f"git:{a.escape_rev}:{PKG}"
    _cells = src.json("expT/expT_cells.json")
    _pairs = {(c["set"], c["rep"]) for c in _cells}
    _bp = {tuple([p.split("/")[0], int(p.split("/")[1][1:])]) for p in out["escape_review"]["excluded"]["b_prime_added"]}
    _calls = esrc.jsonl("expT/expT_escape_calls.jsonl")
    _b = {(x["set"], x["rep"]) for x in _calls if x["kind"] in STRONG_B}
    _w = set()
    for x in _calls:
        if x["tool"] == "write":
            t_, r_ = x["detail"].split("/")[:2]
            _w.add((t_, int(r_[1:])))
    out["extra_scans"] = extra_scans(src, _calls, _pairs - _b - _bp - _w)
    out["network_fingerprint"] = network_fingerprint(src, _calls, _b | _bp | _w)
    if a.list_rev:
        lsrc = Src(None if a.dir else a.list_rev, a.dir, repo)
        out["list_v2_review"] = list_v2_review(src, lsrc, _calls)
        out["source_list_v2"] = a.dir or f"git:{a.list_rev}"
    out["mismatches"] = [x for x in out["expT_vs_theirs"] + out["exam37_vs_theirs"] if not x["ok"]] + \
        [x for x in out["escape_review"]["vs_theirs"] if not x["ok_point"]]
    p = repo / a.out
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=list) + "\n")
    print(json.dumps({"mismatches": out["mismatches"], "out": a.out}, ensure_ascii=False, indent=1, default=list))


if __name__ == "__main__":
    sys.exit(main())
