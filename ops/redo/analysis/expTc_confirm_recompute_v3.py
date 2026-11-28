#!/usr/bin/env python3
"""確認批次 v3（回饋家族逐對逐臂、選擇器逐份）的獨立重算。不 import 執行方的分析碼。

讀：評分輸出 v3 JSON（`per_pair_arm_cells`、`per_pair_status`、`selector.all.per_draft`）。
算：回饋四比較（T−TB、T−G、TB−G、G−A 等）與兩個選擇器比較的差（組加權）、組層級 bootstrap 95%／90% 區間、
組層級符號翻轉置換 p（雙尾）、Holm（四個主比較）；B6 拿掉前 2 組、B35 分組、B59／B60 分台、B5 空白初稿分層、B7 傷害。
用法：python3 expTc_confirm_recompute_v3.py V3_B61.json V3_ORIG59.json --out OUT.json
"""
from __future__ import annotations
import argparse, collections, json, random, statistics

B_N, P_N = 20000, 200000


def boot(vals, lo, hi, seed=7):
    rng = random.Random(seed); k = len(vals); bs = sorted(sum(vals[rng.randrange(k)] for _ in range(k)) / k for _ in range(B_N))
    return [round(bs[int(lo * B_N)], 4), round(bs[int(hi * B_N) - 1], 4)]


def signflip(vals, seed=11):
    rng = random.Random(seed); obs = abs(sum(vals) / len(vals)); hit = 0
    for _ in range(P_N):
        if abs(sum(v if rng.random() < 0.5 else -v for v in vals) / len(vals)) >= obs - 1e-12:
            hit += 1
    return (hit + 1) / (P_N + 1)


def holm(ps):
    it = sorted(ps.items(), key=lambda x: x[1]); m = len(it); out = {}; run = 0.0
    for i, (k, p) in enumerate(it):
        run = max(run, min(1.0, (m - i) * p)); out[k] = round(run, 6)
    return out


def summarize(by_set: dict, delta: float):
    sets = sorted(by_set); vals = [statistics.mean(by_set[s]) for s in sets]
    if not vals:
        return None
    m = sum(vals) / len(vals)
    order = sorted(range(len(vals)), key=lambda i: -vals[i] if m >= 0 else vals[i])[:2]
    v2 = [v for i, v in enumerate(vals) if i not in order]
    units = [x for s in sets for x in by_set[s]]
    ci90 = boot(vals, 0.05, 0.95)
    return {"sets": len(vals), "units": len(units), "diff": round(m, 4), "ci95": boot(vals, 0.025, 0.975), "ci90": ci90,
            "perm_p": round(signflip(vals), 6), "unit_weighted_diff": round(sum(units) / len(units), 4),
            "equivalent_within_delta": ci90[0] > -delta and ci90[1] < delta,
            "drop_top2_sets": {"dropped": [sets[i] for i in order], "diff": round(sum(v2) / len(v2), 4), "ci95": boot(v2, 0.025, 0.975)}}


def fb_compare(cells, pairs, t, c, key="correct_prop_after", delta=0.05):
    by = collections.defaultdict(list)
    for (s, r) in pairs:
        a, b = cells.get(f"{s}/r{r}/{t}"), cells.get(f"{s}/r{r}/{c}")
        if a and b and not a.get("infra_void") and not b.get("infra_void"):
            by[s].append(a[key] - b[key])
    return summarize(by, delta)


HOST1003 = lambda s: (s.startswith("cc") and int(s.split("-s")[1]) <= 5) or (s.startswith("ff") and int(s.split("-s")[1]) <= 10)


