#!/usr/bin/env python3
"""獨立重算核對（2026-11-28，只用標準函式庫、不叫模型、不 import consensus_offline.py）。

核對對象：ops/redo/analysis/consensus_offline.py 的輸出（確認批次 30 組 x 5 份初稿）。
這支做三件事，且**只讀 repo 裡已提交的資料**：
 (1) 從逐份資料（v4_b61.json selector.all.per_draft：每份的 filled／filled_correct／blank_count／evidence_score）
     重算 A、record、nonblank、最好的一份（oracle），k=5 與 k=3，含組群集 bootstrap；
 (2) 用 efamily_per_draft_pools.jsonl 重算紀錄旗標（E 家族定義）當交叉比對；
 (3) 對「逐行多數決、逐行 oracle、一致度旗標」只能做內部一致性檢查——
     這三項需要每組每行 5 份初稿的值（或同一把鍵的 HMAC），提交的資料裡**沒有**
     （expT_lines*.jsonl 只有 r1、r2；r3–r5 逐行資料不在 git）。腳本把這點明寫進輸出，不假裝重算。
用法：consensus_recompute.py <repo_or_worktree_root> --out DIR
"""
from __future__ import annotations
import argparse, collections, json, pathlib, random, statistics

SEED, NB = 20261128, 2000
AUD = "ops/redo/audit"


def boot(vals):
    """以組為群集：重抽組（每組一個差值），取均值；百分位區間。種子寫死。"""
    rng = random.Random(SEED)
    n = len(vals)
    bs = sorted(sum(vals[rng.randrange(n)] for _ in range(n)) / n for _ in range(NB))
    return [round(bs[int(0.025 * NB)], 4), round(bs[int(0.975 * NB) - 1], 4)]


def load(root):
    r = pathlib.Path(root)
    v4 = json.loads((r / AUD / "expTc_20261128/expTc_confirm_analysis_20261128_v4_b61.json").read_text())
    pools = [json.loads(l) for l in (r / AUD / "expTc_20261128/efamily/efamily_per_draft_pools.jsonl").read_text().splitlines()]
    rep = json.loads((r / AUD / "consensus_20261128/consensus_offline.json").read_text())
    return v4["selector"]["all"]["per_draft"], pools, rep


def selectors(per_draft, K):
    by = collections.defaultdict(list)
    for d in per_draft:
        if d["rep"] <= K:
            by[d["set"]].append(d)
    out = {}
    for s, ds in sorted(by.items()):
        if len(ds) < K:
            continue
        prop = lambda d: d["filled_correct"] / d["n_claims"]
        rec = max(ds, key=lambda d: (int(d["evidence_score"]), -int(d["blank_count"]), -int(d["rep"])))
        nb = max(ds, key=lambda d: (int(d["n_claims"]) - int(d["blank_count"]), -int(d["rep"])))
        out[s] = {"A": statistics.mean(prop(d) for d in ds), "record": prop(rec), "nonblank": prop(nb),
                  "oracle": max(prop(d) for d in ds)}
    return out


def pairs(per, a, b):
    vals = [v[a] - v[b] for _, v in sorted(per.items())]
    return {"mean": round(sum(vals) / len(vals), 4), "ci95": boot(vals), "sets": len(vals)}


