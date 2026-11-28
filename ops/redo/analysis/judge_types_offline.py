#!/usr/bin/env python3
"""判定種類 × 分辨力 × 增益：跨批次的事後並列表（非預註冊；稽核用）。

這支在架構裡承重的是「什麼樣的判定值得做」這個問題的資料面：把五種判定
（題目測試、AI 出的考卷、只查空白／有沒有交、紀錄出處比對、零設定缺檔退回）
在現有資料上，用同一組量去描述：
  - Pf：判定之前的失敗率（單位：格或行）；
  - V ：判定看得見的失敗佔全部失敗的比例（＝失敗裡被退回／被標的比例，召回）；
  - 精確度：被退回／被標的裡面真的失敗的比例（1 − 誤收／誤標）；
  - 誤擋：通過的被退回／被標的比例；
  - C ：被退回且真的失敗的，在重來之後變成功的比例（重來的權力 × 修得好的能力）；
  - 傷害：原本成功、被判定的動作弄壞的比例；
  - 增益：該判定的動作帶來的成功率差，附以題（或組）為群集的 bootstrap 95% 區間。
對「重來」型的判定，增益 ≡ Pf·V·C − 傷害（會計恆等式，不是模型）；列出來是為了看哪一個因子卡住。

資料（只讀已存檔）：
  - 題目測試：`ops/redo/audit/acceptance_signal_20261128/acceptance_signal_offline.json`（本 repo）。
  - AI 考卷：`origin/auto/redo` 的 `ops/redo/audit/expT_exam37_20261128/exam37/exam37_part{1,2}_cells.json`。
  - 紀錄出處、只查空白：`origin/auto/redo` 的 `ops/redo/audit/expTc_20261128/expTc_confirm_analysis_20261128_v4_b61.json`
    （回饋四臂逐對、選擇器逐組）與 `efamily/efamily_per_draft_{pools,arm}.jsonl`。
  - 零設定缺檔退回：數字取自 `decisions/conclusions/CONCLUSION_20261002_COLAB_DABSTEP_V37.md`、
    `CONCLUSION_20260928_NOCAP_UNSEEN_U274.md`、`CONCLUSION_20260925_ZERO_CONFIG_DABSTEP.md`（只抄數字，不重算）。
只用標準函式庫。用法：python3 ops/redo/analysis/judge_types_offline.py [--ref origin/auto/redo] [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import random
import subprocess
import sys
from collections import defaultdict

SEED = 20261128
BOOT = 10000


def gshow(ref, path):
    return subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True, check=True).stdout


def pct(xs, q):
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    f = math.floor(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def boot_ratio(groups, rng, n=BOOT):
    """groups：每群集一個 (分子, 分母)；重抽群集，統計量 Σ分子/Σ分母。"""
    est = sum(a for a, _ in groups) / sum(b for _, b in groups)
    reps = []
    k = len(groups)
    for _ in range(n):
        num = den = 0.0
        for _j in range(k):
            a, b = groups[rng.randrange(k)]
            num += a
            den += b
        reps.append(num / den if den else 0.0)
    return round(100 * est, 1), [round(100 * pct(reps, .025), 1), round(100 * pct(reps, .975), 1)]


def boot_mean_of_groups(vals, rng, n=BOOT):
    """vals：每群集一個值（組平均）；群集等權。"""
    est = sum(vals) / len(vals)
    reps = []
    k = len(vals)
    for _ in range(n):
        reps.append(sum(vals[rng.randrange(k)] for _ in range(k)) / k)
    return round(100 * est, 1), [round(100 * pct(reps, .025), 1), round(100 * pct(reps, .975), 1)]


def r3(x):
    return None if x is None else round(x, 3)


# ── 1. 題目測試（五批）──────────────────────────────────────────────────

def tests_rows(acc_json):
    out = []
    for b, R in acc_json["batches"].items():
        s = R["success_sources"]["R"]
        a1 = s["per_attempt"]["1"]
        n = a1["attempts"]
        fails = n - a1["hidden_pass"]
        fa, fr = a1["false_accept"], a1["false_reject"]
        rejected_fail = fails - fa                  # 第 1 次隱藏沒過、可見也沒全過
        p = R["first_vs_final"]["R"]
        conv = p["treat_only"]                      # 第 1 次沒過、最終過
        lost = p["ctrl_only"]
        off = R["offline_three_independent_first_attempts"]
        out.append({
            "judge": "題目測試（可見那一半；R 臂，失敗就重開）", "batch": b, "unit": "格",
            "Pf": r3(fails / n), "V_reject_given_fail": r3(rejected_fail / fails) if fails else None,
            "precision_reject": r3(rejected_fail / (rejected_fail + fr)) if rejected_fail + fr else None,
            "false_accept_given_accepted": a1["false_accept_rate_given_accepted"],
            "false_reject_given_rejected": a1["false_reject_rate_given_rejected"],
            "C_convert_given_rejected_fail": r3(conv / rejected_fail) if rejected_fail else None,
            "harm_rate": r3(lost / n),
            "accounting_pp": round(100 * (conv - lost) / n, 1),
            "gain": {"what": "R 最終 − R 第 1 次（同格配對）", "pp": p["delta_pp"], "ci95_cluster": p["cluster_boot95_pp"],
                     "newcombe95": p["newcombe95_pp"]},
            "gain_selection_equal_cost": {"what": "三臂第 1 次重建：依可見挑 − 隨機取一份", "pp": off["select_minus_random_pp"],
                                          "ci95_cluster": off["select_minus_random_cluster_boot95_pp"],
                                          "ceiling_oracle_minus_random_pp": round(100 * (off["rate_oracle_any_hidden"] - off["rate_random_pick"]), 1)},
        })
    return out


# ── 2. AI 出的考卷（exam37）────────────────────────────────────────────

def exam_rows(ref, rng):
    cells = []
    for part in (1, 2):
        cells += json.loads(gshow(ref, f"ops/redo/audit/expT_exam37_20261128/exam37/exam37_part{part}_cells.json"))
    idx = {(c["task"], c["rep"], c["arm"]): c for c in cells}
    out = []
    names = {"GT": "題目測試（gate_visible，工作區沒有測試）", "XM": "AI 出的考卷 XM", "PB": "性質檢查 PB",
             "XMT": "AI 考卷 XMT（通過比例 ≥0.85 即放行）", "XMV": "AI 考卷 XMV（驗證過的版本）"}
    for arm, label in names.items():
        sc = [c for c in cells if c["arm"] == arm and not c["infra_void"] and c["attempts"]]
        a1 = [c["attempts"][0] for c in sc]

        def acc(a):
            return a["acc_status"] == "ok" and (a["acc_total"] or 0) > 0 and a["acc_passed"] == a["acc_total"]
        # XMT 的放行是通過比例 ≥0.85；用交付格的 accepted 欄位核對第 1 次的放行
        if arm == "XMT":
            def acc(a):  # noqa: F811
                return a["acc_status"] == "ok" and (a["acc_total"] or 0) > 0 and a["acc_passed"] / a["acc_total"] >= 0.85
        n = len(a1)
        fails = sum(1 for a in a1 if not a["hidden_pass"])
        fa = sum(1 for a in a1 if acc(a) and not a["hidden_pass"])
        fr = sum(1 for a in a1 if not acc(a) and a["hidden_pass"])
        accepted = sum(1 for a in a1 if acc(a))
        rej_fail = fails - fa
        conv = sum(1 for c in sc if not c["attempts"][0]["hidden_pass"] and not acc(c["attempts"][0]) and c["hidden_pass"])
        lost = sum(1 for c in sc if c["attempts"][0]["hidden_pass"] and not c["hidden_pass"])
        # 增益 1：最終 − 第 1 次（以題為群集）
        g1 = defaultdict(lambda: [0, 0])
        for c in sc:
            g1[c["task"]][0] += int(bool(c["hidden_pass"])) - int(bool(c["attempts"][0]["hidden_pass"]))
            g1[c["task"]][1] += 1
        e1, ci1 = boot_ratio(list(g1.values()), rng)
        # 增益 2：對 N3（同 (題, 重複) 配對；以題為群集）
        g2 = defaultdict(lambda: [0, 0])
        for c in sc:
            y = idx.get((c["task"], c["rep"], "N3"))
            if y is None or y["infra_void"]:
                continue
            g2[c["task"]][0] += int(bool(c["hidden_pass"])) - int(bool(y["hidden_pass"]))
            g2[c["task"]][1] += 1
        e2, ci2 = boot_ratio(list(g2.values()), rng)
        # 核對：第 1 次推得的放行 vs 交付格 accepted（只對 n_attempts==1 的格）
        chk = sum(1 for c in sc if c["n_attempts"] == 1 and bool(c["accepted"]) != acc(c["attempts"][0]))
        out.append({
            "judge": label, "batch": f"exam37 {arm}", "unit": "格",
            "Pf": r3(fails / n), "V_reject_given_fail": r3(rej_fail / fails) if fails else None,
            "precision_reject": r3(rej_fail / (rej_fail + fr)) if rej_fail + fr else None,
            "false_accept_given_accepted": r3(fa / accepted) if accepted else None,
            "false_reject_given_rejected": r3(fr / (n - accepted)) if n - accepted else None,
            "C_convert_given_rejected_fail": r3(conv / rej_fail) if rej_fail else None,
            "harm_rate": r3(lost / n),
            "accounting_pp": round(100 * (conv - lost) / n, 1),
            "gain": {"what": "最終 − 第 1 次（同格；含失敗回饋的重開）", "pp": e1, "ci95_cluster": ci1},
            "gain_vs_N3": {"what": f"{arm} − N3（同 (題,重複)；N3＝同工作區續做、只給『再檢查』提示）", "pp": e2, "ci95_cluster": ci2},
            "_accept_derivation_mismatch_single_attempt_cells": chk,
        })
    # 對照：N3（沒有判定，同一工作區續做 3 次、只給「再檢查」提示，交最後一次）的最終 − 第 1 次
    sc = [c for c in cells if c["arm"] == "N3" and not c["infra_void"] and c["attempts"]]
    g = defaultdict(lambda: [0, 0])
    for c in sc:
        g[c["task"]][0] += int(bool(c["hidden_pass"])) - int(bool(c["attempts"][0]["hidden_pass"]))
        g[c["task"]][1] += 1
    e, ci = boot_ratio(list(g.values()), rng)
    out.append({"judge": "沒有判定（N3：續做＋『再檢查』提示）", "batch": "exam37 N3", "unit": "格",
                "Pf": r3(sum(1 for c in sc if not c["attempts"][0]["hidden_pass"]) / len(sc)),
                "gain": {"what": "N3 最終 − N3 第 1 次（同格）", "pp": e, "ci95_cluster": ci},
                "first_attempt_pass": sum(1 for c in sc if c["attempts"][0]["hidden_pass"]), "final_pass": sum(1 for c in sc if c["hidden_pass"]),
                "cells": len(sc)})
    return out


# ── 3. 紀錄出處、只查空白（實驗 T 確認批次）────────────────────────────

def expTc_rows(ref, rng, local_json=None):
    d = json.loads(pathlib.Path(local_json).read_text() if local_json else
                   gshow(ref, "ops/redo/audit/expTc_20261128/expTc_confirm_analysis_20261128_v4_b61.json"))
    cells = d["per_pair_arm_cells"]
    out = []
    by = defaultdict(dict)
    for key, c in cells.items():
        s, r, arm = key.split("/")
        by[(s, r)][arm] = c
    for domain, pref in (("全部", ""), ("公司", "cc-"), ("足球", "ff-")):
        for arm, label in (("T", "紀錄出處比對（T：退回沒根據的行＋空白行，附頁面清單）"),
                           ("TB", "只查空白（TB：只退回空白行）"),
                           ("G", "籠統再檢查（G：不指出哪一行）")):
            sent = errs = fixed = wrong_before = lines = harm = loss = 0
            gain_by_set = defaultdict(list)
            for (s, r), arms in by.items():
                if not s.startswith(pref):
                    continue
                x, a = arms.get(arm), arms.get("A")
                if not x or not a or x["infra_void"] or a["infra_void"]:
                    continue
                lines += x["n_claims"]
                wrong_before += x["n_claims"] - x["correct_before"]
                sent += x["sent_back_total"]
                errs += x["sent_back_errors"]
                fixed += x["sent_back_errors_fixed"]
                harm += x["harm_total"]
                loss += x["harm_c2w_or_d"]
                gain_by_set[s].append(x["correct_prop_after"] - a["correct_prop_after"])
            vals = [sum(v) / len(v) for v in gain_by_set.values()]
            if not vals:
                continue
            g, ci = boot_mean_of_groups(vals, rng)
            out.append({
                "judge": label, "batch": f"expTc 回饋（{domain}）", "unit": "行",
                "Pf": r3(wrong_before / lines) if lines else None,
                "V_reject_given_fail": r3(errs / wrong_before) if wrong_before else None,
                "precision_reject": r3(errs / sent) if sent else None,
                "C_convert_given_rejected_fail": r3(fixed / errs) if errs else None,
                "harm_rate": r3(harm / lines) if lines else None,
                "loss_rate_correct_to_wrong_or_deleted": r3(loss / lines) if lines else None,
                "accounting_pp": (round(100 * ((wrong_before / lines) * (errs / wrong_before) * (fixed / errs) - loss / lines), 1)
                                  if lines and wrong_before and errs else None),
                "gain": {"what": f"{arm} − A（組平均正確行比例；以組為群集）", "pp": g, "ci95_cluster": ci, "sets": len(vals)},
                "note": "G 不送行，V／精確度／C 不適用" if arm == "G" else "sent_back_* 為輸出欄位（跨輪合計）",
            })
    # 選擇器
    sel = d["selector"]["all"]["per_set"]
    for name in ("record", "nonblank"):
        g, ci = boot_mean_of_groups([x[name] - x["random"] for x in sel], rng)
        out.append({"judge": "紀錄分數挑初稿" if name == "record" else "只數填了幾行挑初稿", "batch": "expTc 選擇器（30 組 × 5 份）",
                    "unit": "份", "gain": {"what": f"{name} − random（組平均；以組為群集）", "pp": g, "ci95_cluster": ci},
                    "ceiling_oracle_minus_random_pp": round(100 * sum(x["oracle"] - x["random"] for x in sel) / len(sel), 1),
                    "blank_drafts": sum(x["blank_drafts"] for x in sel)})
    g, ci = boot_mean_of_groups([x["record"] - x["nonblank"] for x in sel], rng)
    out.append({"judge": "紀錄分數 − 只數填了幾行", "batch": "expTc 選擇器", "unit": "份",
                "gain": {"what": "record − nonblank", "pp": g, "ci95_cluster": ci}})
    return out


def efamily_rows(ref, rng):
    pools = [json.loads(l) for l in gshow(ref, "ops/redo/audit/expTc_20261128/efamily/efamily_per_draft_pools.jsonl").splitlines() if l.strip()]
    arms = [json.loads(l) for l in gshow(ref, "ops/redo/audit/expTc_20261128/efamily/efamily_per_draft_arm.jsonl").splitlines() if l.strip()]
    out = []
    for domain, pref in (("全部", ""), ("公司", "cc-"), ("足球", "ff-")):
        P = [p for p in pools if p["set"].startswith(pref)]
        ff, ffw = sum(p["er_flagged_filled"] for p in P), sum(p["er_flagged_filled_wrong"] for p in P)
        uf, ufw = sum(p["unflagged_filled"] for p in P), sum(p["unflagged_filled_wrong"] for p in P)
        A = {(x["set"], x["rep"]): x for x in arms if x["arm"] == "A" and x["set"].startswith(pref)}
        blank = sum(x["blank"] for x in A.values())
        lines = sum(x["n_claims"] for x in A.values())
        wrong = sum(x["n_claims"] - x["correct"] for x in A.values())
        row = {"batch": f"expTc E 家族（{domain}；Haiku 依標記重寫）", "unit": "行",
               "Pf": r3(wrong / lines),
               "blank_share_of_wrong": r3(blank / wrong) if wrong else None,
               "flag_precision_filled": r3(ffw / ff) if ff else None,
               "unflagged_filled_wrong_rate": r3(ufw / uf) if uf else None,
               "flag_recall_of_wrong_filled": r3(ffw / (ffw + ufw)) if ffw + ufw else None,
               "enrichment": r3((ffw / ff) / (ufw / uf)) if ff and uf and ufw else None}
        for arm in ("EB", "ER", "EN"):
            X = {(x["set"], x["rep"]): x for x in arms if x["arm"] == arm and x["set"].startswith(pref)}
            byset = defaultdict(list)
            sb = sf = fb = fx = hb = hc = 0
            for k, x in X.items():
                a = A[k]
                byset[k[0]].append((x["correct"] - a["correct"]) / a["n_claims"])
                sb += x["sent_blank"]; sf += x["sent_filled"]; fb += x["fixed_blank"]; fx += x["fixed_filled"]
                hb += x["harm_b2w"]; hc += x["harm_c2w_or_d"]
            g, ci = boot_mean_of_groups([sum(v) / len(v) for v in byset.values()], rng)
            row[arm] = {"gain_vs_A_pp": g, "ci95_cluster": ci, "sent_blank": sb, "sent_filled": sf, "fixed_blank": fb,
                        "fixed_filled": fx, "harm_b2w": hb, "harm_c2w_or_d": hc,
                        "C_blank": r3(fb / sb) if sb else None}
        row["ER_fixed_filled_over_flagged_wrong"] = r3(row["ER"]["fixed_filled"] / ffw) if ffw else None
        out.append(row)
    return out


# ── 4. 零設定缺檔退回（只抄結論檔的數字）────────────────────────────────

ZERO_CONFIG = [
    {"judge": "零設定：說做完卻沒寫要求的檔 ⇒ 退回（v3.7）", "batch": "Colab DABstep 77×3、15 回合（CONCLUSION_20261002_COLAB_DABSTEP_V37）",
     "unit": "格", "A_correct": "97/231", "A_failures": 134, "visible_failures_missing_at_done": 42,
     "V_reject_given_fail": round(42 / 134, 3), "V_among_failures_at_done": round(42 / (42 + 22), 3),
     "false_accept_given_accepted_at_done": round(22 / 119, 3), "false_reject": "0（缺檔不可能是對的）",
     "C": "C37 被退回 43 格，退回後答對 34（含 failed_step 13 次）≈0.79", "harm": "0 次",
     "gain": {"what": "C37 − A（每題平均差；Wilcoxon，預註冊）", "pp": 11.3, "p": 0.0028, "ci95": "取不到（結論只給 p）"}},
    {"judge": "同上（v3.6.1；不設回合上限）", "batch": "u274：100 題 DABstep hard（CONCLUSION_20260928_NOCAP_UNSEEN_U274）",
     "unit": "格", "V_reject_given_fail": "取不到", "C": "缺檔退回 31 跑之後 0 對（一半是模型出錯後被叫回來）",
     "gain": {"what": "C − A", "pp": "9 對 10（答對題數）", "p": 1.0, "ci95": "取不到"}},
    {"judge": "零設定初版（五類退回）", "batch": "DABstep 77 題正式批次（CONCLUSION_20260925_ZERO_CONFIG_DABSTEP；CLAUDE.md）",
     "unit": "格", "false_reject": "8 次退回全是誤報，其中 7 次退回的是對的答案",
     "gain": {"what": "C − A", "pp": "沒有量到差別", "p": "0.21／0.29（gemma／qwen）", "ci95": "取不到"}},
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="origin/auto/redo")
    ap.add_argument("--acc-json", default="ops/redo/audit/acceptance_signal_20261128/acceptance_signal_offline.json")
    ap.add_argument("--out")
    a = ap.parse_args()
    rng = random.Random(SEED)
    acc = json.loads(pathlib.Path(a.acc_json).read_text())
    res = {"schema": "vacant.redo.judge_types_offline/1", "post_hoc": True, "ref": a.ref,
           "ref_commit": subprocess.run(["git", "rev-parse", a.ref], capture_output=True, text=True).stdout.strip(),
           "seed": SEED, "bootstrap": BOOT,
           "tests": tests_rows(acc), "exam37": exam_rows(a.ref, rng), "expTc": expTc_rows(a.ref, rng),
           "efamily": efamily_rows(a.ref, rng), "zero_config": ZERO_CONFIG}
    txt = json.dumps(res, ensure_ascii=False, indent=1)
    if a.out:
        pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(a.out).write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    sys.exit(main())
