#!/usr/bin/env python3
"""步驟 1 的分析（PLAN.md 事前寫定的量；事後探索性）。讀 V1（judge_lines_all）、V2／V3／機制對照（v2v3_lines）、步驟 0 分類，
算三種問法的 AUC 與配對差（組群集 bootstrap 10,000 次）、兩個事先定的門檻、分類別召回、ECE／Brier、機制對照。輸出無值。
用法：judge_v2v3_analysis.py R1 R2 --dir ops/redo/audit/judge_v2v3_20261128"""
from __future__ import annotations
import argparse, collections, hashlib, hmac, json, pathlib, random, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from judge_gemini_analysis import auc  # noqa: E402
import judge_pages as P  # noqa: E402
M = P.M
KEY = (pathlib.Path.home() / ".config/vacant/audit_hmac.key").read_text().strip().encode()
lk = lambda sid, rep, cid: hmac.new(KEY, f"{sid}|r{rep}|{cid}".encode(), hashlib.sha256).hexdigest()[:20]
NB, SEED = 10000, 20261128


def fast_auc(scores, labels):
    return auc(scores, labels)


def boot_diff(rows, a, b, nb=NB):
    sets = sorted({r["set"] for r in rows}); by = collections.defaultdict(list)
    for r in rows:
        by[r["set"]].append(r)
    rng = random.Random(SEED); d = []; aa = []; bb = []
    for _ in range(nb):
        smp = [x for s in (sets[rng.randrange(len(sets))] for _ in sets) for x in by[s]]
        lab = [x["wrong"] for x in smp]
        if 0 < sum(lab) < len(lab):
            ua = fast_auc([1 - x[a] for x in smp], lab); ub = fast_auc([1 - x[b] for x in smp], lab)
            aa.append(ua); bb.append(ub); d.append(ua - ub)
    q = lambda v: [round(sorted(v)[int(0.025 * len(v))], 4), round(sorted(v)[int(0.975 * len(v)) - 1], 4)] if v else None
    lab = [x["wrong"] for x in rows]
    pa = fast_auc([1 - x[a] for x in rows], lab); pb = fast_auc([1 - x[b] for x in rows], lab)
    return {"auc_" + a: pa, "auc_" + a + "_ci": q(aa), "auc_" + b: pb, "diff": round(pa - pb, 4) if pa is not None and pb is not None else None,
            "diff_ci": q(d), "sets": len(sets), "boot_valid": len(d)}


def stats(rows, flag):
    f = [r for r in rows if flag(r)]; nf = [r for r in rows if not flag(r)]; w = sum(r["wrong"] for r in rows)
    r_ = lambda x, y: round(x / y, 4) if y else None
    return {"flagged_share": r_(len(f), len(rows)), "err_in": r_(sum(x["wrong"] for x in f), len(f)), "pass_err": r_(sum(x["wrong"] for x in nf), len(nf)),
            "recall": r_(sum(x["wrong"] for x in f), w), "n_flagged": len(f)}


