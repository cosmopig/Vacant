#!/usr/bin/env python3
"""判別模型先導的離線分析（事後、探索性；用答案鍵評分）。讀 judge_lines_all.jsonl（HMAC 行鍵、機率、紀錄旗標、對錯），
重算同一批行的 5 份一致度旗標（值≠多數 或 同意份數≤1），算：AUC、各門檻的旗標內／外錯誤率與召回（分足球／公司）、三種旗標的重疊、
10 桶校準、一致度 OR 判別模型。輸出只有計數與比例。用法：judge_gemini_analysis.py <drafts_root> <drafts_root> --dir OUTDIR"""
from __future__ import annotations
import argparse, collections, hashlib, hmac, json, pathlib, sys
REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "ops" / "d2"))
from ops.d2 import expT_metrics as M  # noqa: E402
KEY = (pathlib.Path.home() / ".config/vacant/audit_hmac.key").read_text().strip().encode()
lk = lambda sid, rep, cid: hmac.new(KEY, f"{sid}|r{rep}|{cid}".encode(), hashlib.sha256).hexdigest()[:20]


def auc(scores, labels):
    pos = [s for s, y in zip(scores, labels) if y]; neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return None
    allv = sorted([(s, 1) for s in pos] + [(s, 0) for s in neg]); ranks = {}
    i = 0
    while i < len(allv):
        j = i
        while j < len(allv) and allv[j][0] == allv[i][0]:
            j += 1
        for k in range(i, j):
            ranks.setdefault(allv[k][0], (i + j + 1) / 2)
        i = j
    rp = sum(ranks[s] for s in pos)
    return round((rp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)), 4)


def stats(rows, flagf):
    f = [r for r in rows if flagf(r)]; nf = [r for r in rows if not flagf(r)]; w = sum(r["wrong"] for r in rows)
    r_ = lambda a, b: round(a / b, 4) if b else None
    return {"flagged_share": r_(len(f), len(rows)), "err_in": r_(sum(x["wrong"] for x in f), len(f)), "err_out": r_(sum(x["wrong"] for x in nf), len(nf)),
            "recall": r_(sum(x["wrong"] for x in f), w), "n_flagged": len(f)}


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("roots", nargs=2); ap.add_argument("--dir", required=True); a = ap.parse_args()
    d = pathlib.Path(a.dir); rows = [json.loads(l) for l in (d / "judge_lines_all.jsonl").read_text().splitlines()]
    roots = [pathlib.Path(r) for r in a.roots]
    plan = json.loads((roots[0] / "RUN.json").read_text())["plan_body"]; truth = M.load_manifests_with_truth(plan)
    cons = {}
    for root in roots:
        pass
    drafts = collections.defaultdict(dict); erflag = {}
    for root in roots:
        for c0 in sorted(root.glob("cells/*/r[1-5]/c0")):
            sid, rep = c0.parts[-3], int(c0.parts[-2][1:])
            vals = M.SD.parse_report((c0 / "report.md").read_text(errors="replace"), truth[sid]["claims"])
            def cv(raw):
                if raw in (None, "") or not str(raw).strip():
                    return None
                c_ = M.canon_strict(raw)
                return c_ if c_ is not None else "RAW:" + " ".join(str(raw).split()).lower()   # 解析不出的值用原字串（事後選定）
            drafts[sid][rep] = {c["id"]: cv(vals.get(c["id"])) for c in truth[sid]["claims"]}
            m_ = root / "escalation" / sid / f"r{rep}" / "ER" / "meta.json"
            ertg = set(json.loads(m_.read_text()).get("target_ids") or []) if m_.is_file() else set()
            for c in truth[sid]["claims"]:
                erflag[lk(sid, rep, c["id"])] = c["id"] in ertg
    for sid, reps in drafts.items():
        rs = sorted(reps)
        for c in truth[sid]["claims"]:
            cid = c["id"]; cnt = collections.Counter(reps[r][cid] for r in rs if reps[r][cid] is not None)
            if not cnt:
                continue
            top = max(cnt.values()); first = {}
            for r in rs:
                if reps[r][cid] is not None:
                    first.setdefault(reps[r][cid], r)
            maj = min([v for v in cnt if cnt[v] == top], key=lambda v: first[v])
            for r in rs:
                v = reps[r][cid]
                if v is not None:
                    cons[lk(sid, r, cid)] = (v != maj) or (cnt[v] <= 1)
    rows = [dict(r, cons_flag=cons.get(r["key"], False), record_flag_flags_v2=r["record_flag"], record_flag=erflag.get(r["key"], False))
            for r in rows if r["p_supported"] is not None]
    res = {"note": "事後探索性；判別模型只看公開頁面文字＋欄位＋值；對錯用答案鍵離線評分。",
           "definitions": {"denominator": "有填行＝初稿該行的值非空（canon_strict 解析不出的值也算，算錯）",
                           "record_flag": "E 家族定義：該份初稿在 ER 臂被送出的有填行（escalation/*/ER/meta.json 的 target_ids），和已定稿結論一致；flags_v2 的 flagged 另存 record_flag_flags_v2，只對照",
                           "consensus_flag": "事後選定：值（canon_strict；解析不出用原字串）≠ 5 份裡的多數值，或同值份數 ≤1；多數平手取 r 最小者的值；空白不參與"},
           "lines": len(rows), "by_domain": {}}
    for dom in ("football", "companies", "all"):
        rr = [r for r in rows if dom == "all" or r["domain"] == dom]
        out = {"lines": len(rr), "error_rate": round(sum(r["wrong"] for r in rr) / len(rr), 4),
               "auc_judge_unsupported": auc([1 - r["p_supported"] for r in rr], [r["wrong"] for r in rr]),
               "judge": {f"p<{t}": stats(rr, lambda r, t=t: r["p_supported"] < t) for t in (0.1, 0.3, 0.5, 0.7, 0.9)},
               "record_flag": stats(rr, lambda r: r["record_flag"]), "record_flag_flags_v2": stats(rr, lambda r: r["record_flag_flags_v2"]),
               "consensus_flag": stats(rr, lambda r: r["cons_flag"]),
               "consensus_OR_judge_p<0.5": stats(rr, lambda r: r["cons_flag"] or r["p_supported"] < 0.5)}
        j = lambda r: r["p_supported"] < 0.5
        out["overlap_at_p<0.5"] = {"judge&record": sum(1 for r in rr if j(r) and r["record_flag"]), "judge&consensus": sum(1 for r in rr if j(r) and r["cons_flag"]),
                                   "record&consensus": sum(1 for r in rr if r["record_flag"] and r["cons_flag"]),
                                   "all_three": sum(1 for r in rr if j(r) and r["record_flag"] and r["cons_flag"])}
        bins = collections.defaultdict(lambda: [0, 0, 0.0])
        for r in rr:
            b = min(9, int(r["p_supported"] * 10)); bins[b][0] += 1; bins[b][1] += (not r["wrong"]); bins[b][2] += r["p_supported"]
        out["calibration_p_supported_vs_correct"] = {f"{b/10:.1f}-{(b+1)/10:.1f}": {"n": v[0], "mean_p": round(v[2] / v[0], 3), "correct_rate": round(v[1] / v[0], 3)}
                                                     for b, v in sorted(bins.items())}
        res["by_domain"][dom] = out
    (d / "judge_analysis.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: {kk: v[kk] for kk in ("lines", "error_rate", "auc_judge_unsupported")} for k, v in res["by_domain"].items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
