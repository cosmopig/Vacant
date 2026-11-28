#!/usr/bin/env python3
"""評分器效度 3：完整性的結構檢查（零成本判定）。足球『出場 (進球)』必填兩個整數：值裡整數少於 2 個（去掉 * 與反引號後）⇒ 旗標『只寫一半』。
同一批 1,747 個有填初稿行，和判別 V1（p<0.5）、紀錄旗標（E 家族定義）、5 份一致度旗標並列（重評標籤；足球不受重評影響）。
公司組列出多值欄位（答案鍵含多個項目）的行數。事後；不叫模型。用法：struct_check.py D1 D2"""
import collections, json, pathlib, re, sys
HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from judge_gemini_analysis import M, lk, auc, stats  # noqa: E402
import judge_pages as P  # noqa: E402
roots = [pathlib.Path(r) for r in sys.argv[1:3]]; D = HERE.parent / "audit"
v1 = {json.loads(l)["key"]: json.loads(l) for l in (D / "judge_gemini_decision_20261128/judge_lines_all.jsonl").read_text().splitlines()}
cls = {json.loads(l)["key"]: json.loads(l)["class"] for l in (D / "judge_v2v3_20261128/err_taxonomy_lines.jsonl").read_text().splitlines()}
plan = json.loads((roots[0] / "RUN.json").read_text())["plan_body"]; truth = M.load_manifests_with_truth(plan)
drafts = collections.defaultdict(dict); er = {}; raw = {}
for root in roots:
    for c0 in sorted(root.glob("cells/*/r[1-5]/c0")):
        sid, rep = c0.parts[-3], int(c0.parts[-2][1:])
        vals = M.SD.parse_report((c0 / "report.md").read_text(errors="replace"), truth[sid]["claims"])
        def cv(x):
            if x in (None, "") or not str(x).strip():
                return None
            c_ = M.canon_strict(x); return c_ if c_ is not None else "RAW:" + " ".join(str(x).split()).lower()
        drafts[sid][rep] = {c["id"]: cv(vals.get(c["id"])) for c in truth[sid]["claims"]}
        m_ = root / "escalation" / sid / f"r{rep}" / "ER" / "meta.json"
        tg = set(json.loads(m_.read_text()).get("target_ids") or []) if m_.is_file() else set()
        for c in truth[sid]["claims"]:
            k = lk(sid, rep, c["id"]); er[k] = c["id"] in tg; raw[k] = vals.get(c["id"])
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
half = lambda v: len(re.findall(r"\d+", re.sub(r"[*`]", "", str(v)))) < 2
rows = []
for k, r in v1.items():
    if r["domain"] != "football" or r["p_supported"] is None:
        continue
    rows.append({"wrong": r["wrong"], "struct": half(raw[k]), "v1": r["p_supported"] < 0.5, "rec": er.get(k, False), "cons": cons.get(k, False),
                 "p": r["p_supported"], "cls": cls.get(k, "correct")})
res = {"note": "足球有填初稿行；旗標＝值的整數少於 2 個。", "football": {"lines": len(rows), "wrong": sum(x["wrong"] for x in rows)}}
for name, f in (("struct_half", lambda x: x["struct"]), ("judge_v1_p<0.5", lambda x: x["v1"]), ("record_flag", lambda x: x["rec"]),
                ("consensus_flag", lambda x: x["cons"]), ("struct_OR_consensus", lambda x: x["struct"] or x["cons"]),
                ("struct_OR_judge_v1", lambda x: x["struct"] or x["v1"]), ("struct_OR_consensus_OR_v1", lambda x: x["struct"] or x["cons"] or x["v1"])):
    res["football"][name] = stats(rows, f)
res["football"]["struct_vs_R-部分"] = {"R-部分_lines": sum(x["cls"] == "R-部分" for x in rows), "flagged_among_R-部分": sum(x["struct"] for x in rows if x["cls"] == "R-部分"),
                                       "struct_flagged_not_R-部分": sum(x["struct"] and x["cls"] != "R-部分" for x in rows)}
# 公司組多值欄位
multi = collections.Counter(); tot = collections.Counter()
for sid, st in truth.items():
    if not sid.startswith("cc"):
        continue
    for c in st["claims"]:
        a = st["truth"][0][c["id"]] or ""; lab = c.get("label", ""); tot[lab] += 1
        n = max(len(P.ticker_pairs(a)), len(re.findall(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b", a)), len(re.findall(r"\(\d{4}[–-]\d{0,4}\)", a)),
                len(re.findall(r"\d+\s+years?\s+ago", a)))
        if n >= 2:
            multi[lab] += 1
res["companies_multivalued_fields"] = {lab: {"answer_keys_multivalued": multi[lab], "answer_keys_total": tot[lab]} for lab in sorted(multi)}
o = D / "scorer_validity_20261128/struct_check.json"; o.write_text(json.dumps(res, ensure_ascii=False, indent=1))
print(json.dumps(res, ensure_ascii=False, indent=1))
