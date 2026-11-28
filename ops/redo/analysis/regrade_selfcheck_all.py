#!/usr/bin/env python3
"""第二正規化器：不看欄名版（regrade_sensitivity.key_equiv_nolabel）對看欄名版（judge_pages.key_equiv）在確認批次所有產出上的逐行一致性：
初稿 c0、回饋四臂 A/G/T/TB 的最終報告、E 三臂 EB/ER/EN 的報告。只看原評分判非對、且有值的行。用法：regrade_selfcheck_all.py DRAFTS1 DRAFTS2 FB1 FB2"""
import collections, json, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import judge_pages as P  # noqa: E402
from regrade_sensitivity import key_equiv_nolabel, M, _ORIG  # noqa: E402
d1, d2, f1, f2 = [pathlib.Path(x) for x in sys.argv[1:5]]
plan = json.loads((d1 / "RUN.json").read_text())["plan_body"]; truth = M.load_manifests_with_truth(plan)
reports = []
for root in (d1, d2):
    reports += [(p, "c0") for p in root.glob("cells/*/r[1-5]/c0/report.md")]
    reports += [(p, p.parts[-2]) for p in root.glob("escalation/*/r[1-5]/E[BRN]/report.md")]
for root in (f1, f2):
    reports += [(p, p.parts[-2]) for p in root.glob("cells/*/r[1-5]/*/report.md") if p.parts[-2] in ("A", "G", "T", "TB")]
cnt = collections.Counter(); dis = []
for p, arm in reports:
    sid = next(x for x in p.parts if x.startswith(("cc-", "ff-")))
    vals = M.SD.parse_report(p.read_text(errors="replace"), truth[sid]["claims"])
    for c in truth[sid]["claims"]:
        v = vals.get(c["id"])
        if v in (None, "") or not str(v).strip() or _ORIG(v, c["id"], truth[sid]["truth"], 0) == "correct":
            continue
        a = P.key_equiv(v, truth[sid]["truth"][0][c["id"]], c.get("label", "")) is not None
        b = key_equiv_nolabel(v, truth[sid]["truth"][0][c["id"]]) is not None
        cnt[(arm, a == b)] += 1
        if a != b:
            dis.append({"arm": arm, "set": sid, "field": c.get("label"), "label_version": a, "nolabel_version": b})
res = {"reports": len(reports), "by_arm": {f"{k[0]}|{'agree' if k[1] else 'disagree'}": v for k, v in sorted(cnt.items())},
       "agree": sum(v for k, v in cnt.items() if k[1]), "disagree": len(dis), "disagreements": dis}
(HERE.parent / "audit/judge_v2v3_20261128/regrade/selfcheck_all_outputs.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
print(json.dumps({k: res[k] for k in ("reports", "agree", "disagree", "by_arm")}, ensure_ascii=False))
