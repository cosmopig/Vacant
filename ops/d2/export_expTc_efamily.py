#!/usr/bin/env python3
"""確認批次 E 家族稽核匯出（2026-11-28；vacant-cloud 稽核要求）：逐份初稿 × 臂的計數，不含任何值。
輸出（out_dir）：
- `efamily_per_draft_arm.jsonl`：每份初稿 × 臂（A、EB、ER、EN）：n_claims、正確行數、送出的空白／有填行數、改對（空白／有填）、
  傷害 B→W、C→W/D；臂沒有呼叫時標 called=false。
- `efamily_per_draft_pools.jsonl`：每份初稿：ER 標到的有填行數與其中錯幾行；沒被標的有填行數與其中錯幾行；EN 抽到的有填行數與其中錯幾行。
- `efamily_hp_per_set.jsonl`：HP 每組：正確行數、n_claims、輸入／輸出 token、美元。
- `efamily_c9_fixed_not_in_pages.jsonl`：改對的行裡，值不在給它的頁面裡的逐行清單（組、次、臂、行 id；不含值）。
空白的判定：解析出的值是 None 或空字串（和 flags_v2 的 is_blank 一致）。
用法：export_expTc_efamily.py <drafts_root> [<drafts_root> ...] --out <dir>
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, sys
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "ops" / "d2"))
from ops.d2 import expT_metrics as M  # noqa: E402
from ops.d2 import expTc_confirm_analysis as CA  # noqa: E402
from vacant_network.trace import sources as S  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("roots", nargs="+"); ap.add_argument("--out", required=True); a = ap.parse_args()
    roots = [pathlib.Path(r) for r in a.roots]; out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    plan = json.loads((roots[0] / "RUN.json").read_text())["plan_body"]; truth = M.load_manifests_with_truth(plan)
    def parse(sid, txt):
        vals = CA.SD.parse_report(txt, truth[sid]["claims"])
        return {c["id"]: (None if vals.get(c["id"]) in (None, "") else vals.get(c["id"])) for c in truth[sid]["claims"]}
    def st(sid, vals):
        return {cid: ("blank" if v is None else M.strict_status(v, cid, truth[sid]["truth"], 0)) for cid, v in vals.items()}
    rows, pools, c9 = [], [], []
    for root in roots:
        for c0 in sorted(root.glob("cells/*/r[1-5]/c0")):
            sid, rep = c0.parts[-3], c0.parts[-2]
            av = parse(sid, (c0 / "report.md").read_text(errors="replace")); ast = st(sid, av); n = len(ast)
            rows.append({"set": sid, "rep": rep, "arm": "A", "n_claims": n, "correct": sum(s == "correct" for s in ast.values()),
                         "blank": sum(s == "blank" for s in ast.values())})
            targets = {}
            for arm in ("EB", "ER", "EN"):
                od = root / "escalation" / sid / rep / arm; m = json.loads((od / "meta.json").read_text())
                vv = parse(sid, (od / "report.md").read_text(errors="replace")); ss = st(sid, vv)
                tg = list(m.get("target_ids") or []); targets[arm] = set(tg)
                r = {"set": sid, "rep": rep, "arm": arm, "called": bool(m.get("called", bool(tg))), "n_claims": n,
                     "correct": sum(s == "correct" for s in ss.values()),
                     "sent_blank": sum(ast[c] == "blank" for c in tg), "sent_filled": sum(ast[c] != "blank" for c in tg),
                     "fixed_blank": sum(ast[c] == "blank" and ss[c] == "correct" for c in tg),
                     "fixed_filled": sum(ast[c] not in ("blank", "correct") and ss[c] == "correct" for c in tg),
                     "harm_b2w": sum(ast[c] == "blank" and ss[c] not in ("blank", "correct") for c in ss),
                     "harm_c2w_or_d": sum(ast[c] == "correct" and ss[c] != "correct" for c in ss)}
                rows.append(r)
                for c in tg:
                    if ss[c] == "correct" and ast[c] != "correct":
                        shas = set((m.get("page_shas") or {}).values())
                        files = [f for f in (c0 / "site_frozen").glob("*") if f.is_file() and hashlib.sha256(f.read_bytes()).hexdigest() in shas] if shas else []
                        if not files:
                            pinned = json.loads((c0 / "site_snapshot_sha256.json").read_text())
                            names = {u.rsplit("/", 1)[-1] for u in (m.get("pages_given") or [])}
                            files = [c0 / "site_frozen" / nm for nm in pinned if nm in names]
                        if not any(S.plain_contains(f.read_text(errors="replace"), vv.get(c) or "") for f in files):
                            c9.append({"set": sid, "rep": rep, "arm": arm, "claim_id": c})
            filled = [c for c, s in ast.items() if s != "blank"]
            erf = [c for c in filled if c in targets["ER"]]; unf = [c for c in filled if c not in targets["ER"]]
            enf = [c for c in filled if c in targets["EN"]]
            pools.append({"set": sid, "rep": rep, "er_flagged_filled": len(erf), "er_flagged_filled_wrong": sum(ast[c] != "correct" for c in erf),
                          "unflagged_filled": len(unf), "unflagged_filled_wrong": sum(ast[c] != "correct" for c in unf),
                          "en_sampled_filled": len(enf), "en_sampled_filled_wrong": sum(ast[c] != "correct" for c in enf)})
    hp = []
    for sid in sorted(truth):
        hd = roots[0] / "escalation_hp" / sid / "hp1"
        if (hd / "report.md").is_file():
            ss = st(sid, parse(sid, (hd / "report.md").read_text(errors="replace"))); m = json.loads((hd / "meta.json").read_text())
            hp.append({"set": sid, "n_claims": len(ss), "correct": sum(s == "correct" for s in ss.values()),
                       **{k: m.get(k) for k in ("input_tokens", "output_tokens", "cost_usd") if k in m}})
    for name, data in (("efamily_per_draft_arm", rows), ("efamily_per_draft_pools", pools), ("efamily_hp_per_set", hp), ("efamily_c9_fixed_not_in_pages", c9)):
        (out / f"{name}.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in data))
    agg = {}
    for arm in ("EB", "ER", "EN"):
        rs = [r for r in rows if r["arm"] == arm]
        agg[arm] = {k: sum(r[k] for r in rs) for k in ("sent_blank", "sent_filled", "fixed_blank", "fixed_filled", "harm_b2w", "harm_c2w_or_d")}
    print(json.dumps(agg, ensure_ascii=False)); print("c9 by arm", {a_: sum(1 for x in c9 if x["arm"] == a_) for a_ in ("ER", "EN", "EB")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
