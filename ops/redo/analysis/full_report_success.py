#!/usr/bin/env python3
"""評分器效度 2：整份成功率＝『全部必填行都被判正確』的報告比例。分臂、兩種評分（原 strict／第二正規化器重評）、組群集 bootstrap 95%（2000 次、種子 20261128）。
資料：v4 主分析與重評的 per_pair_arm_cells（回饋 A/G/T/TB）、E 匯出的 per_draft_arm（初稿 A、EB、ER、EN）與 hp_per_set（HP）。"""
import collections, json, pathlib, random
REPO = pathlib.Path(__file__).resolve().parents[3]
A = REPO / "ops/redo/audit/expTc_20261128"; R = REPO / "ops/redo/audit/judge_v2v3_20261128/regrade"
src = {"original": (json.loads((A / "expTc_confirm_analysis_20261128_v4_b61.json").read_text()), A / "efamily"),
       "regraded": (json.loads((R / "expTc_confirm_analysis_regrade_b61.json").read_text()), R / "efamily_regrade")}


def boot(units):  # units: list of (set, success)
    by = collections.defaultdict(list)
    for s, ok in units:
        by[s].append(ok)
    sets = sorted(by); rng = random.Random(20261128); bs = []
    for _ in range(2000):
        pick = [sets[rng.randrange(len(sets))] for _ in sets]; xs = [x for s in pick for x in by[s]]; bs.append(sum(xs) / len(xs))
    bs.sort()
    return {"success": sum(ok for _, ok in units), "n": len(units), "rate": round(sum(ok for _, ok in units) / len(units), 4),
            "ci95": [round(bs[50], 4), round(bs[1949], 4)], "sets": len(sets)}


out = {"note": "整份成功率：一份報告的全部必填行都被判正確。組群集區間。", "by_mode": {}}
for mode, (ca, ef) in src.items():
    res = {}
    for dom, pre in (("all", ""), ("companies", "cc"), ("football", "ff")):
        r = {}
        for arm in ("A", "G", "T", "TB"):
            u = [(k.split("/")[0], c["correct_after"] == c["n_claims"]) for k, c in ca["per_pair_arm_cells"].items()
                 if k.split("/")[2] == arm and k.startswith(pre) and not c.get("infra_void") and c.get("n_claims")]
            r[f"feedback_{arm}"] = boot(u)
        rows = [json.loads(l) for l in (ef / "efamily_per_draft_arm.jsonl").read_text().splitlines()]
        for arm in ("A", "EB", "ER", "EN"):
            u = [(x["set"], x["correct"] == x["n_claims"]) for x in rows if x["arm"] == arm and x["set"].startswith(pre)]
            r["drafts_c0" if arm == "A" else f"E_{arm}"] = boot(u)
        hp = [json.loads(l) for l in (ef / "efamily_hp_per_set.jsonl").read_text().splitlines()]
        r["E_HP"] = boot([(x["set"], x["correct"] == x["n_claims"]) for x in hp if x["set"].startswith(pre)])
        res[dom] = r
    out["by_mode"][mode] = res
o = REPO / "ops/redo/audit/scorer_validity_20261128/full_report_success.json"; o.write_text(json.dumps(out, ensure_ascii=False, indent=1))
for mode in out["by_mode"]:
    print(mode, {k: f"{v['success']}/{v['n']}" for k, v in out["by_mode"][mode]["all"].items()})
