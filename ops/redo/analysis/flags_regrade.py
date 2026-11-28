#!/usr/bin/env python3
"""敏感度第 3 項：用第二正規化器修正「錯」的標籤後，紀錄旗標（E 家族定義）、5 份一致度旗標、判別 V1 在各組的 標出的錯／放行的錯／召回 與 AUC。
修正＝步驟 0 分類為 U-等值或 K-等值的錯行改算對（不排除，改標籤）。事後；不叫模型。用法：flags_regrade.py R1 R2"""
import collections, json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import judge_gemini_analysis as G  # noqa: E402
from judge_gemini_analysis import M, lk, auc, stats  # noqa: E402
roots = [pathlib.Path(r) for r in sys.argv[1:3]]
D = pathlib.Path(__file__).resolve().parents[1] / "audit"
rows = [json.loads(l) for l in (D / "judge_gemini_decision_20261128/judge_lines_all.jsonl").read_text().splitlines()]
cls = {json.loads(l)["key"]: json.loads(l)["class"] for l in (D / "judge_v2v3_20261128/err_taxonomy_lines.jsonl").read_text().splitlines()}
plan = json.loads((roots[0] / "RUN.json").read_text())["plan_body"]; truth = M.load_manifests_with_truth(plan)
drafts = collections.defaultdict(dict); er = {}
for root in roots:
    for c0 in sorted(root.glob("cells/*/r[1-5]/c0")):
        sid, rep = c0.parts[-3], int(c0.parts[-2][1:])
        vals = M.SD.parse_report((c0 / "report.md").read_text(errors="replace"), truth[sid]["claims"])
        def cv(raw):
            if raw in (None, "") or not str(raw).strip():
                return None
            c_ = M.canon_strict(raw); return c_ if c_ is not None else "RAW:" + " ".join(str(raw).split()).lower()
        drafts[sid][rep] = {c["id"]: cv(vals.get(c["id"])) for c in truth[sid]["claims"]}
        m_ = root / "escalation" / sid / f"r{rep}" / "ER" / "meta.json"
        tg = set(json.loads(m_.read_text()).get("target_ids") or []) if m_.is_file() else set()
        for c in truth[sid]["claims"]:
            er[lk(sid, rep, c["id"])] = c["id"] in tg
cons = {}
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
res = {"note": "事後敏感度；『錯』的標籤用第二正規化器修正（U-等值、K-等值改算對）；旗標本身不變。紀錄旗標＝E 家族定義（ER 送出的有填行）。", "by_domain": {}}
for label_mode in ("original", "regraded"):
    for dom in ("companies", "football", "all"):
        rr = []
        for r in rows:
            if dom != "all" and r["domain"] != dom:
                continue
            w = r["wrong"] and not (label_mode == "regraded" and cls.get(r["key"]) in ("U-等值", "K-等值"))
            rr.append({"wrong": w, "p": r["p_supported"], "rec": er.get(r["key"], False), "cons": cons.get(r["key"], False)})
        res["by_domain"][f"{dom}|{label_mode}"] = {
            "lines": len(rr), "wrong": sum(x["wrong"] for x in rr),
            "record_flag": stats(rr, lambda x: x["rec"]), "consensus_flag": stats(rr, lambda x: x["cons"]),
            "judge_v1_p<0.5": stats(rr, lambda x: x["p"] < 0.5),
            "auc_judge_v1": auc([1 - x["p"] for x in rr], [x["wrong"] for x in rr]),
            "auc_record_flag": auc([float(x["rec"]) for x in rr], [x["wrong"] for x in rr]),
            "auc_consensus_flag": auc([float(x["cons"]) for x in rr], [x["wrong"] for x in rr])}
(D / "judge_v2v3_20261128/flags_regrade.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
for k, v in res["by_domain"].items():
    print(k, "lines", v["lines"], "wrong", v["wrong"], "| rec", v["record_flag"], "| cons", v["consensus_flag"], "| V1", v["judge_v1_p<0.5"], "| AUC V1/rec/cons", v["auc_judge_v1"], v["auc_record_flag"], v["auc_consensus_flag"])
