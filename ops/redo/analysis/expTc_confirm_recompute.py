#!/usr/bin/env python3
"""確認批次（實驗 T，2026-11-28）的獨立重算：不 import 執行方的分析碼，只讀稽核包裡的評分輸出 JSON（遮罩副本）。

稽核包裡有逐組資料的只有選擇器（selector.*.per_set）；回饋四臂只有彙總（沒有逐對、逐行的分數），
所以回饋家族只能做一致性檢查（Holm、判定邏輯、門檻、區間與等價），不能從頭重算差與區間。
用法：python3 expTc_confirm_recompute.py <expTc_confirm_analysis_20261128.json> --out OUT.json
"""
from __future__ import annotations
import argparse, json, random, statistics


def boot_ci(vals, n=20000, seed=7, lo=0.025, hi=0.975):
    rng = random.Random(seed); k = len(vals); bs = []
    for _ in range(n):
        bs.append(sum(vals[rng.randrange(k)] for _ in range(k)) / k)
    bs.sort()
    return [round(bs[int(lo * n)], 4), round(bs[int(hi * n) - 1], 4)]


def signflip_p(vals, n=200000, seed=11):
    """組層級符號翻轉置換檢定（雙尾）；|平均| ≥ 觀察值的比例（含觀察本身，+1 校正）。"""
    rng = random.Random(seed); obs = abs(sum(vals) / len(vals)); hit = 0
    for _ in range(n):
        s = sum(v if rng.random() < 0.5 else -v for v in vals)
        if abs(s / len(vals)) >= obs - 1e-12:
            hit += 1
    return round((hit + 1) / (n + 1), 6)


def holm(ps: dict) -> dict:
    items = sorted(ps.items(), key=lambda x: x[1]); m = len(items); out = {}; run = 0.0
    for i, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p)); out[k] = round(run, 5)
    return out


