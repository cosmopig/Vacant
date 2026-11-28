#!/usr/bin/env python3
"""實驗 T 確認批次：升級臂（附錄 C）的固定分析。在任何升級呼叫之前提交；sha256 記在附錄 C。2026-11-28。

單位＝一份初稿（組, 次），群集＝組（組加權：先組內平均、再組間平均）。分數＝嚴格評分的正確行比例（`expT_metrics.strict_status`，對照 revision 0）。
主比較（第二個 Holm 家族，和 A/G/T/TB 家族分開；Holm 只作用於三個置換 p）：
  ER−A：差 ≥5pp、95% 區間下界 >0、Holm 後 p<0.05 ⇒「紀錄引導的升級比初稿好」。
  ER−EN：只用 ER 有標到有填行的初稿。90% 區間完全在 (−5, +5) 內 ⇒「差小於 5pp」；≥5pp 且下界 >0 且 Holm p<0.05 ⇒「ER 比 EN 好」；否則依 B1 格式「沒有量到差別」。
  ER−EB：同上（±5pp）。
另報（只描述）：B5 三段的非空白初稿分層、拿掉前 2 組、每臂每份的 Haiku 美元與 token、截斷次數、整份回覆被截斷而等於初稿的份數、
  「每多對一行花多少」（ER 比 A 多對的行數 ÷ ER 的花費）、和後續修訂相符但和 revision 0 不符的行數（各臂）、
  E 臂改對的行裡值有沒有出現在給它的頁面文字裡、ER 與 EN 的行重疊率。兩種成本口徑並列：(i) 只算 Haiku 美元；(ii) 9B token／牆鐘＋Haiku 美元。
用法：expTc_escalation_analysis.py --drafts D1 D2 --k K --out OUT.json
"""
from __future__ import annotations
import argparse, collections, json, pathlib, sys
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from ops.d2 import expT_metrics as M  # noqa: E402
from ops.d2 import expTc_confirm_analysis as A  # noqa: E402
from vacant_network.trace import sources as S  # noqa: E402

