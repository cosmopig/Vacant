#!/usr/bin/env python3
"""BCB-Hard 夜間批次的分析——照預註冊 `decisions/prereg/PREREG_20260924_BCB_HARD_VACANT_AB.md` 寫死，
只在全部 worker 收工後跑一次。輸出 `report.json`＋`report.md`（繁體中文）。

⚠ 本檔不改任何格子的資料；infra_void 的判準與預註冊 §五 逐字對應。
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import statistics
import sys
import time

RUN = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/var/tmp/vacant_piext_20260924/bcb_run")
sys.path.insert(0, os.environ.get("VACANT_REPO", "/var/tmp/vacant_piext_20260924/pilot_1004/repo"))
from vacant_network import research  # noqa: E402

STRATA = ("1004", "1003", "gemini")
HTTP_ERR = re.compile(r"\b[45]\d\d status code\b|ECONNREFUSED|fetch failed|ETIMEDOUT", re.I)


def cell(b: str, arm: str, tid: str, att: int) -> dict | None:
    L = RUN / b / "cells" / f"{arm}_{tid}_a{att}"
    if not (L / "rc").exists():
        return None
    rc = int((L / "rc").read_text().strip() or -1)
    try:
        hid = json.loads((L / "hidden.json").read_text())
    except Exception:
        hid = {}
    total = hid.get("total")
    correct = bool(total) and hid.get("passed") == total
    delivered = (L / "delivered_solution.py").exists()
    wire = []
    for f in ("proxyd_slice.jsonl", "gate_wire_index.jsonl"):
        if (L / f).exists():
            wire += [json.loads(x) for x in open(L / f) if x.strip()]
    posts = [r for r in wire if r.get("method") == "POST"]
    ok2xx = sum(1 for r in posts if isinstance(r.get("status"), int) and 200 <= r["status"] < 300)
    err = (L / "stderr").read_text(errors="replace") if (L / "stderr").exists() else ""
    if arm in ("CH", "GATE"):
        infra = (len(posts) > 0 and ok2xx == 0) or (len(posts) == 0 and rc != 0 and bool(HTTP_ERR.search(err)))
    else:
        infra = rc != 0 and not delivered and bool(HTTP_ERR.search(err))
    if arm == "GATE" and rc == 22:
        infra = True
    return {"rc": rc, "correct": correct, "delivered": delivered, "infra": infra,
            "wall_s": float((L / "wall_s").read_text()), "posts": len(posts), "posts_2xx": ok2xx,
            "n429": sum(1 for r in posts if r.get("status") == 429) + len(re.findall(r"\b429\b", err)),
            "visible_pass": (L / "visible.rc").exists() and (L / "visible.rc").read_text().strip() == "0",
            "hidden": f"{hid.get('passed')}/{total}"}


def task_outcomes(b: str, tid: str) -> dict:
    off, ch, g1 = cell(b, "OFF", tid, 1), cell(b, "CH", tid, 1), cell(b, "GATE", tid, 1)
    g_atts = [c for c in (cell(b, "GATE", tid, a) for a in (1, 2, 3)) if c is not None]
    o: dict = {"task": tid, "backend": b, "cells": {"OFF": off, "CH": ch, "GATE": g1,
                                                     "GATE_redraws": g_atts[1:]}}
    for name, c in (("OFF", off), ("CH", ch)):
        o[name] = None if (c is None or c["infra"]) else {
            "released": c["rc"] == 0, "false_release": c["rc"] == 0 and not c["correct"],
            "correct_delivery": c["rc"] == 0 and c["correct"]}
    o["GATE"] = None if (g1 is None or g1["infra"]) else {
        "released": g1["rc"] == 0, "false_release": g1["rc"] == 0 and not g1["correct"],
        "correct_delivery": g1["rc"] == 0 and g1["correct"],
        "blocked_correct": g1["rc"] == 20 and g1["correct"], "blocked": g1["rc"] == 20}
    if o["GATE"] is None or any(c["infra"] for c in g_atts):
        o["GATE+R"] = None
    else:
        acc = next((c for c in g_atts if c["rc"] == 0), None)
        o["GATE+R"] = {"released": acc is not None, "false_release": acc is not None and not acc["correct"],
                       "correct_delivery": acc is not None and acc["correct"],
                       "attempts": len(g_atts), "extra_posts": sum(c["posts"] for c in g_atts[1:])}
    return o


def paired(rows, a, b, key):
    """回傳各層 (b_k, c_k)：b＝a 組為真且 b 組為假；c＝反之。任一邊 None（infra／缺格）⇒ 整題排除。"""
    out, excluded = {}, 0
    for s in STRATA:
        bb = cc = 0
        for r in rows:
            if r["backend"] != s:
                continue
            if r[a] is None or r[b] is None:
                excluded += 1
                continue
            x, y = r[a][key], r[b][key]
            bb += int(x and not y)
            cc += int(y and not x)
        out[s] = (bb, cc)
    return out, excluded


def rate(rows, arm, key, s=None):
    xs = [r[arm][key] for r in rows if r[arm] is not None and (s is None or r["backend"] == s)]
    return (sum(xs), len(xs))


def main():
    rec = json.loads((RUN / "launch_record.json").read_text())
    rows = []
    for s in STRATA:
        tdir = RUN / s / "tasks"
        for f in sorted(tdir.glob("*.done")) if tdir.exists() else []:
            rows.append(task_outcomes(s, f.name[: -len(".done")]))
    rep: dict = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "launch_record": rec, "n_tasks_done": len(rows),
                 "per_stratum_n": {s: sum(1 for r in rows if r["backend"] == s) for s in STRATA}}
    # H1：假完成放行 OFF vs GATE（b＝OFF 放行而 GATE 沒放行）
    st, ex = paired(rows, "OFF", "GATE", "false_release")
    h1 = research.stratified_mcnemar_exact([st[s] for s in STRATA])
    rep["H1_false_release_OFF_vs_GATE"] = {"strata": {s: st[s] for s in STRATA}, "excluded_tasks": ex, **h1,
                                           "heterogeneity": research.bc_heterogeneity_chisq([st[s] for s in STRATA]),
                                           "direction_as_predicted": h1["b"] > h1["c"],
                                           "significant_at_0.05": h1["p"] < 0.05}
    # H2：正確交付 GATE+R vs OFF（b＝GATE+R 對而 OFF 沒對）
    st2, ex2 = paired(rows, "GATE+R", "OFF", "correct_delivery")
    h2 = research.stratified_mcnemar_exact([st2[s] for s in STRATA])
    rep["H2_correct_delivery_GATER_vs_OFF"] = {"strata": {s: st2[s] for s in STRATA}, "excluded_tasks": ex2, **h2,
                                               "direction_as_predicted": h2["b"] > h2["c"],
                                               "significant_at_0.025": h2["p"] < 0.025}
    # H3：CH − OFF 正確交付的配對差（TOST，δ=0.10，α=0.025）
    diffs = [int(r["CH"]["correct_delivery"]) - int(r["OFF"]["correct_delivery"])
             for r in rows if r["CH"] is not None and r["OFF"] is not None]
    rep["H3_no_harm_CH_vs_OFF"] = ({"n": len(diffs), **research.tost_equiv_boot(diffs, 0.10, alpha=0.025)}
                                   if diffs else {"n": 0, "note": "沒有可配對的題"})
    # 描述性
    desc = {}
    for s in (None,) + STRATA:
        k = s or "all"
        d = {}
        for arm in ("OFF", "CH", "GATE", "GATE+R"):
            d[arm] = {m: rate(rows, arm, m, s) for m in ("released", "false_release", "correct_delivery")}
        d["GATE"]["blocked"] = rate(rows, "GATE", "blocked", s)
        d["GATE"]["blocked_correct"] = rate(rows, "GATE", "blocked_correct", s)
        walls = {arm: [r["cells"][arm]["wall_s"] for r in rows if r["cells"][arm] and (s is None or r["backend"] == s)]
                 for arm in ("OFF", "CH", "GATE")}
        d["wall_s_median"] = {a: (statistics.median(v) if v else None) for a, v in walls.items()}
        d["redraws"] = sum(len(r["cells"]["GATE_redraws"]) for r in rows if s is None or r["backend"] == s)
        d["infra_void_cells"] = sum(1 for r in rows if s is None or r["backend"] == s
                                    for c in [r["cells"]["OFF"], r["cells"]["CH"], r["cells"]["GATE"], *r["cells"]["GATE_redraws"]]
                                    if c and c["infra"])
        d["n429"] = sum(c["n429"] for r in rows if s is None or r["backend"] == s
                        for c in [r["cells"]["OFF"], r["cells"]["CH"], r["cells"]["GATE"], *r["cells"]["GATE_redraws"]] if c)
        desc[k] = d
    rep["descriptive"] = desc
    rep["rows"] = rows
    (RUN / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))

    def pct(t):
        return f"{t[0]}/{t[1]}（{(100 * t[0] / t[1]):.0f}%）" if t[1] else "—"
    L = [f"# BCB-Hard × pi × 有／沒有 Vacant：夜間批次報告", "",
         f"- 預註冊：`{rec['prereg']}`（sha256 `{rec['prereg_sha256'][:12]}…`）；發射 {rec['launched_utc']}",
         f"- 完成題數：{len(rows)}（" + "、".join(f"{s} {rep['per_stratum_n'][s]}" for s in STRATA) + "）", "",
         "## 主要（H1）：假完成放行率 GATE < OFF", ""]
    h = rep["H1_false_release_OFF_vs_GATE"]
    L += [f"- 不一致對：OFF 放行而 GATE 沒放行 b＝{h['b']}，反之 c＝{h['c']}；分層精確 p＝{h['p']:.4g}"
          f"（{'成立' if h['significant_at_0.05'] and h['direction_as_predicted'] else '不成立'}，α＝0.05）",
          "- 各層 (b, c, p)：" + "；".join(f"{s} ({x['b']}, {x['c']}, {x['p']:.3g})" for s, x in zip(STRATA, h["per_stratum"])),
          f"- 排除（infra／缺格）：{h['excluded_tasks']} 題；異質性（描述性）χ²＝{h['heterogeneity'].get('chi2')}", ""]
    h = rep["H2_correct_delivery_GATER_vs_OFF"]
    L += ["## 次要（H2）：正確交付率 GATE+R > OFF（α＝0.025）", "",
          f"- b＝{h['b']}、c＝{h['c']}；p＝{h['p']:.4g}（{'成立' if h['significant_at_0.025'] and h['direction_as_predicted'] else '不成立'}）", ""]
    h = rep["H3_no_harm_CH_vs_OFF"]
    L += ["## 次要（H3）：只裝 Vacant 不會變差（CH − OFF，TOST δ＝0.10，α＝0.025）", "",
          (f"- n＝{h['n']}，平均差 {h['mean']:+.3f}，95% CI [{h['ci_lo']:+.3f}, {h['ci_hi']:+.3f}] ⇒ "
           f"{'等效成立' if h['equivalent'] else '等效不成立'}" if h.get("n") else "- 沒有可配對的題"), "",
          "## 描述性（每組）", "",
          "| 層 | 組 | 交出去 | 假完成放行 | 正確交付 |", "|---|---|---|---|---|"]
    for k in ("all",) + STRATA:
        for arm in ("OFF", "CH", "GATE", "GATE+R"):
            d = desc[k][arm]
            L.append(f"| {k} | {arm} | {pct(d['released'])} | {pct(d['false_release'])} | {pct(d['correct_delivery'])} |")
    L += ["", "| 層 | GATE 擋下 | 其中擋錯（其實是對的） | 重抽次數 | infra_void 格 | 429 次數 | 牆鐘中位數 OFF/CH/GATE（秒） |",
          "|---|---|---|---|---|---|---|"]
    for k in ("all",) + STRATA:
        d = desc[k]
        w = d["wall_s_median"]
        L.append(f"| {k} | {pct(d['GATE']['blocked'])} | {pct(d['GATE']['blocked_correct'])} | {d['redraws']} | "
                 f"{d['infra_void_cells']} | {d['n429']} | {w['OFF']}/{w['CH']}/{w['GATE']} |")
    L += ["", "## 口徑（預註冊 §八）", "",
          "- 閘門不改 agent 的產出，只改交不交；H1 成立只能說「假完成被放行的比率下降」，不能說「agent 變準」。",
          "- GATE+R 的提升是閘門＋重抽，成本（重抽次數、額外呼叫）一起看。",
          "- 可見測試是單邊的：GATE 的「假完成放行」就是可見過、隱藏沒過的那一塊（V/GT 缺口）。",
          "- 三層推論條件不同（1004 不思考／1003 思考／Gemini 26B 思考），各層分開讀。",
          "- 本檔沒有人類逐字簽核的預註冊（授權是口頭的「幫我排程」），照實記。"]
    (RUN / "report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
