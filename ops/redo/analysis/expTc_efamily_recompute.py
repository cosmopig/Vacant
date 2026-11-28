#!/usr/bin/env python3
"""確認批次 E 家族（附錄 C）的獨立重算，另加回饋家族逐行資料對逐格分數的核對。不 import 執行方的碼。

讀：ops/redo/audit/expTc_20261128/efamily/ 的四個匯出檔（無值）；回饋 root 的 expT_lines.jsonl（逐行狀態）；
評分輸出 v4 的 per_pair_arm_cells（核對用）。
算：ER−A、ER−EN（只用 ER 標到有填行的初稿）、ER−EB 的差（組加權）、組層級 bootstrap 95%／90% 區間、組層級符號翻轉 p（雙尾）、
Holm（三個比較一族）；錯誤集中倍數（被標有填行錯誤率 ÷ 沒被標有填行錯誤率）的組群集 bootstrap 區間，全體與公司／足球分開；
C6 兩臂並列、EB 送出的有填行、ER 改對與傷害行數、HP、成本分母。
用法：python3 expTc_efamily_recompute.py EFAMILY_DIR FB1003_LINES FB1004_LINES V4_B61.json --out OUT.json
"""
from __future__ import annotations
import argparse, collections, json, random, statistics

B_N, P_N = 20000, 200000


def jl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def boot_stat(groups: dict, stat, lo, hi, seed=7):
    keys = sorted(groups); rng = random.Random(seed); out = []
    for _ in range(B_N):
        smp = [groups[keys[rng.randrange(len(keys))]] for _ in keys]
        v = stat(smp)
        if v is not None:
            out.append(v)
    out.sort()
    return [round(out[int(lo * len(out))], 4), round(out[int(hi * len(out)) - 1], 4)]


def signflip(vals, seed=11):
    rng = random.Random(seed); obs = abs(sum(vals) / len(vals)); hit = 0
    for _ in range(P_N):
        if abs(sum(v if rng.random() < 0.5 else -v for v in vals) / len(vals)) >= obs - 1e-12:
            hit += 1
    return (hit + 1) / (P_N + 1)


def summarize(by_set, delta):
    sets = sorted(by_set); vals = [statistics.mean(by_set[s]) for s in sets]; m = sum(vals) / len(vals)
    g = {s: v for s, v in zip(sets, vals)}; mean = lambda smp: sum(smp) / len(smp)
    ci90 = boot_stat(g, mean, 0.05, 0.95)
    units = [x for s in sets for x in by_set[s]]
    order = sorted(range(len(vals)), key=lambda i: -vals[i] if m >= 0 else vals[i])[:2]
    v2 = {s: v for i, (s, v) in enumerate(zip(sets, vals)) if i not in order}
    return {"sets": len(sets), "units": len(units), "diff": round(m, 4), "ci95": boot_stat(g, mean, 0.025, 0.975), "ci90": ci90,
            "perm_p": round(signflip(vals), 6), "unit_weighted_diff": round(sum(units) / len(units), 4),
            "equivalent_within_delta": ci90[0] > -delta and ci90[1] < delta,
            "drop_top2_sets": {"dropped": [sets[i] for i in order], "diff": round(sum(v2.values()) / len(v2), 4), "ci95": boot_stat(v2, mean, 0.025, 0.975)}}


