#!/usr/bin/env python3
"""實驗 T 確認批次的固定分析（預註冊 `decisions/prereg/PREREG_20261128_EXPT_CONFIRM.md` 的主文＋附錄 A）。
2026-11-28 在任何確認批次的結果被看之前寫好、提交；sha256 記在預註冊附錄。

輸入：兩台的初稿 root（第一部分）與兩台的回饋 root（第二部分）。計畫 sha 必須各自相同。
做的事：
  1. 回饋四臂：用 `expT_metrics.score_cell` 逐格評分（和探索批次同一份嚴格評分），`paired_comparison`（組平均、以組為群集的 bootstrap，
     2,000 次，種子 20261127）算 T−TB、T−G（主要）與 TB−G、G−A（描述）；另報 T−A、TB−A。
  2. 選擇器：`expT_metrics.collect_offline_drafts`（同一份紀錄分數），四種挑法（record／nonblank／random 期望值／oracle）。
  3. p 值：以組為單位的符號翻轉置換檢定（每組的差取組平均，10,000 次，種子 20261130，雙尾）。四個主要比較做 Holm 校正。
     「過」＝效果量門檻、區間下界 >0、Holm 校正後 p<0.05 同時成立（T−G 另要 T 的傷害不多於 G）。
  4. 非空白初稿分層（初稿已填行數 ≥1 的對；選擇器只留非空白初稿、<2 份的組排除）。全樣本過但分層不過 ⇒ 判定字串標
     `effect_from_blank_drafts`。
  5. 拿掉貢獻最大的 2 個單位（回饋：對；選擇器：組）後的差與區間，每個比較都算（過關的才在結論引用）。
  6. 評分補欄：最終值和後續修訂（cycle≥1）的真值相符、但和 revision 0 不符的行數。
  7. 無法區分條件、空白初稿份數（分台、分組）。
越界掃描另跑 `ops/d2/expT_escape.py`（四個 root 各跑一次），這支讀它的 summary 做「排除越界的對」版本。
用法：
  expTc_confirm_analysis.py --drafts R1 R2 --fb F1 F2 [--escape-json E1 E2 ...] --out OUT.json [--md OUT.md]
"""
from __future__ import annotations
import argparse, json, pathlib, random, statistics, sys
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from ops.d2 import expT_metrics as M  # noqa: E402

SD = M.SD
PRIMARY = [("T", "TB", 0.05), ("T", "G", 0.10)]
DESCRIPTIVE = [("TB", "G"), ("G", "A"), ("T", "A"), ("TB", "A")]


def load_plan(root: pathlib.Path) -> tuple[dict, str]:
    run = json.loads((root / "RUN.json").read_text())
    return run["plan_body"], run.get("plan_sha256")


def perm_p(vals: list[float], n: int = 10000, seed: int = 20261130) -> float | None:
    if not vals:
        return None
    rng = random.Random(seed); obs = abs(sum(vals) / len(vals)); hit = 0
    for _ in range(n):
        s = sum(v if rng.random() < 0.5 else -v for v in vals) / len(vals)
        if abs(s) >= obs - 1e-12:
            hit += 1
    return (hit + 1) / (n + 1)


def holm(ps: dict[str, float | None]) -> dict[str, float | None]:
    items = sorted(((p, k) for k, p in ps.items() if p is not None))
    m = len(items); out: dict[str, float | None] = {k: None for k in ps}; run = 0.0
    for i, (p, k) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p)); out[k] = round(run, 5)
    return out


