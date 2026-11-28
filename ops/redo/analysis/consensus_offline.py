#!/usr/bin/env python3
"""事後離線分析（2026-11-28，非預註冊，不叫模型）：用「多份獨立初稿彼此一致」當判定，不看答案鍵能做到什麼程度。

資料：確認批次 150 份初稿（30 組 × r1–r5；兩個初稿 root）。值的正規化用 expT_metrics.canon_strict，對錯用 strict_status（和評分同一套）。
1. 逐行多數決：每組每行取 k 份裡出現最多的非空白值（canon_strict 後比較；平手取 r 最小的那份的值；全空白＝空白），
   組成一份報告算正確率；並列 A（單份平均）、record、nonblank、oracle（最好的一份）、逐行 oracle（任一份對）。k＝5 與 k＝3（r1–r3）。
   組加權；組群集 bootstrap（2000 次，種子 20261128）區間。record／nonblank 的挑法照選擇器（record＝evidence_score 最高、同分空白少、再 r 小；
   nonblank＝填寫行最多、同分 r 小），k＝3 時在 r1–r3 裡重挑。
2. 一致度旗標（只看有填行）：這份的值 ≠ 多數值，或同意的份數 ≤1 ⇒ 旗標。算旗標內／外的錯誤率（分足球／公司），
   和紀錄標記（flags_v2.json 的 flagged）並列，再算兩種旗標的重疊。
輸出只有計數與比例，沒有值。用法：consensus_offline.py <drafts_root> <drafts_root> --out DIR
"""
from __future__ import annotations
import argparse, collections, json, pathlib, random, statistics, sys
REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "ops" / "d2"))
from ops.d2 import expT_metrics as M  # noqa: E402

SEED, NB = 20261128, 2000