def int_solutions(N, er, fs, ei, eo, rc):
    """由報告的四位小數反推整數 (W 錯行, F 旗標行, FW 旗標內錯)；回傳所有同時吻合者。"""
    r4 = lambda a, b: round(a / b, 4) if b else None
    sol = []
    for W in range(N + 1):
        if r4(W, N) != er:
            continue
        for F in range(N + 1):
            if r4(F, N) != fs:
                continue
            for FW in range(min(F, W) + 1):
                if r4(FW, F) == ei and r4(W - FW, N - F) == eo and r4(FW, W) == rc:
                    sol.append((W, F, FW))
    return sol


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("root"); ap.add_argument("--out", required=True); a = ap.parse_args()
    per_draft, pools, rep = load(a.root)
    res = {"note": "只用已提交資料；逐行多數決／逐行 oracle／一致度旗標無法由提交資料重算（見 not_recomputable）。",
           "seed": SEED, "bootstrap": f"組群集，{NB} 次，percentile [int(.025*B), int(.975*B)-1]", "recomputed": {}, "vs_reported": []}
    cmpl = lambda name, mine, theirs: res["vs_reported"].append(
        {"item": name, "recomputed": mine, "reported": theirs, "match": (mine == theirs), "diff": None if mine is None or theirs is None or isinstance(mine, list) else round(mine - theirs, 4)})
    for K in (5, 3):
        per = selectors(per_draft, K)
        means = {m: round(statistics.mean(v[m] for v in per.values()), 4) for m in ("A", "record", "nonblank", "oracle")}
        dom = {d: {m: round(statistics.mean(v[m] for s, v in per.items() if s.startswith(p)), 4) for m in means}
               for d, p in (("companies", "cc"), ("football", "ff"))}
        cm = {f"{x}_vs_{y}": pairs(per, x, y) for x, y in (("record", "A"), ("nonblank", "A"), ("record", "nonblank"), ("oracle", "record"))}
        res["recomputed"][f"k{K}"] = {"sets": len(per), "means": means, "by_domain": dom, "comparisons": cm}
        R = rep["k"][str(K)]
        for m in means:
            cmpl(f"k{K} mean {m}", means[m], R["means"]["A" if m == "A" else m])
        for d in dom:
            for m in means:
                cmpl(f"k{K} {d} {m}", dom[d][m], R["by_domain_means"][d][m])
    # 與 v4 selector 區塊的 record_vs_random／record_vs_nonblank（他們的選擇器分析，bootstrap 實作可能不同）
    # 一致度數字內部一致性：由報告的比例反推整數計數，檢查是否存在同時吻合的整數解
    res["flag_internal_consistency"] = {}
    fl = rep["flags_k5_filled_lines"]
    pd_dom = {"companies": "cc", "football": "ff", "all": ""}
    for d, p in pd_dom.items():
        filled = sum(x["filled"] for x in per_draft if x["set"].startswith(p))
        wrong = filled - sum(x["filled_correct"] for x in per_draft if x["set"].startswith(p))
        f = fl[d]
        ent = {"filled_from_per_draft": filled, "filled_reported": f["filled_lines"], "filled_match": filled == f["filled_lines"],
               "error_rate_from_per_draft": round(wrong / filled, 4), "error_rate_reported": f["error_rate"],
               "error_rate_match": round(wrong / filled, 4) == f["error_rate"],
               "filled_diff": filled - f["filled_lines"],
               "wrong_from_per_draft": wrong, "wrong_implied_by_reported": round(f["error_rate"] * f["filled_lines"]),
               "wrong_diff": wrong - round(f["error_rate"] * f["filled_lines"]),
               "diff_all_wrong_lines": (filled - f["filled_lines"]) == (wrong - round(f["error_rate"] * f["filled_lines"]))}
        for kind in ("consensus", "record"):
            g = f[kind]
            s = int_solutions(f["filled_lines"], f["error_rate"], g["flagged_share"], g["err_in"], g["err_out"], g["recall"])
            ent[kind] = {"integer_solutions(W,F,FW)": s, "coherent": len(s) >= 1}
        res["flag_internal_consistency"][d] = ent
    # 交叉比對：E 家族定義的紀錄旗標（er_flagged_filled），不同於 flags_v2 定義，數字預期接近但不相同
    ef = {}
    for d, p in pd_dom.items():
        q = [x for x in pools if x["set"].startswith(p)]
        F = sum(x["er_flagged_filled"] for x in q); FW = sum(x["er_flagged_filled_wrong"] for x in q)
        U = sum(x["unflagged_filled"] for x in q); UW = sum(x["unflagged_filled_wrong"] for x in q)
        ef[d] = {"filled": F + U, "err_in": round(FW / F, 4), "err_out": round(UW / U, 4), "recall": round(FW / (FW + UW), 4),
                 "flagged_share": round(F / (F + U), 4)}
    res["efamily_record_flag_crosscheck"] = ef
    res["not_recomputable"] = {
        "reason": "逐行多數決、逐行 oracle、一致度旗標都要每組每行 5 份初稿的（canon_strict）值或 HMAC；git 裡只有 r1、r2 的逐行 HMAC（expT_lines_hmac.jsonl，且 before_matches_k 比的是教材修訂，不是初稿之間），"
                  "r3–r5 只有每份的彙總（filled、filled_correct、evidence_score、旗標池計數）。初稿根目錄與 flags_v2.json 不在 git。",
        "items": ["majority", "line_oracle", "majority_vs_*", "consensus flag err_in/err_out/recall", "flag overlap", "tie/blank variants"]}
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / "consensus_recompute.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    bad = [r for r in res["vs_reported"] if not r["match"]]
    print("recomputed items:", len(res["vs_reported"]), "mismatch:", len(bad))
    for r in bad:
        print(r)
    print(json.dumps(res["recomputed"]["k5"]["comparisons"], ensure_ascii=False))
    print(json.dumps(res["flag_internal_consistency"], ensure_ascii=False))
    print(json.dumps(ef, ensure_ascii=False))


if __name__ == "__main__":
    main()