def feedback_version(d):
    cells = d["per_pair_arm_cells"]; st = d["per_pair_status"]
    base = sorted((k.split("/r")[0], int(k.split("/r")[1])) for k, v in st.items() if v.get("in_base"))
    out = {"pairs": len(base)}
    for t, c, dl in (("T", "TB", 0.05), ("T", "G", 0.10), ("TB", "G", 0.05), ("G", "A", 0.05), ("T", "A", 0.05), ("TB", "A", 0.05)):
        out[f"{t}_vs_{c}"] = fb_compare(cells, base, t, c, delta=dl)
        out[f"{t}_vs_{c}"]["harm_total_rate"] = fb_compare(cells, base, t, c, key="harm_total_rate", delta=dl)
    blank = {(k.split("/r")[0], int(k.split("/r")[1])) for k, v in st.items() if v.get("blank_draft")}
    ctx = {(k.split("/r")[0], int(k.split("/r")[1])) for k, v in st.items() if v.get("draft_context_exhausted")}
    strata = {"nonblank": [p for p in base if p not in blank], "blank_only": [p for p in base if p in blank],
              "company": [p for p in base if p[0].startswith("cc")], "football": [p for p in base if p[0].startswith("ff")],
              "host_1003": [p for p in base if HOST1003(p[0])], "host_1004": [p for p in base if not HOST1003(p[0])],
              "draft_ctx_not_exhausted": [p for p in base if p not in ctx]}
    out["strata"] = {}
    for name, ps in strata.items():
        out["strata"][name] = {"pairs": len(ps)}
        for t, c, dl in (("T", "TB", 0.05), ("T", "G", 0.10)):
            r = fb_compare(cells, ps, t, c, delta=dl)
            out["strata"][name][f"{t}_vs_{c}"] = {k: r[k] for k in ("sets", "units", "diff", "ci95", "ci90", "perm_p", "equivalent_within_delta")} if r else None
    # 各臂平均（格平均）與傷害行數
    arms = collections.defaultdict(list)
    for (s, r) in base:
        for a in ("A", "G", "T", "TB"):
            x = cells.get(f"{s}/r{r}/{a}")
            if x and not x.get("infra_void"):
                arms[a].append(x)
    out["per_arm"] = {a: {"cells": len(v), "correct_prop_mean": round(statistics.mean(x["correct_prop_after"] for x in v), 4),
                          "harm_c2w_or_d": sum(x["harm_c2w_or_d"] for x in v), "harm_b2w": sum(x["harm_b2w"] for x in v),
                          "fixed": sum(x.get("fixed_count") or 0 for x in v)} for a, v in arms.items()}
    out["blank_pairs"] = {"total": len([p for p in base if p in blank]), "1003": len([p for p in base if p in blank and HOST1003(p[0])]),
                          "1004": len([p for p in base if p in blank and not HOST1003(p[0])])}
    # TB 在 1003：最終報告和 A 不同的對數
    out["TB_changed_vs_A_by_host"] = {h: sum(1 for (s, r) in base if (HOST1003(s) == (h == "1003")) and cells.get(f"{s}/r{r}/TB")
                                             and cells[f"{s}/r{r}/TB"]["correct_after"] != cells[f"{s}/r{r}/A"]["correct_after"]) for h in ("1003", "1004")}
    out["TB_rounds_by_host"] = {h: sum((cells.get(f"{s}/r{r}/TB") or {}).get("rounds_run") or 0 for (s, r) in base if HOST1003(s) == (h == "1003")) for h in ("1003", "1004")}
    return out