def boot(diffs: dict) -> dict:
    sets = sorted(diffs); vals = [diffs[s] for s in sets]
    if not vals:
        return {}
    rng = random.Random(SEED); bs = []
    for _ in range(NB):
        smp = [vals[rng.randrange(len(vals))] for _ in vals]; bs.append(sum(smp) / len(smp))
    bs.sort()
    return {"mean": round(sum(vals) / len(vals), 4), "ci95": [round(bs[int(0.025 * NB)], 4), round(bs[int(0.975 * NB) - 1], 4)], "sets": len(vals)}


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("roots", nargs=2); ap.add_argument("--out", required=True); a = ap.parse_args()
    roots = [pathlib.Path(r) for r in a.roots]; out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    plan = json.loads((roots[0] / "RUN.json").read_text())["plan_body"]; truth = M.load_manifests_with_truth(plan)
    drafts = collections.defaultdict(dict)       # sid -> rep -> {claim: (raw, canon, status)}
    flags = collections.defaultdict(dict)        # sid -> rep -> {claim: record_flagged}
    for root in roots:
        for c0 in sorted(root.glob("cells/*/r[1-5]/c0")):
            sid, rep = c0.parts[-3], int(c0.parts[-2][1:])
            vals = M.SD.parse_report((c0 / "report.md").read_text(errors="replace"), truth[sid]["claims"])
            d = {}
            for c in truth[sid]["claims"]:
                raw = vals.get(c["id"]); raw = None if raw in (None, "") else raw
                d[c["id"]] = (raw, M.canon_strict(raw), "blank" if raw is None else M.strict_status(raw, c["id"], truth[sid]["truth"], 0))
            drafts[sid][rep] = d
            fb = json.loads((c0 / "flags_v2.json").read_text()).get("flags_by_claim") or {}
            flags[sid][rep] = {cid: bool(v.get("flagged")) for cid, v in fb.items()}
    # 選擇器的 evidence_score：取 v4 輸出的 per_draft（同一套），以便 k=3 重挑
    sel = {}
    v4 = REPO / "ops/redo/audit/expTc_20261128/expTc_confirm_analysis_20261128_v4_b61.json"
    for r in json.loads(v4.read_text())["selector"]["all"]["per_draft"]:
        sel[(r["set"], int(r["rep"]))] = r
    res = {"note": "事後離線分析、非預註冊；不看答案鍵的部分只有多數決與一致度旗標本身，對錯一律用答案鍵評分。", "k": {}}
    for K in (5, 3):
        per = {}
        for sid, reps in sorted(drafts.items()):
            rs = [r for r in sorted(reps) if r <= K]
            if len(rs) < K:
                continue
            claims = [c["id"] for c in truth[sid]["claims"]]; n = len(claims)
            maj_correct = 0; line_oracle = 0
            for cid in claims:
                cnt = collections.Counter(); first = {}
                for r in rs:
                    raw, can, st = reps[r][cid]
                    if can is not None:
                        cnt[can] += 1; first.setdefault(can, (r, raw, st))
                if cnt:
                    top = max(cnt.values()); cand = [c for c in cnt if cnt[c] == top]
                    pick = min(cand, key=lambda c: first[c][0])
                    maj_correct += first[pick][2] == "correct"
                line_oracle += any(reps[r][cid][2] == "correct" for r in rs)
            props = {r: sum(reps[r][c][2] == "correct" for c in claims) / n for r in rs}
            ds = [sel[(sid, r)] for r in rs]
            rec = max(ds, key=lambda d: (int(d["evidence_score"]), -int(d["blank_count"]), -int(d["rep"])))
            nb = max(ds, key=lambda d: (int(d["n_claims"]) - int(d["blank_count"]), -int(d["rep"])))
            per[sid] = {"majority": maj_correct / n, "A": statistics.mean(props.values()), "record": props[int(rec["rep"])],
                        "nonblank": props[int(nb["rep"])], "oracle": max(props.values()), "line_oracle": line_oracle / n}
        means = {m: round(statistics.mean(v[m] for v in per.values()), 4) for m in ("majority", "A", "record", "nonblank", "oracle", "line_oracle")}
        cmp_ = {f"majority_vs_{b}": boot({s: v["majority"] - v[b] for s, v in per.items()}) for b in ("A", "record", "nonblank", "oracle")}
        res["k"][str(K)] = {"sets": len(per), "means": means, "comparisons": cmp_,
                            "by_domain_means": {dom: {m: round(statistics.mean(v[m] for s, v in per.items() if s.startswith(pre)), 4) for m in means}
                                                for dom, pre in (("companies", "cc"), ("football", "ff"))}}
    # 2. 一致度旗標（k=5、有填行）
    tab = collections.defaultdict(collections.Counter)
    for sid, reps in drafts.items():
        dom = "companies" if sid.startswith("cc") else "football"
        rs = sorted(reps)
        for cid in [c["id"] for c in truth[sid]["claims"]]:
            cnt = collections.Counter(reps[r][cid][1] for r in rs if reps[r][cid][1] is not None)
            if not cnt:
                continue
            top = max(cnt.values()); first = {}
            for r in rs:
                if reps[r][cid][1] is not None:
                    first.setdefault(reps[r][cid][1], r)
            maj = min([c for c in cnt if cnt[c] == top], key=lambda c: first[c])
            for r in rs:
                raw, can, st = reps[r][cid]
                if can is None:
                    continue
                cf = (can != maj) or (cnt[can] <= 1)
                rf = flags[sid][r].get(cid, False)
                wrong = st != "correct"
                for d_ in (dom, "all"):
                    t = tab[d_]; t["filled"] += 1; t["wrong"] += wrong
                    t["cons_flag"] += cf; t["cons_flag_wrong"] += cf and wrong; t["cons_noflag_wrong"] += (not cf) and wrong
                    t["rec_flag"] += rf; t["rec_flag_wrong"] += rf and wrong; t["rec_noflag_wrong"] += (not rf) and wrong
                    t["both"] += cf and rf; t["both_wrong"] += cf and rf and wrong; t["either"] += cf or rf
    flagres = {}
    for d_, t in tab.items():
        r_ = lambda a_, b_: round(a_ / b_, 4) if b_ else None
        flagres[d_] = {"filled_lines": t["filled"], "error_rate": r_(t["wrong"], t["filled"]),
                       "consensus": {"flagged_share": r_(t["cons_flag"], t["filled"]), "err_in": r_(t["cons_flag_wrong"], t["cons_flag"]),
                                     "err_out": r_(t["cons_noflag_wrong"], t["filled"] - t["cons_flag"]),
                                     "recall": r_(t["cons_flag_wrong"], t["wrong"])},
                       "record": {"flagged_share": r_(t["rec_flag"], t["filled"]), "err_in": r_(t["rec_flag_wrong"], t["rec_flag"]),
                                  "err_out": r_(t["rec_noflag_wrong"], t["filled"] - t["rec_flag"]), "recall": r_(t["rec_flag_wrong"], t["wrong"])},
                       "overlap": {"both": t["both"], "either": t["either"], "jaccard": r_(t["both"], t["either"]),
                                   "err_in_both": r_(t["both_wrong"], t["both"])}}
    res["flags_k5_filled_lines"] = flagres
    res["exploratory"] = "探索批次每組只有 2 份初稿（r1、r2），2 份無法做多數決（平手即全部），略過。"
    (out / "consensus_offline.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res["k"], ensure_ascii=False)[:1500]); print(json.dumps(flagres, ensure_ascii=False)[:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