def score_fb(roots: list[pathlib.Path]):
    plan, sha = load_plan(roots[0])
    for r in roots[1:]:
        assert load_plan(r)[1] == sha, "fb roots have different plan sha"
    truth = M.load_manifests_with_truth(plan); reps = int(plan.get("reps") or 2); arms = list(plan["arms"])
    by_key, host_of, c0_filled, future = {}, {}, {}, {}
    for root in roots:
        for sid in truth:
            for rep in range(1, reps + 1):
                rd = root / "cells" / sid / f"r{rep}"
                if not (rd / "c0" / "report.md").is_file():
                    continue
                c0 = (rd / "c0" / "report.md").read_text(errors="replace")
                claims = truth[sid]["claims"]; tr = truth[sid]["truth"]
                c0_filled[(sid, rep)] = sum(1 for c in claims if SD.parse_report(c0, claims).get(c["id"]) is not None)
                for arm in arms:
                    cp = rd / arm / "cell.json"
                    if not cp.is_file():
                        continue
                    cd = json.loads(cp.read_text())
                    host_of[(sid, rep)] = cd.get("provider")
                    if cd.get("infra_void"):
                        by_key[(sid, rep, arm)] = {"set": sid, "rep": rep, "arm": arm, "infra_void": True}; continue
                    fin = (rd / arm / "report.md").read_text(errors="replace")
                    by_key[(sid, rep, arm)] = M.score_cell(cd, c0, fin, truth[sid], chain_path=None, verify_chain=False)
                    vals = SD.parse_report(fin, claims); fut = 0
                    for c in claims:
                        cv = M.canon_strict(vals.get(c["id"]))
                        if cv is None or cv == M.canon_strict(tr[0][c["id"]]):
                            continue
                        if any(cv == M.canon_strict(tr[j][c["id"]]) for j in range(1, len(tr))):
                            fut += 1
                    future[(sid, rep, arm)] = fut
    return plan, sha, truth, reps, arms, by_key, host_of, c0_filled, future


def pair_diffs(by_key, sets, reps, t, c, keep=None):
    """每對的 (a) 差（correct_prop_after），回傳 {(sid,rep): diff}。"""
    out = {}
    for sid in sets:
        for rep in range(1, reps + 1):
            if keep is not None and (sid, rep) not in keep:
                continue
            a, b = by_key.get((sid, rep, t)), by_key.get((sid, rep, c))
            if not a or not b or a.get("infra_void") or b.get("infra_void"):
                continue
            out[(sid, rep)] = a["correct_prop_after"] - b["correct_prop_after"]
    return out


def per_set(d: dict) -> list[float]:
    g: dict = {}
    for (sid, _rep), v in d.items():
        g.setdefault(sid, []).append(v)
    return [sum(v) / len(v) for _, v in sorted(g.items())]


def drop_top2(d: dict) -> dict:
    top = sorted(d.items(), key=lambda kv: kv[1], reverse=True)[:2]
    rest = {k: v for k, v in d.items() if k not in dict(top)}
    ps = per_set(rest)
    return {"dropped": [list(k) if isinstance(k, tuple) else k for k, _ in top],
            "diff": round(sum(ps) / len(ps), 4) if ps else None, "ci95": M._cluster_boot_ci(ps, seed=20261127)}


def fb_block(by_key, sets, reps, keep=None, label="all"):
    res = {}
    for t, c in [(t, c) for t, c, _ in PRIMARY] + DESCRIPTIVE:
        bk = by_key if keep is None else {k: v for k, v in by_key.items() if (k[0], k[1]) in keep}
        pc = M.paired_comparison(bk, sets, reps, treatment=t, control=c)
        d = pair_diffs(by_key, sets, reps, t, c, keep)
        ps = per_set(d)
        res[f"{t}_vs_{c}"] = {
            "pairs": pc["paired_cells"], "sets": pc["paired_sets"],
            "diff": pc["per_set_correct_prop_diff"], "ci95": pc["per_set_correct_prop_diff_ci95"],
            "fprec_diff": pc.get("per_set_filled_precision_diff"), "fprec_ci95": pc.get("per_set_filled_precision_diff_ci95"),
            "harm_total_rate_diff": pc.get("per_set_harm_total_rate_diff"), "harm_total_rate_ci95": pc.get("per_set_harm_total_rate_diff_ci95"),
            "harm_counts": {"t_c2w_or_d": pc.get("treatment_harm_c2w_or_d"), "c_c2w_or_d": pc.get("control_harm_c2w_or_d"),
                            "t_b2w": pc.get("treatment_harm_b2w"), "c_b2w": pc.get("control_harm_b2w")},
            "perm_p": perm_p(ps), "drop_top2": drop_top2(d)}
    res["_label"] = label
    return res