def selector(d):
    pdr = d["selector"]["all"]["per_draft"]; by = collections.defaultdict(list)
    for x in pdr:
        by[x["set"]].append(x)
    rows = []
    for s, ds in sorted(by.items()):
        ds = sorted(ds, key=lambda x: x["rep"])
        rec = max(ds, key=lambda x: (int(x["evidence_score"]), -int(x["blank_count"])))     # 同分取空白少，再同分取 rep 小（max 取第一個）
        nb = max(ds, key=lambda x: int(x["n_claims"]) - int(x["blank_count"]))
        rows.append({"set": s, "k": len(ds), "record": rec["correct_prop"], "nonblank": nb["correct_prop"],
                     "random": statistics.mean(x["correct_prop"] for x in ds), "oracle": max(x["correct_prop"] for x in ds),
                     "record_rep": rec["rep"], "nonblank_rep": nb["rep"], "blank_drafts": sum(1 for x in ds if x["filled"] == 0)})
    def comp(sub, a, b, dl):
        return summarize({r["set"]: [r[a] - r[b]] for r in sub}, dl)
    out = {"k_values": sorted({r["k"] for r in rows}), "sets": len(rows), "same_pick": sum(r["record_rep"] == r["nonblank_rep"] for r in rows),
           "means": {k: round(statistics.mean(r[k] for r in rows), 4) for k in ("record", "nonblank", "random", "oracle")},
           "record_vs_random": comp(rows, "record", "random", 0.05), "record_vs_nonblank": comp(rows, "record", "nonblank", 0.03),
           "per_set_matches_their_per_set": None}
    theirs = {r["set"]: r for r in d["selector"]["all"]["per_set"]}
    out["per_set_mismatch"] = [r["set"] for r in rows if any(abs(r[k] - theirs[r["set"]][k]) > 1e-9 for k in ("record", "nonblank", "random", "oracle"))
                               or r["record_rep"] != theirs[r["set"]]["record_rep"] or r["nonblank_rep"] != theirs[r["set"]]["nonblank_rep"]]
    out["strata"] = {}
    for name, f in (("company", lambda r: r["set"].startswith("cc")), ("football", lambda r: r["set"].startswith("ff")),
                    ("host_1003", lambda r: HOST1003(r["set"])), ("host_1004", lambda r: not HOST1003(r["set"]))):
        sub = [r for r in rows if f(r)]
        out["strata"][name] = {"sets": len(sub), "record_vs_random": {k: v for k, v in comp(sub, "record", "random", 0.05).items() if k != "drop_top2_sets"},
                               "record_vs_nonblank": {k: v for k, v in comp(sub, "record", "nonblank", 0.03).items() if k != "drop_top2_sets"}}
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("b61"); ap.add_argument("orig59"); ap.add_argument("--out", required=True)
    a = ap.parse_args(); db, do = json.load(open(a.b61)), json.load(open(a.orig59))
    res = {"b61": feedback_version(db), "orig59": feedback_version(do), "selector": selector(db)}
    for lab, d, fb in (("b61", db, res["b61"]), ("orig59", do, res["orig59"])):
        ps = {"record_vs_random": res["selector"]["record_vs_random"]["perm_p"], "record_vs_nonblank": res["selector"]["record_vs_nonblank"]["perm_p"],
              "T_vs_TB": fb["T_vs_TB"]["perm_p"], "T_vs_G": fb["T_vs_G"]["perm_p"]}
        fb["holm"] = holm(ps)
        fb["their"] = {"holm": d["holm"], "perm_p_raw": d["perm_p_raw"], "verdict": d["verdict"], "qualifiers": d["qualifiers"],
                       "T_vs_TB": {k: d["feedback"]["all"]["T_vs_TB"][k] for k in ("diff", "ci95", "ci90", "perm_p")},
                       "T_vs_G": {k: d["feedback"]["T_vs_G_aligned"]["T_vs_G"][k] for k in ("diff", "ci95", "ci90", "perm_p")},
                       "T_vs_G_harm": d["feedback"]["T_vs_G_aligned"]["T_vs_G"]["harm_total_rate"]["diff"]}
    json.dump(res, open(a.out, "w"), ensure_ascii=False, indent=1)
    for lab in ("b61", "orig59"):
        fb = res[lab]; print("==", lab, "pairs", fb["pairs"], "blank", fb["blank_pairs"])
        for c in ("T_vs_TB", "T_vs_G", "TB_vs_G", "G_vs_A", "T_vs_A", "TB_vs_A"):
            x = fb[c]; print("  ", c, x["sets"], x["units"], x["diff"], x["ci95"], x["ci90"], x["perm_p"], "eq", x["equivalent_within_delta"],
                             "drop2", x["drop_top2_sets"]["dropped"], x["drop_top2_sets"]["diff"], x["drop_top2_sets"]["ci95"], "harm", x["harm_total_rate"]["diff"], x["harm_total_rate"]["ci95"])
        print("   holm", fb["holm"]); print("   their", json.dumps(fb["their"], ensure_ascii=False))
        for k, v in fb["strata"].items():
            print("   strata", k, v["pairs"], {c: (v[c]["diff"], v[c]["ci95"]) if v[c] else None for c in ("T_vs_TB", "T_vs_G")})
        print("   per_arm", fb["per_arm"], "TB changed vs A", fb["TB_changed_vs_A_by_host"], "TB rounds", fb["TB_rounds_by_host"])
    s = res["selector"]; print("== selector", s["k_values"], s["sets"], s["means"], "same", s["same_pick"], "mismatch", s["per_set_mismatch"])
    for c in ("record_vs_random", "record_vs_nonblank"):
        x = s[c]; print("  ", c, x["diff"], x["ci95"], x["ci90"], x["perm_p"], x["drop_top2_sets"])
    for k, v in s["strata"].items():
        print("   strata", k, v["sets"], v["record_vs_random"]["diff"], v["record_vs_random"]["ci95"], v["record_vs_nonblank"]["diff"], v["record_vs_nonblank"]["ci95"])


if __name__ == "__main__":
    main()
