#!/usr/bin/env python3
"""實驗 T 確認批次：升級臂（附錄 C＋附錄 C 補充 C1–C11）的固定分析，第二版。在任何升級呼叫之前提交；sha256 記在附錄 C 補充。2026-11-28。

單位＝一份初稿（組, 次），群集＝組（組加權）。分數＝嚴格評分的正確行比例（對照 revision 0）。
**三臂沒有全部完成**（任一臂 budget_cap 或 infra_void 或缺）的初稿，從 E 家族所有比較中排除並列名（C2）；被擋下的初稿 >10% ⇒ 判定「未定（花費上限）」。
主比較（第二個 Holm 家族；Holm 只作用於三個置換 p）：
  ER−A（「紀錄引導的升級（含空白行）比初稿好」）：≥5pp、95% 下界 >0、Holm p<0.05；過關時若 ER 的 harm_total_rate 比 A 高且配對下界 >0 ⇒ 加「以錯換填」（C4(2)）。
  ER−EN（「在交同樣多有填行的條件下，紀錄挑的行比隨機挑的好」）：只用 ER 有標到有填行的初稿；≥5pp、下界 >0、Holm p<0.05 ⇒ 過；90% 區間在 ±5pp 內 ⇒ 等價。
  ER−EB（「多交有填行有沒有帶來東西」）：同上。
另報（只描述）：B5 三段（非空白初稿分層）、B6 拿掉前 2 組、每臂對 A 的 harm_total_rate／C→W/D／B→W（C4(1)）、公司／足球兩層（C4(3)、B35）、
  公司層 ER 交出的有填行裡「原值本來就對」的比例、排除 B27 量具缺口初稿的版本（C4(4)）、ER／EN 只在有填行上的改對數與傷害數（C6(2)）、
  EN 有差額的初稿排除版（C7）、重疊率、每臂花費／token／截斷、每多對一行的花費、和後續修訂相符的行數（含 HP）、
  E 臂改對的值是否在給它的頁面裡（用 page_shas 對凍結站實際檔案，C9）、EB 在空白初稿上的效果（C11）、HP 的正確率與每組成本（C10，不進 Holm）。
用法：expTc_escalation_analysis.py --drafts D1 D2 --k K [--b27 FILE] --out OUT.json
"""
from __future__ import annotations
import argparse, collections, hashlib, json, pathlib, sys
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from ops.d2 import expT_metrics as M  # noqa: E402
from ops.d2 import expTc_confirm_analysis as A  # noqa: E402
from vacant_network.trace import sources as S  # noqa: E402

DELTA = 0.05; ARMS = ("EB", "ER", "EN")