def comp(per_set, a, b, delta):
    d = [r[a] - r[b] for r in per_set]
    m = sum(d) / len(d)
    ci95 = boot_ci(d); ci90 = boot_ci(d, lo=0.05, hi=0.95); p = signflip_p(d)
    top = sorted(range(len(d)), key=lambda i: -d[i] if m >= 0 else d[i])[:2]
    d2 = [x for i, x in enumerate(d) if i not in top]
    return {"sets": len(d), "diff": round(m, 4), "ci95": ci95, "ci90": ci90, "perm_p": p,
            "equivalent_within_delta": ci90[0] > -delta and ci90[1] < delta,
            "drop_top2_sets": {"dropped": [per_set[i]["set"] for i in top], "diff": round(sum(d2) / len(d2), 4), "ci95": boot_ci(d2)},
            "sets_positive": sum(x > 0 for x in d), "sets_negative": sum(x < 0 for x in d), "sets_zero": sum(x == 0 for x in d)}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("--out", required=True)
    a = ap.parse_args(); src = json.load(open(a.src))
    res = {"note": "選擇器從逐組資料重算；回饋家族只能做一致性檢查（稽核包沒有逐對資料）"}
    sel = {}
    for lab in ("all", "nonblank_drafts"):
        ps = src["selector"][lab]["per_set"]
        ks = sorted({r["k"] for r in ps})
        blank_sets = [r["set"] for r in ps if r.get("blank_drafts")]
        sel[lab] = {"sets": len(ps), "k_values": ks, "sets_with_blank_drafts": len(blank_sets),
                    "means": {x: round(statistics.mean(r[x] for r in ps), 4) for x in ("record", "nonblank", "random", "oracle")},
                    "record_vs_random": comp(ps, "record", "random", 0.05),
                    "record_vs_nonblank": comp(ps, "record", "nonblank", 0.03),
                    "nonblank_vs_random": comp(ps, "nonblank", "random", 0.05),
                    "same_pick_record_nonblank": sum(r["record_rep"] == r["nonblank_rep"] for r in ps),
                    "record_pick_has_more_blank_than_nonblank_pick": None}
        # 依 blank_drafts 分：有空白份的組 vs 沒有的組，record−random
        wb = [r for r in ps if r.get("blank_drafts")]; nb = [r for r in ps if not r.get("blank_drafts")]
        sel[lab]["record_minus_random_by_blank_presence"] = {
            "sets_with_blank": {"n": len(wb), "mean": round(statistics.mean(r["record"] - r["random"] for r in wb), 4) if wb else None},
            "sets_without_blank": {"n": len(nb), "mean": round(statistics.mean(r["record"] - r["random"] for r in nb), 4) if nb else None}}
    res["selector"] = sel
    # B35／B60：選擇器的分組（公司 cc／足球 ff）與分台（1003＝cc-s01..05、ff-s01..10；1004＝其餘）——逐組資料可直接分
    def host_of(sid):
        n = int(sid.split("-s")[1]); return "1003" if (sid.startswith("cc") and n <= 5) or (sid.startswith("ff") and n <= 10) else "1004"
    strata = {}
    ps = src["selector"]["all"]["per_set"]
    for name, key in (("domain", lambda r: r["set"][:2]), ("host", lambda r: host_of(r["set"]))):
        for g in sorted({key(r) for r in ps}):
            sub = [r for r in ps if key(r) == g]
            strata[f"{name}:{g}"] = {"sets": len(sub), "blank_drafts": sum(r["blank_drafts"] for r in sub),
                                     "record_vs_random": comp(sub, "record", "random", 0.05),
                                     "record_vs_nonblank": comp(sub, "record", "nonblank", 0.03)}
    res["selector_strata"] = strata
    res["selector_blank_drafts_total"] = sum(r["blank_drafts"] for r in ps)
    res["selector_record_pick_scored_zero"] = [r["set"] for r in ps if r["record"] == 0]
    # Holm：選擇器兩個 p 用重算值；回饋兩個 p 只能用執行方的原始 p（無法重算）
    ps_fb = src["perm_p_raw"]
    ph = {"record_vs_random": sel["all"]["record_vs_random"]["perm_p"], "record_vs_nonblank": sel["all"]["record_vs_nonblank"]["perm_p"],
          "T_vs_TB": ps_fb["T_vs_TB"], "T_vs_G": ps_fb["T_vs_G"]}
    res["holm_recomputed_mixed"] = holm(ph)
    res["holm_from_their_raw_p"] = holm(dict(ps_fb))
    # 判定（預註冊：門檻＋95% 下界 >0＋Holm<0.05；等價：90% 區間在 ±Δ 內）
    def verdict(diff, ci95, ci90, hp, delta, extra=True):
        if diff >= delta and ci95[0] > 0 and hp < 0.05 and extra: return "pass"
        if diff >= delta and ci95[0] > 0 and extra: return "pass_uncorrected_only"
        if ci90[0] > -delta and ci90[1] < delta: return "equivalent_within_delta"
        return "no_difference_measured"
    fb = src["feedback"]["all"]; fba = src["feedback"]["T_vs_G_aligned"]
    hp = res["holm_recomputed_mixed"]
    res["verdict_recomputed"] = {
        "record_vs_random": verdict(sel["all"]["record_vs_random"]["diff"], sel["all"]["record_vs_random"]["ci95"], sel["all"]["record_vs_random"]["ci90"], hp["record_vs_random"], 0.05),
        "record_vs_nonblank": verdict(sel["all"]["record_vs_nonblank"]["diff"], sel["all"]["record_vs_nonblank"]["ci95"], sel["all"]["record_vs_nonblank"]["ci90"], hp["record_vs_nonblank"], 0.03),
        "T_vs_TB_from_their_summary": verdict(fb["T_vs_TB"]["diff"], fb["T_vs_TB"]["ci95"], fb["T_vs_TB"]["ci90"], hp["T_vs_TB"], 0.05),
        "T_vs_G_from_their_summary": verdict(fba["T_vs_G"]["diff"], fba["T_vs_G"]["ci95"], fba["T_vs_G"]["ci90"], hp["T_vs_G"], 0.10,
                                            extra=(fba["T_vs_G"]["harm_total_rate"].get("diff") is not None and fba["T_vs_G"]["harm_total_rate"]["diff"] <= 0))}
    json.dump(res, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ("holm_recomputed_mixed", "verdict_recomputed")}, ensure_ascii=False, indent=1))
    for lab in sel:
        s = sel[lab]; print(lab, s["sets"], s["k_values"], s["means"], "same", s["same_pick_record_nonblank"])
        for c in ("record_vs_random", "record_vs_nonblank", "nonblank_vs_random"):
            x = s[c]; print("  ", c, x["diff"], x["ci95"], x["ci90"], x["perm_p"], "eq", x["equivalent_within_delta"], "drop2", x["drop_top2_sets"]["diff"], x["drop_top2_sets"]["ci95"], "+/-/0", x["sets_positive"], x["sets_negative"], x["sets_zero"])
        print("  by blank presence", s["record_minus_random_by_blank_presence"])
    for k, v in res["selector_strata"].items():
        print("strata", k, v["sets"], "blank", v["blank_drafts"], "rvr", v["record_vs_random"]["diff"], v["record_vs_random"]["ci95"], "rvn", v["record_vs_nonblank"]["diff"], v["record_vs_nonblank"]["ci95"])


if __name__ == "__main__":
    main()
