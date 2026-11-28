#!/usr/bin/env python3
"""敏感度第 1、2 項的彙整：原評分（預註冊主分析，不動）對第二正規化器重評，各臂正確率（分組、組加權）與各比較的差、區間、判定。事後。"""
import collections, json, pathlib, statistics, sys
REPO = pathlib.Path(__file__).resolve().parents[3]
A = REPO / "ops/redo/audit/expTc_20261128"; R = REPO / "ops/redo/audit/judge_v2v3_20261128/regrade"
orig = {"confirm": json.loads((A / "expTc_confirm_analysis_20261128_v4_b61.json").read_text()),
        "esc": json.loads((A / "expTc_escalation_analysis_20261128.json").read_text()), "ef": A / "efamily"}
reg = {"confirm": json.loads((R / "expTc_confirm_analysis_regrade_b61.json").read_text()),
       "esc": json.loads((R / "expTc_escalation_regrade.json").read_text()), "ef": R / "efamily_regrade"}


def sw(pairs):  # {set: [values]} -> set-weighted mean
    return round(statistics.mean(statistics.mean(v) for v in pairs.values()), 4) if pairs else None


def arm_means(src):
    out = {}
    cells = src["confirm"]["per_pair_arm_cells"]
    for dom, pre in (("companies", "cc"), ("football", "ff"), ("all", "")):
        for arm in ("A", "G", "T", "TB"):
            by = collections.defaultdict(list)
            for k, c in cells.items():
                s, r, a = k.split("/")
                if a == arm and s.startswith(pre) and c.get("correct_prop_after") is not None and not c.get("infra_void"):
                    by[s].append(c["correct_prop_after"])
            out[f"feedback_{arm}|{dom}"] = sw(by)
        rows = [json.loads(l) for l in (src["ef"] / "efamily_per_draft_arm.jsonl").read_text().splitlines()]
        for arm in ("A", "EB", "ER", "EN"):
            by = collections.defaultdict(list)
            for r in rows:
                if r["arm"] == arm and r["set"].startswith(pre):
                    by[r["set"]].append(r["correct"] / r["n_claims"])
            out[f"{'drafts_c0' if arm == 'A' else 'E_' + arm}|{dom}"] = sw(by)
        hp = [json.loads(l) for l in (src["ef"] / "efamily_hp_per_set.jsonl").read_text().splitlines()]
        vals = {h["set"]: [h.get("correct_prop", h.get("correct", 0) / max(1, h.get("n_claims", 1)))] for h in hp if h["set"].startswith(pre)}
        out[f"E_HP|{dom}"] = sw(vals)
    return out


def cmp_block(src):
    c = src["confirm"]; e = src["esc"]; pick = lambda d: {k: d.get(k) for k in ("diff", "ci95", "perm_p")}
    o = {f"feedback_{k}": pick(c["feedback"]["all"][k]) for k in ("T_vs_TB", "T_vs_G", "TB_vs_G", "G_vs_A", "T_vs_A", "TB_vs_A")}
    o.update({f"selector_{k}": pick(c["selector"]["all"][k]) for k in ("record_vs_random", "record_vs_nonblank")})
    o.update({f"E_{k}": pick(e["main"][k]) for k in ("ER_vs_A", "ER_vs_EN", "ER_vs_EB")})
    for dom in ("companies", "football"):
        for k in ("T_vs_TB", "T_vs_G"):
            o[f"b35_{dom}_{k}"] = pick(c["b35_feedback_by_domain"][dom]["all"][k])
        dk = "company" if dom == "companies" else "football"
        for k in ("ER_vs_A", "ER_vs_EN", "ER_vs_EB"):
            if k in e["strata_B35"][dk]:
                o[f"E_{dom}_{k}"] = pick(e["strata_B35"][dk][k])
    return o


res = {"note": "事後敏感度、非預註冊；原評分是預註冊主分析，不動。第二正規化器（去掉答案鍵『; N years ago』；答案的（交易所, 代號）對包含值的全部對即算對）的規則是看資料後定的。",
       "arm_correct_prop_setweighted": {"original": arm_means(orig), "regraded": arm_means(reg)},
       "comparisons": {"original": cmp_block(orig), "regraded": cmp_block(reg)},
       "verdicts": {"original": {"confirm": orig["confirm"]["verdict"], "E": orig["esc"]["verdict"]},
                    "regraded": {"confirm": reg["confirm"]["verdict"], "E": reg["esc"]["verdict"]}},
       "holm": {"original": {"confirm": orig["confirm"]["holm"], "E": orig["esc"]["holm_family2"]},
                "regraded": {"confirm": reg["confirm"]["holm"], "E": reg["esc"]["holm_family2"]}}}
res["any_verdict_changed"] = res["verdicts"]["original"] != res["verdicts"]["regraded"]
(R.parent / "regrade_sensitivity.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
ao, ar = res["arm_correct_prop_setweighted"]["original"], res["arm_correct_prop_setweighted"]["regraded"]
for k in ao:
    print(f"{k:28s} {ao[k]} -> {ar[k]}")
co, cr = res["comparisons"]["original"], res["comparisons"]["regraded"]
for k in co:
    print(f"{k:34s} {co[k]['diff']} {co[k]['ci95']} p={co[k]['perm_p']}  ->  {cr[k]['diff']} {cr[k]['ci95']} p={cr[k]['perm_p']}")
print("verdict changed:", res["any_verdict_changed"]); print(res["holm"])
