#!/usr/bin/env python3
"""步驟 0：錯行分類（規則＝ops/redo/audit/judge_v2v3_20261128/PLAN.md，呼叫前已提交）。事後、探索性；不叫模型。
公開輸出：每個錯行的 HMAC 行鍵、類別、V1 機率；計數表；判別機率 × 類別交叉。私有輸出：抽樣核對用的原文（--private）。
用法：judge_err_taxonomy.py R1 R2 --out DIR --private DIR"""
from __future__ import annotations
import argparse, collections, json, pathlib, random, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from audit_key import audit_hmac  # noqa: E402
import judge_pages as P  # noqa: E402
from judge_pages import M, SRC  # noqa: E402
lk = lambda sid, rep, cid: audit_hmac(f"{sid}|r{rep}|{cid}")


def classify(val, ans_list, label, pages):
    ans = ans_list[0]
    parsed = M.canon_strict(val) is not None
    ke = P.key_equiv(val, ans, label)
    if ke:
        return ("U-等值" if not parsed else "K-等值"), ke
    if not parsed:
        return "U", None
    cv = M.canon_strict(val)
    if any(cv == M.canon_strict(a) for a in ans_list[1:] if a):
        return "S", None
    if not P.on_pages(pages, val):
        return "F", None
    if P.unit_or_round(val, ans):
        return "R-單位", None
    if P.norm(val) and P.norm(val) != P.norm(ans) and P.norm(val) in P.norm(ans):
        return "R-部分", None
    for _, h in pages:
        tbs = P.parse_tables(h)
        vl = P.row_locs(tbs, val); al = P.row_locs(tbs, ans)
        if not vl or not al:
            continue
        for (i, j, k) in vl:
            for (ai, aj, ak) in al:
                if i == ai and j == aj and k != ak:
                    return "R-欄", None
        for (i, j, k) in vl:
            for (ai, aj, ak) in al:
                if i == ai and k == ak and j != aj:
                    return "R-期", None
    return "R-他處", None


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("roots", nargs=2); ap.add_argument("--out", required=True); ap.add_argument("--private", required=True)
    a = ap.parse_args(); out = pathlib.Path(a.out); priv = pathlib.Path(a.private); priv.mkdir(parents=True, exist_ok=True)
    roots = [pathlib.Path(r) for r in a.roots]
    plan = json.loads((roots[0] / "RUN.json").read_text())["plan_body"]; truth = M.load_manifests_with_truth(plan)
    v1 = {json.loads(l)["key"]: json.loads(l) for l in (out.parent / "judge_gemini_decision_20261128" / "judge_lines_all.jsonl").read_text().splitlines()}
    rows = []; privrows = []
    for root in roots:
        for c0 in sorted(root.glob("cells/*/r[1-5]/c0")):
            sid, rep = c0.parts[-3], int(c0.parts[-2][1:])
            vals = M.SD.parse_report((c0 / "report.md").read_text(errors="replace"), truth[sid]["claims"]); pages = None
            for c in truth[sid]["claims"]:
                raw = vals.get(c["id"])
                if raw in (None, "") or not str(raw).strip():
                    continue
                if M.strict_status(raw, c["id"], truth[sid]["truth"], 0) == "correct":
                    continue
                if pages is None:
                    pages = P.fetched_pages(c0)
                ans_list = [t.get(c["id"]) for t in truth[sid]["truth"]]
                cls, sub = classify(raw, ans_list, c.get("label", ""), pages)
                k = lk(sid, rep, c["id"]); dom = "companies" if sid.startswith("cc") else "football"
                rows.append({"key": k, "set": sid, "domain": dom, "class": cls, "equiv_rule": sub, "p_v1": v1[k]["p_supported"]})
                privrows.append({"key": k, "set": sid, "rep": rep, "claim": c["id"], "label": c.get("label"), "value": raw, "answer": ans_list[0], "class": cls})
    (out / "err_taxonomy_lines.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    (priv / "err_taxonomy_private.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in privrows))
    tab = {}
    for dom in ("companies", "football"):
        rr = [r for r in rows if r["domain"] == dom]; cnt = collections.Counter(r["class"] for r in rr)
        cross = {}
        for cls in sorted(cnt):
            ps = [r["p_v1"] for r in rr if r["class"] == cls]
            cross[cls] = {"n": len(ps), "p>=0.9": sum(p >= 0.9 for p in ps), "p<0.5": sum(p < 0.5 for p in ps), "mean_p": round(sum(ps) / len(ps), 3)}
        tab[dom] = {"wrong_lines": len(rr), "by_class": dict(cnt), "v1_prob_by_class": cross,
                    "equiv_rules": dict(collections.Counter(r["equiv_rule"] for r in rr if r["equiv_rule"]))}
    # 抽樣核對清單（私有）：每類 20 行
    rng = random.Random(20261128); sample = []
    for cls in sorted({r["class"] for r in privrows}):
        grp = [r for r in privrows if r["class"] == cls]; rng.shuffle(grp); sample += grp[:20]
    (priv / "audit_sample.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in sample))
    (out / "err_taxonomy_summary.json").write_text(json.dumps({"note": "步驟 0；規則見 PLAN.md；事後探索性。", "by_domain": tab}, ensure_ascii=False, indent=1))
    print(json.dumps(tab, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