DELTA = 0.05


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--drafts", nargs="+", required=True); ap.add_argument("--k", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = {}; cost = collections.defaultdict(lambda: collections.Counter()); fut = collections.Counter(); inpage = collections.Counter()
    overlap = []
    for r in a.drafts:
        root = pathlib.Path(r); plan = json.loads((root / "RUN.json").read_text())["plan_body"]; truth = M.load_manifests_with_truth(plan)
        for c0 in sorted(root.glob("cells/*/r*/c0")):
            sid, rep = c0.parts[-3], int(c0.parts[-2][1:])
            if rep > a.k:
                continue
            claims = truth[sid]["claims"]; tr = truth[sid]["truth"]
            draft = M.SD.parse_report((c0 / "report.md").read_text(errors="replace"), claims)
            rec = {"A": draft}; metas = {}; ok = True
            for arm in ("EB", "ER", "EN"):
                d = root / "escalation" / sid / f"r{rep}" / arm
                if not (d / "meta.json").is_file():
                    ok = False; break
                m = json.loads((d / "meta.json").read_text()); metas[arm] = m
                if m.get("infra_void"):
                    ok = False; break
                rec[arm] = M.SD.parse_report((d / "report.md").read_text(errors="replace"), claims)
                if m.get("called"):
                    cost[arm]["usd"] += m.get("cost_usd", 0); cost[arm]["in"] += m.get("input_tokens", 0); cost[arm]["out"] += m.get("output_tokens", 0)
                    cost[arm]["calls"] += 1; cost[arm]["truncated"] += bool(m.get("truncated"))
                    cost[arm]["whole_truncated_eq_draft"] += bool(m.get("truncated") and not m.get("replaced_ids"))
            if not ok:
                continue
            st = {arm: {c["id"]: M.strict_status(v.get(c["id"]), c["id"], tr, 0) for c in claims} for arm, v in rec.items()}
            prop = {arm: sum(x == "correct" for x in s.values()) / len(claims) for arm, s in st.items()}
            filled = sum(1 for c in claims if draft.get(c["id"]) is not None)
            sel = metas["ER"].get("selection", {})
            rows[(sid, rep)] = {"prop": prop, "nonblank": filled >= 1, "er_has_filled": sel.get("er_has_filled"),
                                "extra_correct_ER": sum(1 for c in claims if st["ER"][c["id"]] == "correct" and st["A"][c["id"]] != "correct")}
            if sel:
                overlap.append(sel.get("overlap_ER_EN", 0) / max(1, len(metas["ER"].get("target_ids") or [])))
            for arm in ("EB", "ER", "EN"):
                for c in claims:
                    v = M.canon_strict(rec[arm].get(c["id"]))
                    if v is not None and v != M.canon_strict(tr[0][c["id"]]) and any(v == M.canon_strict(t[c["id"]]) for t in tr[1:]):
                        fut[arm] += 1
                    if st[arm][c["id"]] == "correct" and st["A"][c["id"]] != "correct":
                        pages = list((metas[arm].get("page_shas") or {}).keys())
                        txts = [(c0 / "site_frozen" / u.rsplit("/", 1)[-1]).read_text(errors="replace") for u in pages if (c0 / "site_frozen" / u.rsplit("/", 1)[-1]).is_file()]
                        inpage[(arm, any(S.plain_contains(t, rec[arm].get(c["id"]) or "") for t in txts))] += 1
    def comp(t, c, keep):
        d = collections.defaultdict(list)
        for (sid, rep), r_ in rows.items():
            if keep(r_):
                d[sid].append(r_["prop"][t] - r_["prop"][c])
        res = A.summarize(dict(d), DELTA); res["drop_top2_sets"] = A.drop_top(dict(d), DELTA, "set"); return res
    allk = lambda r_: True
    er_f = lambda r_: bool(r_["er_has_filled"])
    main_ = {"ER_vs_A": comp("ER", "A", allk), "ER_vs_EN": comp("ER", "EN", er_f), "ER_vs_EB": comp("ER", "EB", allk)}
    nb = {"ER_vs_A": comp("ER", "A", lambda r_: r_["nonblank"]), "ER_vs_EN": comp("ER", "EN", lambda r_: r_["nonblank"] and er_f(r_)),
          "ER_vs_EB": comp("ER", "EB", lambda r_: r_["nonblank"])}
    h = A.holm({k: v.get("perm_p") for k, v in main_.items()})
    ver = {}
    for k, v in main_.items():
        if v.get("diff") is None:
            ver[k] = "no_data"; continue
        better = v["diff"] >= DELTA and v["ci95"] and v["ci95"][0] > 0 and h.get(k) is not None and h[k] < 0.05
        ver[k] = ("pass" if k == "ER_vs_A" else "ER_better") if better else ("equivalent_within_5pp" if v.get("equivalent_within_delta") else "no_difference_measured")
        if better:
            ver[k + "_stratum"] = A.strat_verdict(v, nb[k], DELTA)
            if not v["drop_top2_sets"].get("ci95") or v["drop_top2_sets"]["ci95"][0] <= 0:
                ver[k + "_few_sets"] = "driven_by_few_sets"
    extra = sum(r_["extra_correct_ER"] for r_ in rows.values())
    out = {"drafts": len(rows), "main": main_, "nonblank": nb, "holm_family2": h, "verdict": verdict_fix(ver),
           "cost": {k: dict(v) for k, v in cost.items()}, "usd_per_extra_correct_line_ER": round(cost["ER"]["usd"] / extra, 5) if extra else None,
           "future_revision_match_lines": dict(fut), "corrected_value_in_given_pages": {f"{k[0]}|{k[1]}": v for k, v in inpage.items()},
           "ER_EN_overlap_mean": round(sum(overlap) / len(overlap), 4) if overlap else None,
           "note": "HF（Haiku 自己做整份）若有跑，另檔報；不進 Holm。"}
    pathlib.Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("drafts", "verdict", "holm_family2", "usd_per_extra_correct_line_ER")}, ensure_ascii=False))


def verdict_fix(v):
    return v


if __name__ == "__main__":
    main()