def st_of(vals, claims, tr):
    return {c["id"]: M.strict_status(vals.get(c["id"]), c["id"], tr, 0) for c in claims}


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--drafts", nargs="+", required=True); ap.add_argument("--k", type=int, required=True)
    ap.add_argument("--b27"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    b27 = {(x[0], int(x[1])) for x in json.loads(pathlib.Path(a.b27).read_text())} if a.b27 else set()
    rows, excluded = {}, []; cost = collections.defaultdict(collections.Counter); fut = collections.Counter(); inpage = collections.Counter()
    company_er_sent_filled = collections.Counter(); filled_only = collections.defaultdict(collections.Counter); overlap = []
    total = 0
    for r in a.drafts:
        root = pathlib.Path(r); plan = json.loads((root / "RUN.json").read_text())["plan_body"]; truth = M.load_manifests_with_truth(plan)
        for c0 in sorted(root.glob("cells/*/r*/c0")):
            sid, rep = c0.parts[-3], int(c0.parts[-2][1:])
            if rep > a.k:
                continue
            total += 1
            claims = truth[sid]["claims"]; tr = truth[sid]["truth"]
            draft = M.SD.parse_report((c0 / "report.md").read_text(errors="replace"), claims)
            vals = {"A": draft}; metas = {}; why = None
            for arm in ARMS:
                d = root / "escalation" / sid / f"r{rep}" / arm
                if not (d / "meta.json").is_file():
                    why = f"{arm}:missing"; break
                m = json.loads((d / "meta.json").read_text()); metas[arm] = m
                if m.get("budget_cap") or m.get("infra_void") or not (d / "report.md").is_file():
                    why = f"{arm}:{'budget_cap' if m.get('budget_cap') else 'infra_void' if m.get('infra_void') else 'no_report'}"; break
                vals[arm] = M.SD.parse_report((d / "report.md").read_text(errors="replace"), claims)
            if why:
                excluded.append({"set": sid, "rep": rep, "why": why}); continue
            st = {k: st_of(v, claims, tr) for k, v in vals.items()}
            n = len(claims)
            def harm(arm):
                c2w = sum(1 for c in claims if st["A"][c["id"]] == "correct" and st[arm][c["id"]] != "correct")
                b2w = sum(1 for c in claims if draft.get(c["id"]) is None and st[arm][c["id"]] == "wrong")
                return c2w, b2w
            hm = {arm: harm(arm) for arm in ARMS}
            sel = metas["ER"].get("selection", {})
            rows[(sid, rep)] = {"prop": {k: sum(x == "correct" for x in s.values()) / n for k, s in st.items()},
                                "harm_rate": {arm: (hm[arm][0] + hm[arm][1]) / n for arm in ARMS}, "harm_rate_A": 0.0,
                                "c2w": {arm: hm[arm][0] for arm in ARMS}, "b2w": {arm: hm[arm][1] for arm in ARMS},
                                "nonblank": any(draft.get(c["id"]) is not None for c in claims),
                                "er_has_filled": bool(sel.get("er_has_filled")), "en_shortfall": bool(sel.get("en_shortfall")),
                                "domain": "company" if sid.startswith("cc") else "football",
                                "extra_correct_ER": sum(1 for c in claims if st["ER"][c["id"]] == "correct" and st["A"][c["id"]] != "correct")}
            overlap.append(sel.get("overlap_all_lines", 0) / max(1, len(metas["ER"].get("target_ids") or [1])))
            blank = {c["id"] for c in claims if draft.get(c["id"]) is None}
            for arm in ("ER", "EN"):
                for cid in metas[arm].get("target_ids") or []:
                    if cid in blank:
                        continue
                    if st["A"][cid] != "correct" and st[arm][cid] == "correct":
                        filled_only[arm]["fixed"] += 1
                    if st["A"][cid] == "correct" and st[arm][cid] != "correct":
                        filled_only[arm]["harmed"] += 1
            if sid.startswith("cc"):
                for cid in metas["ER"].get("target_ids") or []:
                    if cid not in blank:
                        company_er_sent_filled["sent"] += 1; company_er_sent_filled["orig_correct"] += st["A"][cid] == "correct"
            for arm in ARMS:
                m = metas[arm]
                if m.get("called"):
                    cost[arm]["usd"] += m.get("cost_usd", 0); cost[arm]["in"] += m.get("input_tokens", 0); cost[arm]["out"] += m.get("output_tokens", 0)
                    cost[arm]["calls"] += 1; cost[arm]["truncated"] += bool(m.get("truncated"))
                    cost[arm]["whole_truncated_eq_draft"] += bool(m.get("truncated") and not m.get("replaced_ids"))
                for c in claims:
                    v = M.canon_strict(vals[arm].get(c["id"]))
                    if v is not None and v != M.canon_strict(tr[0][c["id"]]) and any(v == M.canon_strict(t[c["id"]]) for t in tr[1:]):
                        fut[arm] += 1
                    if st[arm][c["id"]] == "correct" and st["A"][c["id"]] != "correct":
                        shas = set((m.get("page_shas") or {}).values())
                        files = [f for f in (c0 / "site_frozen").glob("*") if f.is_file() and hashlib.sha256(f.read_bytes()).hexdigest() in shas] if shas else []
                        if not files:   # 第二版的 meta 只有 pages_given（網址）；用 B25 的頁面集合 → 凍結檔（對 sha）
                            pinned = json.loads((c0 / "site_snapshot_sha256.json").read_text())
                            names = {u.rsplit("/", 1)[-1] for u in (m.get("pages_given") or [])}
                            files = [c0 / "site_frozen" / nm for nm in pinned if nm in names]
                        inpage[(arm, any(S.plain_contains(f.read_text(errors="replace"), vals[arm].get(c["id"]) or "") for f in files))] += 1
    def comp(t, c, keep, key="prop"):
        d = collections.defaultdict(list)
        for (sid, rep), r_ in rows.items():
            if keep((sid, rep), r_):
                if key == "prop":
                    d[sid].append(r_["prop"][t] - r_["prop"][c])
                else:
                    d[sid].append(r_["harm_rate"][t] - (r_["harm_rate"][c] if c != "A" else 0.0))
        res = A.summarize(dict(d), DELTA if key == "prop" else None); res["drop_top2_sets"] = A.drop_top(dict(d), DELTA, "set"); return res
    allk = lambda k_, r_: True
    erf = lambda k_, r_: r_["er_has_filled"]
    main_ = {"ER_vs_A": comp("ER", "A", allk), "ER_vs_EN": comp("ER", "EN", erf), "ER_vs_EB": comp("ER", "EB", allk)}
    h = A.holm({k_: v.get("perm_p") for k_, v in main_.items()})
    nb = {"ER_vs_A": comp("ER", "A", lambda k_, r_: r_["nonblank"]), "ER_vs_EN": comp("ER", "EN", lambda k_, r_: r_["nonblank"] and erf(k_, r_)),
          "ER_vs_EB": comp("ER", "EB", lambda k_, r_: r_["nonblank"])}
    harm = {arm: comp(arm, "A", allk, key="harm") for arm in ARMS}
    strata = {dom: {k_: comp(*k_.split("_vs_"), (lambda k2, r2, dom=dom, k_=k_: r2["domain"] == dom and (erf(k2, r2) if k_ == "ER_vs_EN" else True)))
                    for k_ in main_} for dom in ("company", "football")}
    no_b27 = {k_: comp(*k_.split("_vs_"), (lambda k2, r2, k_=k_: k2 not in b27 and (erf(k2, r2) if k_ == "ER_vs_EN" else True))) for k_ in main_}
    no_short = comp("ER", "EN", lambda k_, r_: erf(k_, r_) and not r_["en_shortfall"])
    eb_blank = comp("EB", "A", lambda k_, r_: not r_["nonblank"])
    capped = sum(1 for e in excluded if "budget_cap" in e["why"])
    ver = {}
    for k_, v in main_.items():
        if v.get("diff") is None:
            ver[k_] = "no_data"; continue
        better = v["diff"] >= DELTA and v["ci95"] and v["ci95"][0] > 0 and h.get(k_) is not None and h[k_] < 0.05
        ver[k_] = ("pass" if k_ == "ER_vs_A" else "ER_better") if better else ("equivalent_within_5pp" if v.get("equivalent_within_delta") else "no_difference_measured")
        if better:
            ver[k_ + "_stratum_B5"] = A.strat_verdict(v, nb[k_], DELTA)
            if not v["drop_top2_sets"].get("ci95") or v["drop_top2_sets"]["ci95"][0] <= 0:
                ver[k_ + "_few_sets"] = "driven_by_few_sets"
    if ver.get("ER_vs_A") == "pass" and harm["ER"].get("ci95") and harm["ER"]["ci95"][0] > 0:
        ver["ER_vs_A_harm"] = "trading_errors_for_fills"
    if total and capped / total > 0.10:
        ver["family"] = "undetermined_budget_cap"
    hp = collections.defaultdict(list); hp_cost = collections.Counter(); hp_fut = 0
    for r in a.drafts[:1]:
        root = pathlib.Path(r); plan = json.loads((root / "RUN.json").read_text())["plan_body"]; truth = M.load_manifests_with_truth(plan)
        for d in sorted(root.glob("escalation_hp/*/hp*")):
            m = json.loads((d / "meta.json").read_text()) if (d / "meta.json").is_file() else {}
            if not m.get("called") or m.get("infra_void") or not (d / "report.md").is_file():
                continue
            sid = d.parts[-2]; claims = truth[sid]["claims"]; tr = truth[sid]["truth"]
            v = M.SD.parse_report((d / "report.md").read_text(errors="replace"), claims); s = st_of(v, claims, tr)
            hp[sid].append(sum(x == "correct" for x in s.values()) / len(claims)); hp_cost["usd"] += m.get("cost_usd", 0); hp_cost["calls"] += 1
            for c in claims:
                vv = M.canon_strict(v.get(c["id"]))
                if vv is not None and vv != M.canon_strict(tr[0][c["id"]]) and any(vv == M.canon_strict(t[c["id"]]) for t in tr[1:]):
                    hp_fut += 1
    extra = sum(r_["extra_correct_ER"] for r_ in rows.values())
    out = {"drafts_total": total, "drafts_used": len(rows), "excluded": excluded, "budget_capped": capped,
           "main": main_, "holm_family2": h, "verdict": ver, "nonblank_B5": nb, "harm_vs_A": harm, "strata_B35": strata,
           "exclude_b27": no_b27, "ER_vs_EN_exclude_shortfall": no_short, "EB_on_blank_drafts": eb_blank,
           "filled_only_fix_harm_C6": {k_: dict(v) for k_, v in filled_only.items()},
           "company_ER_sent_filled_orig_correct": dict(company_er_sent_filled),
           "cost": {k_: dict(v) for k_, v in cost.items()}, "usd_per_extra_correct_line_ER": round(cost["ER"]["usd"] / extra, 5) if extra else None,
           "future_revision_match_lines": dict(fut), "corrected_value_in_given_pages": {f"{k_[0]}|{k_[1]}": v for k_, v in inpage.items()},
           "ER_EN_overlap_all_lines_mean": round(sum(overlap) / len(overlap), 4) if overlap else None,
           "HP": {"sets": len(hp), "mean_correct_prop": round(sum(sum(v) / len(v) for v in hp.values()) / len(hp), 4) if hp else None,
                  "cost": dict(hp_cost), "future_revision_match_lines": hp_fut,
                  "note": "整份交給 Haiku、而且把全部頁面直接給它時的參考；沒有找頁成本；不進 Holm；不是 Haiku agent 對 9B agent（C10）"}}
    pathlib.Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    print(json.dumps({k_: out[k_] for k_ in ("drafts_used", "budget_capped", "verdict", "holm_family2")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