def selector(draft_roots: list[pathlib.Path], nonblank_only: bool):
    plan, sha = load_plan(draft_roots[0])
    for r in draft_roots[1:]:
        assert load_plan(r)[1] == sha, "draft roots have different plan sha"
    truth = M.load_manifests_with_truth(plan); K = int(plan.get("reps") or 5)
    drafts: dict = {}
    for root in draft_roots:
        for sid, ds in M.collect_offline_drafts(root, truth, list(truth), K).items():
            drafts.setdefault(sid, []).extend(ds)
    rows, incomplete = [], []
    for sid in sorted(drafts):
        ds = sorted(drafts[sid], key=lambda d: d["rep"])
        if len(ds) < K:
            incomplete.append(sid)
            if not nonblank_only:
                continue
        claims = truth[sid]["claims"]; tr = truth[sid]["truth"]
        for d in ds:
            root = next(r for r in draft_roots if (r / "cells" / sid / f"r{d['rep']}" / "c0" / "report.md").is_file())
            vals = SD.parse_report((root / "cells" / sid / f"r{d['rep']}" / "c0" / "report.md").read_text(errors="replace"), claims)
            filled = [c for c in claims if vals.get(c["id"]) is not None]
            d["filled"] = len(filled)
            d["filled_correct"] = sum(1 for c in filled if M.strict_status(vals.get(c["id"]), c["id"], tr, 0) == "correct")
        if nonblank_only:
            ds = [d for d in ds if d["filled"] >= 1]
            if len(ds) < 2:
                continue
        rec = max(ds, key=lambda d: (int(d["evidence_score"]), -int(d["blank_count"])))
        nb = max(ds, key=lambda d: int(d["n_claims"]) - int(d["blank_count"]))
        ora = max(ds, key=lambda d: float(d["correct_prop"]))
        rnd = sum(float(d["correct_prop"]) for d in ds) / len(ds)
        fp = lambda d: (d["filled_correct"] / d["filled"]) if d["filled"] else None
        rows.append({"set": sid, "k": len(ds), "blank_drafts": sum(1 for d in ds if d["filled"] == 0),
                     "record_rep": rec["rep"], "nonblank_rep": nb["rep"], "oracle_rep": ora["rep"],
                     "record": rec["correct_prop"], "nonblank": nb["correct_prop"], "random": rnd, "oracle": ora["correct_prop"],
                     "record_fprec": fp(rec), "nonblank_fprec": fp(nb), "oracle_fprec": fp(ora)})
    def cmp(a, b, thr, seed):
        d = {r["set"]: r[a] - (r[b] if isinstance(b, str) else 0) for r in rows}
        vals = [d[k] for k in sorted(d)]
        top = sorted(d.items(), key=lambda kv: kv[1], reverse=True)[:2]
        rest = [v for k, v in d.items() if k not in dict(top)]
        return {"sets": len(vals), "diff": round(sum(vals) / len(vals), 4) if vals else None,
                "ci95": M._cluster_boot_ci(vals, seed=seed), "perm_p": perm_p(vals), "threshold": thr,
                "drop_top2": {"dropped": [k for k, _ in top], "diff": round(sum(rest) / len(rest), 4) if rest else None,
                              "ci95": M._cluster_boot_ci(rest, seed=seed)}}
    n = len(rows); mean = lambda k: round(sum(r[k] for r in rows) / n, 4) if n else None
    return {"K": K, "sets": n, "incomplete_sets": incomplete, "nonblank_only": nonblank_only,
            "means": {k: mean(k) for k in ("record", "nonblank", "random", "oracle")},
            "record_vs_random": cmp("record", "random", 0.05, 20261128),
            "record_vs_nonblank": cmp("record", "nonblank", 0.03, 20261129),
            "record_vs_oracle": cmp("record", "oracle", None, 20261131),
            "same_pick_record_nonblank": sum(1 for r in rows if r["record_rep"] == r["nonblank_rep"]),
            "per_set": rows}