def holm(ps):
    it = sorted(ps.items(), key=lambda x: x[1]); m = len(it); out = {}; run = 0.0
    for i, (k, p) in enumerate(it):
        run = max(run, min(1.0, (m - i) * p)); out[k] = round(run, 6)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("edir"); ap.add_argument("l1003"); ap.add_argument("l1004"); ap.add_argument("v4")
    ap.add_argument("--out", required=True); a = ap.parse_args()
    arm = jl(f"{a.edir}/efamily_per_draft_arm.jsonl"); pools = {(x["set"], x["rep"]): x for x in jl(f"{a.edir}/efamily_per_draft_pools.jsonl")}
    hp = jl(f"{a.edir}/efamily_hp_per_set.jsonl"); c9 = jl(f"{a.edir}/efamily_c9_fixed_not_in_pages.jsonl")
    cell = {(x["set"], x["rep"], x["arm"]): x for x in arm}
    drafts = sorted({(x["set"], x["rep"]) for x in arm})
    prop = lambda s, r, ar: cell[(s, r, ar)]["correct"] / cell[(s, r, ar)]["n_claims"]
    res = {"drafts": len(drafts), "sets": len({s for s, _ in drafts})}

    def comp(t, c, keep, delta):
        by = collections.defaultdict(list)
        for (s, r) in drafts:
            if keep(s, r):
                by[s].append(prop(s, r, t) - prop(s, r, c))
        return summarize(by, delta)
    er_filled = lambda s, r: pools[(s, r)]["er_flagged_filled"] > 0
    allk = lambda s, r: True
    main_ = {"ER_vs_A": comp("ER", "A", allk, 0.05), "ER_vs_EN": comp("ER", "EN", er_filled, 0.05), "ER_vs_EB": comp("ER", "EB", allk, 0.05)}
    res["main"] = main_; res["holm"] = holm({k: v["perm_p"] for k, v in main_.items()})
    res["arm_means_set_weighted"] = {ar: round(statistics.mean(statistics.mean(prop(s, r, ar) for (s2, r) in drafts if s2 == s) for s in sorted({d[0] for d in drafts})), 4) for ar in ("A", "EB", "ER", "EN")}
    res["ER_vs_EN_drafts"] = sum(1 for d in drafts if er_filled(*d)); res["ER_vs_EN_sets"] = len({d[0] for d in drafts if er_filled(*d)})
    res["sets_without_ER_filled"] = sorted({d[0] for d in drafts} - {d[0] for d in drafts if er_filled(*d)})
    res["ER_vs_EN_by_domain"] = {dom: comp("ER", "EN", (lambda s, r, dom=dom: er_filled(s, r) and s.startswith(dom)), 0.05) for dom in ("cc", "ff")}
    shortfall = lambda s, r: er_filled(s, r) and pools[(s, r)]["en_sampled_filled"] < pools[(s, r)]["er_flagged_filled"]
    res["ER_vs_EN_exclude_shortfall"] = comp("ER", "EN", lambda s, r: er_filled(s, r) and not shortfall(s, r), 0.05)
    res["EN_shortfall_drafts"] = sum(1 for d in drafts if shortfall(*d))
    res["ER_vs_EN_all150_unit_weighted"] = round(statistics.mean(prop(s, r, "ER") - prop(s, r, "EN") for (s, r) in drafts), 4)
    # 行數
    tot = {ar: collections.Counter() for ar in ("EB", "ER", "EN")}
    for ar in tot:
        for (s, r) in drafts:
            x = cell[(s, r, ar)]
            for k in ("sent_blank", "sent_filled", "fixed_blank", "fixed_filled", "harm_b2w", "harm_c2w_or_d"):
                tot[ar][k] += x.get(k) or 0
            tot[ar]["called"] += bool(x.get("called"))
    res["line_counts"] = {ar: dict(v) for ar, v in tot.items()}
    res["EB_sent_filled_drafts"] = [f"{s}/{r}" for (s, r) in drafts if (cell[(s, r, "EB")].get("sent_filled") or 0) > 0]
    # 錯誤集中倍數（組群集）
    def enrich_stat(smp):
        fw = sum(x[0] for x in smp); f = sum(x[1] for x in smp); uw = sum(x[2] for x in smp); u = sum(x[3] for x in smp)
        return (fw / f) / (uw / u) if f and u and uw else None
    def enrich(dom=None):
        g = collections.defaultdict(lambda: [0, 0, 0, 0])
        for (s, r), p in pools.items():
            if dom and not s.startswith(dom):
                continue
            q = g[s]; q[0] += p["er_flagged_filled_wrong"]; q[1] += p["er_flagged_filled"]; q[2] += p["unflagged_filled_wrong"]; q[3] += p["unflagged_filled"]
        g = {k: tuple(v) for k, v in g.items()}
        fw, f, uw, u = (sum(v[i] for v in g.values()) for i in range(4))
        return {"flagged_filled": f, "flagged_wrong": fw, "flagged_wrong_rate": round(fw / f, 4) if f else None,
                "unflagged_filled": u, "unflagged_wrong": uw, "unflagged_wrong_rate": round(uw / u, 4) if u else None,
                "ratio": round((fw / f) / (uw / u), 3) if f and u and uw else None, "ratio_ci95_set_cluster": boot_stat(g, enrich_stat, 0.025, 0.975),
                "sets": len(g)}
    res["enrichment"] = {"all": enrich(), "company": enrich("cc"), "football": enrich("ff")}
    en_s = sum(p["en_sampled_filled"] for p in pools.values()); en_sw = sum(p["en_sampled_filled_wrong"] for p in pools.values())
    res["EN_sampled"] = {"filled": en_s, "wrong": en_sw, "correct_rate": round(1 - en_sw / en_s, 4)}
    res["ER_fix_rate_on_wrong_filled"] = round(tot["ER"]["fixed_filled"] / res["enrichment"]["all"]["flagged_wrong"], 4)
    res["EN_fix_rate_on_wrong_filled"] = round(tot["EN"]["fixed_filled"] / en_sw, 4)
    # HP
    res["HP"] = {"sets": len(hp), "mean_correct_prop": round(statistics.mean(x["correct"] / x["n_claims"] for x in hp), 4),
                 "usd": round(sum(x["cost_usd"] for x in hp), 4), "usd_per_set": round(statistics.mean(x["cost_usd"] for x in hp), 5),
                 "input_tokens_mean": round(statistics.mean(x["input_tokens"] for x in hp)), "output_tokens_mean": round(statistics.mean(x["output_tokens"] for x in hp))}
    res["C9_fixed_not_in_pages"] = dict(collections.Counter(x["arm"] for x in c9))
    # 回饋家族：逐行狀態加總 vs 逐格分數
    cells = json.load(open(a.v4))["per_pair_arm_cells"]
    agg = collections.defaultdict(lambda: [0, 0])
    for p in (a.l1003, a.l1004):
        for x in jl(p):
            k = f"{x['set']}/r{x['rep']}/{x['arm']}"; agg[k][0] += 1; agg[k][1] += x["after_status"] == "correct"
    mism = [k for k, (n, c) in agg.items() if k in cells and (cells[k]["n_claims"] != n or cells[k]["correct_after"] != c)]
    res["feedback_lines_vs_cells"] = {"cells_in_lines": len(agg), "cells_in_v4": len(cells), "mismatch": mism[:20], "mismatch_n": len(mism)}
    json.dump(res, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ("drafts", "sets", "holm", "arm_means_set_weighted", "ER_vs_EN_drafts", "ER_vs_EN_sets", "sets_without_ER_filled",
                                          "EN_shortfall_drafts", "ER_vs_EN_all150_unit_weighted", "line_counts", "EB_sent_filled_drafts", "enrichment",
                                          "EN_sampled", "ER_fix_rate_on_wrong_filled", "EN_fix_rate_on_wrong_filled", "HP", "C9_fixed_not_in_pages", "feedback_lines_vs_cells")}, ensure_ascii=False, indent=0))
    for k, v in main_.items():
        print(k, v["sets"], v["units"], v["diff"], v["ci95"], v["ci90"], v["perm_p"], "unitw", v["unit_weighted_diff"], "eq", v["equivalent_within_delta"], "drop2", v["drop_top2_sets"])
    for k, v in res["ER_vs_EN_by_domain"].items():
        print("ER_vs_EN", k, v["sets"], v["units"], v["diff"], v["ci95"], v["ci90"])
    v = res["ER_vs_EN_exclude_shortfall"]; print("excl shortfall", v["sets"], v["units"], v["diff"], v["ci95"])


if __name__ == "__main__":
    main()