def calib(rows, s):
    bins = collections.defaultdict(list)
    for r in rows:
        bins[min(14, int(r[s] * 15))].append(r)
    n = len(rows); ece = 0.0
    for b, rr in bins.items():
        ece += len(rr) / n * abs(sum(x[s] for x in rr) / len(rr) - sum(not x["wrong"] for x in rr) / len(rr))
    brier = sum((r[s] - (0 if r["wrong"] else 1)) ** 2 for r in rows) / n
    return {"ece15": round(ece, 4), "brier": round(brier, 4)}


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("roots", nargs=2); ap.add_argument("--dir", required=True); ap.add_argument("--nb", type=int, default=NB)
    a = ap.parse_args(); d = pathlib.Path(a.dir)
    roots = [pathlib.Path(r) for r in a.roots]
    plan = json.loads((roots[0] / "RUN.json").read_text())["plan_body"]; truth = M.load_manifests_with_truth(plan)
    key2set = {}
    for root in roots:
        for c0 in sorted(root.glob("cells/*/r[1-5]/c0")):
            sid, rep = c0.parts[-3], int(c0.parts[-2][1:])
            for c in truth[sid]["claims"]:
                key2set[lk(sid, rep, c["id"])] = sid
    v1 = {json.loads(l)["key"]: json.loads(l) for l in (d.parent / "judge_gemini_decision_20261128" / "judge_lines_all.jsonl").read_text().splitlines()}
    vv = collections.defaultdict(dict)
    for l in (d / "v2v3_lines.jsonl").read_text().splitlines():
        j = json.loads(l); vv[j["tag"]][j["key"]] = j
    cls = {json.loads(l)["key"]: json.loads(l)["class"] for l in (d / "err_taxonomy_lines.jsonl").read_text().splitlines()}
    rows = []; miss = 0
    for k, r in v1.items():
        s2 = vv["V2"].get(k, {}).get("score"); s3 = vv["V3"].get(k, {}).get("score")
        if r["p_supported"] is None or s2 is None or s3 is None:
            miss += 1; continue
        rows.append({"key": k, "set": key2set[k], "domain": r["domain"], "wrong": r["wrong"], "cls": cls.get(k, "correct"),
                     "V1": r["p_supported"], "V2": s2, "V3": s3})
    res = {"note": "事後探索性；規則＝PLAN.md（呼叫前提交）。主分析排除量具等值（U-等值＋K-等值）。分數＝判定說「支持／對」的機率；AUC 標籤＝錯、分數＝1−p。",
           "lines_with_all_three": len(rows), "lines_missing_any": miss, "versions": {}}
    excl = {"main_excl_U_K_equiv": {"U-等值", "K-等值"}, "spec_literal_excl_U_equiv": {"U-等值"}, "no_exclusion": set()}
    fb_v1_rate = None
    for vn, ex in excl.items():
        out = {}
        for dom in ("companies", "football"):
            rr = [r for r in rows if r["domain"] == dom and r["cls"] not in ex]
            o = {"lines": len(rr), "wrong": sum(r["wrong"] for r in rr)}
            nb = a.nb if vn != "no_exclusion" else 2000
            o["V2_vs_V1"] = boot_diff(rr, "V2", "V1", nb); o["V3_vs_V1"] = boot_diff(rr, "V3", "V1", nb)
            out[dom] = o
        # 門檻
        fb = [r for r in rows if r["domain"] == "football" and r["cls"] not in ex]
        v1rate = sum(r["V1"] < 0.5 for r in fb) / len(fb)
        if vn == "main_excl_U_K_equiv":
            fb_v1_rate = v1rate
        thr = {}
        for V in ("V1", "V2", "V3"):
            sc = sorted(r[V] for r in fb); t = sc[min(len(sc) - 1, int(round(v1rate * len(sc))))]
            thr[V] = t
        for dom in ("companies", "football"):
            rr = [r for r in rows if r["domain"] == dom and r["cls"] not in ex]
            out[dom]["thresholds"] = {V: {"p<0.5": stats(rr, lambda r, V=V: r[V] < 0.5),
                                          f"match_football_V1_rate(t={thr[V]:.4f})": stats(rr, lambda r, V=V: r[V] < thr[V])} for V in ("V1", "V2", "V3")}
            out[dom]["recall_by_class_p<0.5"] = {V: {c: round(sum(r[V] < 0.5 for r in rr if r["cls"] == c) / max(1, sum(r["cls"] == c for r in rr)), 3)
                                                     for c in sorted({r["cls"] for r in rr if r["wrong"]})} for V in ("V1", "V2", "V3")}
            out[dom]["class_counts"] = dict(collections.Counter(r["cls"] for r in rr if r["wrong"]))
            out[dom]["calibration"] = {V: calib(rr, V) for V in ("V1", "V2", "V3")}
        out["football_V1_flag_rate_at_0.5"] = round(v1rate, 4)
        res["versions"][vn] = out
    # 機制對照
    mech = {}
    for dom in ("companies", "football", "all"):
        m = {}
        for tag in ("MECH_V1", "MECH_V2"):
            sc = [j["score"] for j in vv[tag].values() if j.get("score") is not None and (dom == "all" or j["domain"] == dom)]
            m[tag] = {"n": len(sc), "share_p>=0.9": round(sum(s >= 0.9 for s in sc) / max(1, len(sc)), 4),
                      "share_p>=0.5": round(sum(s >= 0.5 for s in sc) / max(1, len(sc)), 4), "mean": round(sum(sc) / max(1, len(sc)), 4)}
        mech[dom] = m
    res["mechanism_swap_field_on_correct_lines"] = mech
    mn = res["versions"]["main_excl_U_K_equiv"]
    verdict = {}
    for V in ("V2", "V3"):
        c = mn["companies"][f"{V}_vs_V1"]; f = mn["football"][f"{V}_vs_V1"]
        ok_c = bool(c["auc_" + V + "_ci"] and c["auc_" + V + "_ci"][0] > 0.5 and c["diff_ci"] and c["diff_ci"][0] > 0)
        ok_f = bool(f["diff_ci"] and f["diff_ci"][0] > -0.03)
        verdict[V] = {"companies_effective": ok_c, "football_not_worse": ok_f, "recommend_switch": ok_c and ok_f}
    res["prereg_style_verdict_main"] = verdict
    errs = {t: sum(1 for j in vv[t].values() if j.get("error")) for t in vv}
    res["call_errors_by_tag"] = errs
    (d / "v2v3_analysis.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({"verdict": verdict, "mech": mech, "errors": errs}, ensure_ascii=False))
    for dom in ("companies", "football"):
        for V in ("V2", "V3"):
            x = mn[dom][f"{V}_vs_V1"]; print(dom, V, {k: x[k] for k in x})
    return 0


if __name__ == "__main__":
    sys.exit(main())