def verdict(comp: dict, thr: float, holm_p: float | None, extra_ok: bool = True) -> str:
    if comp.get("diff") is None:
        return "no_data"
    ok = comp["diff"] >= thr and comp["ci95"] and comp["ci95"][0] > 0 and extra_ok
    if ok and holm_p is not None and holm_p < 0.05:
        return "pass"
    if ok:
        return "pass_uncorrected_only"
    return "no_evidence"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drafts", nargs="+", required=True); ap.add_argument("--fb", nargs="+", required=True)
    ap.add_argument("--escape-json", nargs="*", default=[]); ap.add_argument("--out", required=True); ap.add_argument("--md")
    a = ap.parse_args()
    droots = [pathlib.Path(x) for x in a.drafts]; froots = [pathlib.Path(x) for x in a.fb]
    plan, sha, truth, reps, arms, by_key, host_of, c0_filled, future = score_fb(froots)
    sets = list(truth)
    nonblank_pairs = {k for k, v in c0_filled.items() if v >= 1}
    blank_pairs = sorted(k for k, v in c0_filled.items() if v == 0)
    esc_pairs: set = set()
    for e in a.escape_json:
        j = json.loads(pathlib.Path(e).read_text())
        esc_pairs |= {tuple(x) for x in j.get("excluded_pairs_a", [])}
    all_pairs = set(c0_filled)
    fb_all = fb_block(by_key, sets, reps, None, "all")
    fb_nonblank = fb_block(by_key, sets, reps, nonblank_pairs, "nonblank_drafts")
    fb_noesc = fb_block(by_key, sets, reps, all_pairs - esc_pairs, "exclude_escape_pairs") if esc_pairs else None
    sel_all = selector(droots, False); sel_nb = selector(droots, True)
    # Holm over the four primary comparisons (full sample; same correction applied within each stratum)
    def holm_for(fb, sel):
        ps = {"T_vs_TB": fb["T_vs_TB"]["perm_p"], "T_vs_G": fb["T_vs_G"]["perm_p"],
              "record_vs_random": sel["record_vs_random"]["perm_p"], "record_vs_nonblank": sel["record_vs_nonblank"]["perm_p"]}
        return ps, holm(ps)
    raw_all, h_all = holm_for(fb_all, sel_all); raw_nb, h_nb = holm_for(fb_nonblank, sel_nb)
    def harm_ok(fb):
        hc = fb["T_vs_G"]["harm_counts"]
        try:
            return (hc["t_c2w_or_d"] + hc["t_b2w"]) <= (hc["c_c2w_or_d"] + hc["c_b2w"])
        except TypeError:
            return False
    def verdicts(fb, sel, h):
        return {"T_vs_TB": verdict(fb["T_vs_TB"], 0.05, h["T_vs_TB"]),
                "T_vs_G": verdict(fb["T_vs_G"], 0.10, h["T_vs_G"], harm_ok(fb)),
                "record_vs_random": verdict(sel["record_vs_random"], 0.05, h["record_vs_random"]),
                "record_vs_nonblank": verdict(sel["record_vs_nonblank"], 0.03, h["record_vs_nonblank"])}
    v_all = verdicts(fb_all, sel_all, h_all); v_nb = verdicts(fb_nonblank, sel_nb, h_nb)
    final = {}
    for k in v_all:
        final[k] = ("effect_from_blank_drafts" if v_all[k] == "pass" and v_nb[k] != "pass" else v_all[k])
    # indistinguishable
    a_cells = [v for k, v in by_key.items() if k[2] == "A" and not v.get("infra_void")]
    t_cells = [v for k, v in by_key.items() if k[2] == "T" and not v.get("infra_void")]
    a_prop = statistics.mean(c["correct_prop_after"] for c in a_cells) if a_cells else None
    t_sent = sum(1 for c in t_cells if (c.get("feedback_sent_count") or 0) > 0)
    indist = (a_prop is not None and (a_prop > 0.85 or a_prop < 0.10)) or (t_cells and t_sent < len(t_cells) / 4)
    per_arm = {}
    for arm in arms:
        cs = [v for k, v in by_key.items() if k[2] == arm and not v.get("infra_void")]
        if cs:
            per_arm[arm] = {"cells": len(cs), "correct_prop_mean": round(statistics.mean(c["correct_prop_after"] for c in cs), 4),
                            "harm_c2w_or_d": sum(c["harm_c2w_or_d"] for c in cs), "harm_b2w": sum(c["harm_b2w"] for c in cs),
                            "future_truth_match_lines": sum(future.get(k, 0) for k in by_key if k[2] == arm)}
    blank_by_host: dict = {}
    for k in blank_pairs:
        blank_by_host[host_of.get(k)] = blank_by_host.get(host_of.get(k), 0) + 1
    out = {"schema": "vacant.d2.expTc.confirm/1", "fb_plan_sha256": sha, "pairs": len(all_pairs),
           "blank_draft_pairs": [list(k) for k in blank_pairs], "blank_draft_pairs_by_host": blank_by_host,
           "indistinguishable": bool(indist), "A_correct_prop": a_prop, "T_feedback_cells": [t_sent, len(t_cells)],
           "per_arm": per_arm, "feedback": {"all": fb_all, "nonblank_drafts": fb_nonblank, "exclude_escape_pairs": fb_noesc},
           "selector": {"all": sel_all, "nonblank_drafts": sel_nb},
           "perm_p_raw": {"all": raw_all, "nonblank": raw_nb}, "holm": {"all": h_all, "nonblank": h_nb},
           "verdict": {"all": v_all, "nonblank": v_nb, "final": final}}
    pathlib.Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    print(json.dumps({"verdict": out["verdict"], "holm": out["holm"], "indistinguishable": out["indistinguishable"],
                      "blank_draft_pairs": len(blank_pairs)}, ensure_ascii=False))
    if a.md:
        L = [f"# 確認批次固定輸出（fb plan {str(sha)[:12]}）", "", f"對數 {len(all_pairs)}；空白初稿的對 {len(blank_pairs)}（分台 {blank_by_host}）；"
             f"無法區分 {out['indistinguishable']}（A {a_prop:.3f}，T 送出回饋 {t_sent}/{len(t_cells)}）", ""]
        for lab, fb in (("全部", fb_all), ("非空白初稿", fb_nonblank), ("排除越界的對", fb_noesc)):
            if not fb:
                continue
            L.append(f"## 回饋比較：{lab}")
            for k, v in fb.items():
                if k.startswith("_"):
                    continue
                L.append(f"- {k}: {v['diff']} {v['ci95']}（{v['pairs']} 對；perm p={v['perm_p']}；拿掉前 2 對 {v['drop_top2']['diff']} {v['drop_top2']['ci95']}）")
            L.append("")
        for lab, s in (("全部", sel_all), ("非空白初稿", sel_nb)):
            L.append(f"## 選擇器：{lab}（{s['sets']} 組）平均 {s['means']}")
            for k in ("record_vs_random", "record_vs_nonblank", "record_vs_oracle"):
                v = s[k]; L.append(f"- {k}: {v['diff']} {v['ci95']}（perm p={v['perm_p']}；拿掉前 2 組 {v['drop_top2']['diff']} {v['drop_top2']['ci95']}）")
            L.append("")
        L.append(f"## Holm（全部）{h_all}；（非空白）{h_nb}")
        L.append(f"## 判定 全部 {v_all}；非空白 {v_nb}；最終 {final}")
        L.append(f"## 各臂 {per_arm}")
        pathlib.Path(a.md).write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
