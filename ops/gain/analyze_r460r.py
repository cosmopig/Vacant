#!/usr/bin/env python3
"""R460R 彙總分析：五次複製各自判一次，再把五次**描述性**地列在一起。

規格：`DECISION_20260911_R460R_FIVE_REPLICATIONS_PREREG.md`（Fable R2／R6）。
這支在架構裡承重什麼：**它是「複製」這件事唯一的仲裁者**，而複製最容易被
偷偷變成「把五次的 n 加起來」。本檔用三道機制擋那件事：

1. **每一次複製各自走 `analyze_r460.analyze()` 一次**，用的是 R460 §六 那套
   **一個字沒改**的四狀態規則（Holm 家族仍然是該次複製自己的 6 個檢定）。
   ⇒ 「複製」的定義逐字是「同一個事前規則，在新資料上再判一次」。
2. **禁止併 n**：本檔**沒有**任何把五次 rows 接起來的路徑（`R449C §六-2`／
   R460 §六-(7)-3 的既有禁令）。彙總欄位全部是「五個數字排在一起」，
   不是「一個合併出來的數字」。`aggregate.pooled_*` 這種鍵**刻意不存在**。
3. **宣稱規則事前寫死**（§二）：`5/5 同號且 ≥4/5 Holm 顯著` ⇒ 可以寫
   「複製穩定」；否則**逐次照實列**，不准挑、不准平均、不准講「多數支持」。
   本檔把判到的那一句逐字印在 `aggregate.statement`，並附
   `aggregate.statement_rule`（規則本身），好讓讀的人看得到規則不是事後配的。
4. **跨複製的逐端點併發對帳**（`global_topology`，round460r-2／§六-11）：
   逐次的拓撲報表只看那一次自己的六塊，而排程器是**跨複製**發射的
   ⇒ r1 的最後一塊與 r2 的第一塊會同時在跑，逐次全綠仍然可能整體超賣。
   本檔把**全部複製的全部塊**丟進同一條掃描線再算一次，超過凍結上限
   ⇒ `endpoint_concurrency_exceeded_global` ⇒ 退出碼 1。

⚠ **檢定力的事前預期（寫在資料之前，§三）**：n=120 對 +10pp 的檢定力只有
  0.43–0.63 ⇒ 就算真值真的是 +10pp，**五次裡預期只有 2–3 次**會通過 P-R3。
  所以「5 次裡 2 次顯著」**不是**反證，「5 次全部顯著」也**不是**加碼的理由。
  這句話印在每一次執行的 `power_expectation`，不印就不准結算。

⚠ **winner's curse**：R460 的 +13.33pp 是能被判顯著的點估計 ⇒ 上偏。
  複製跑的點估計**預期會比它小**，這不是「效果消失」。同樣逐次印出來。

用法：
    python3 ops/gain/analyze_r460r.py --reps 1 2 3 4 5 --bank lcb2 --rescore-turn1
    python3 ops/gain/analyze_r460r.py --selftest      # 拿 R460 六塊對釘已知答案
零模型呼叫；`--rescore-turn1` 會跑沙箱（與 R460 收官同一條路徑）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.gain.analyze_r460 import (ALPHA, AUTHORIZED_BLOCKS,  # noqa: E402
                                   CI_DISCLAIMER, DELTA_C_MIN_PP,
                                   ENDPOINT_CONCURRENCY_CAPS,
                                   REPLICATION_BLOCKS, REPLICATION_SEEDS,
                                   analyze, block_window, load_bank_meta,
                                   max_concurrent_by_endpoint, pool_runs)

ROOT = pathlib.Path(__file__).resolve().parents[2]

#: 主要假設（R460 §六-(4) 逐字沿用）：H-MIX vs CONFORM。
PRIMARY = "HMIX"
PRIMARY_PAIR = "HMIX_vs_CONFORM"

#: R460 的錨（`DECISION_20260911_R460_FABLE_AUDIT_HARNESS.md` §二／§三）。
#: 這些數字**只當比較的錨**，不是複製跑的判準；判準是 R460 §六 的四狀態。
R460_ANCHORS = {
    "hmix_deliv_pp": 84.17, "conform_deliv_pp": 70.83,
    "delta_c_pp": 13.33, "holm_p_adj": 0.0112,
    "false_delivery_n_hmix": 14, "false_delivery_n_conform": 29,
    "tokens_per_task_hmix": 5677, "tokens_per_task_conform": 5805,
}

#: 事前註冊的五條逐次預測（§三）。判的都是**那一次複製自己**的欄位。
PREDICTIONS = {
    "P-R1": "Δ_C > 0（paired.HMIX_vs_CONFORM.delta_pp）",
    "P-R2": "Δ_C ≥ +10.0pp（點估計）",
    "P-R3": "Holm p_adj(HMIX vs CONFORM) < 0.05",
    "P-R4": "假交付 HMIX < CONFORM（per_arm.*.false_delivery_pp）",
    "P-R5": "token/題 HMIX ≤ 1.2 × CONFORM（tokens.*.tokens_per_task）",
}

#: 事前寫死的宣稱規則（§二）。改這裡＝改事前註冊 ⇒ 不准。
STATEMENT_RULE = ("5/5 同號（Δ_C > 0）且 ≥4/5 Holm 顯著 ⇒ 可以寫「複製穩定」；"
                  "否則**逐次照實列**，不准挑一次、不准平均、不准寫「多數支持」。")
POWER_EXPECTATION = ("n=120 對 +10pp 的檢定力只有 0.43–0.63 ⇒ 就算真值是 +10pp，"
                     "五次裡**預期只有 2–3 次**通過 P-R3。"
                     "「5 次裡 2 次顯著」不是反證；「5 次全顯著」也不是加碼的理由。")
WINNERS_CURSE = ("R460 的 +13.33pp 是**能被判顯著**的點估計 ⇒ 它是效果量的上偏估計。"
                 "複製跑的點估計預期比它小，那不是「效果消失」。"
                 "跨次比幅度一律看區間重疊，不比點估計誰大。")
NO_POOLING = ("五次複製**不得併 n**（R449C §六-2、R460 §六-(7)-3）。"
              "本檔沒有任何併 n 的路徑；彙總欄位全部是五個數字排在一起。")


#: §六-11（round460r-2）：**跨複製**的逐端點併發對帳。
GLOBAL_CONCURRENCY_NOTE = (
    "逐次的 `topology.max_concurrent_by_endpoint` 只看那一次自己的六塊，"
    "而排程器是**跨複製**發射的（r1 的最後一塊與 r2 的第一塊會同時在跑）"
    "⇒ 逐次全綠仍然可能整體超賣。本欄把**全部複製的全部塊**丟進同一條掃描線"
    "重算一次，上限與逐次那條同一張表（凍結的 `ENDPOINT_CONCURRENCY_CAPS`）。"
    "⚠ 事前的閘門在排程器的槽位，這裡是事後對帳——排程器說了不算。"
    "⚠ 算不出時間窗一律 `block_ts_unrecorded`：算不出不是通過。")


def rep_dirs(k: int, root: pathlib.Path = ROOT) -> list[pathlib.Path]:
    return [root / "runs" / name for name in REPLICATION_BLOCKS[k]]


def global_concurrency(blocks: list[dict]) -> dict:
    """跨全部複製、全部塊的逐端點併發對帳（§六-11）。

    ⚠ 為什麼不能只信逐次那一條：`analyze_rep` 對每一次複製各跑一次
    `topology_report`，而那條掃描線只放得下那一次的六塊。排程器的槽位是
    **跨複製**共用的（r1 最後一塊還在跑時 r2 的第一塊就發出去了）⇒
    「1004 同時三塊」這件事在逐次的帳上永遠看不到第四塊。
    本函式把全部塊放進**同一條**掃描線，所以它量的是那顆卡真正扛過的峰值。
    """
    out: dict = {"blocks_n": len(blocks),
                 "reps_covered": sorted({b["rep"] for b in blocks if "rep" in b}),
                 "caps": dict(ENDPOINT_CONCURRENCY_CAPS),
                 "max_concurrent_by_endpoint": {},
                 "blocks_per_endpoint": {},
                 "window_by_block": {},
                 "peak_witness": {},
                 "violations": [],
                 "note": GLOBAL_CONCURRENCY_NOTE}
    if not blocks:
        return out
    out["max_concurrent_by_endpoint"] = max_concurrent_by_endpoint(blocks)
    by_ep: dict[str, list[str]] = {}
    for b in blocks:
        out["window_by_block"][b["name"]] = block_window(b)
        for ep in (b.get("endpoints") or []):
            by_ep.setdefault(ep, []).append(b["name"])
    out["blocks_per_endpoint"] = {ep: sorted(v) for ep, v in sorted(by_ep.items())}
    for b in blocks:
        if (out["window_by_block"].get(b["name"]) or {}).get("lo_ms") is None:
            out["violations"].append(f"block_ts_unrecorded:{b['name']}")
    for ep in sorted(by_ep):
        cap = ENDPOINT_CONCURRENCY_CAPS.get(ep)
        if cap is None:
            # 沒登記上限 ≠ 沒有上限（與逐次那條同一句話）。
            out["violations"].append(f"endpoint_not_registered:{ep}")
            continue
        got = out["max_concurrent_by_endpoint"].get(ep, 0)
        out["peak_witness"][ep] = _peak_witness(blocks, ep)
        if got > cap:
            out["violations"].append(
                f"endpoint_concurrency_exceeded_global:{ep}:{got}>{cap}")
    return out


def _peak_witness(blocks: list[dict], endpoint: str) -> dict:
    """峰值那一刻是哪幾塊同時在跑——違規要指得出人，不是只報一個數字。"""
    spans = []
    for b in blocks:
        eps = b.get("endpoints") or []
        if len(eps) != 1 or eps[0] != endpoint:
            continue
        ts = [(int(c["ts_ms"]), int(c.get("latency_ms") or 0))
              for c in (b.get("calls") or [])
              if isinstance(c.get("ts_ms"), (int, float))]
        if ts:
            spans.append((min(t for t, _ in ts),
                          max(t + max(d, 0) for t, d in ts), b["name"]))
    best_t, best_names = None, []
    for lo, _hi, _n in spans:
        live = sorted(n for a, b_, n in spans if a <= lo <= b_)
        if len(live) > len(best_names):
            best_t, best_names = lo, live
    return {"at_ms": best_t, "blocks": best_names, "n": len(best_names)}


def analyze_rep(k: int, *, bank: str = "lcb2", rescore_turn1: bool = False,
                root: pathlib.Path = ROOT,
                blocks_out: list[dict] | None = None) -> dict:
    """第 k 次複製的完整收官報表（＝ `analyze_r460` 在那六塊上的輸出）。

    ⚠ 六塊少一塊就不判：`analyze_r460` 自己會把 `block_count_not_6` 與
    `pooled_task_count_not_120` 放進 `broken_reasons`。本檔**不繞過**它。
    `blocks_out` 給 `global_concurrency` 收集跨複製的塊（不影響任何仲裁值）。
    """
    dirs = rep_dirs(k, root)
    missing = [str(d) for d in dirs if not (d / "rows.jsonl").exists()]
    if missing:
        return {"rep": k, "status": "NOT_RUN", "missing": missing,
                "seed_expected": REPLICATION_SEEDS[k]}
    rows, summary, calls, blocks = pool_runs(dirs)
    if blocks_out is not None:
        blocks_out += [dict(b, rep=k) for b in blocks]
    turn1 = None
    if rescore_turn1:
        from ops.gain.gain_run import load_tasks
        tasks: dict[str, dict] = {}
        for b in blocks:
            for t in load_tasks(bank, b["seed"], b["n"], offset=b["offset"]):
                tasks[t["task_id"]] = t
        from ops.gain.analyze_r460 import rescore_turn1 as _rescore
        turn1 = _rescore(rows, calls, tasks)
    out = analyze(rows, summary, calls, bank=load_bank_meta(bank), turn1=turn1,
                  blocks=blocks, topology_mode="scheduled",
                  authorized=REPLICATION_BLOCKS[k], ph0_blocks=None)
    out["rep"] = k
    out["status"] = "ANALYZED"
    out["seed_expected"] = REPLICATION_SEEDS[k]
    seeds = {b["seed"] for b in blocks}
    if seeds != {REPLICATION_SEEDS[k]}:
        out["broken_reasons"].append(
            f"rep_seed_mismatch:{sorted(map(str, seeds))}!={REPLICATION_SEEDS[k]}")
    return out


def rep_row(out: dict) -> dict:
    """一次複製壓縮成彙總表上的一列（**只取事前指名的欄位**）。"""
    if out.get("status") != "ANALYZED":
        return {"rep": out["rep"], "status": out.get("status"),
                "missing": out.get("missing")}
    per, paired, holm = out["per_arm"], out["paired"], out["holm"]
    tokens, decision = out["tokens"], out["decision"]
    pr = paired.get(PRIMARY_PAIR) or {}
    hm = holm.get(PRIMARY_PAIR) or {}
    d_c = pr.get("delta_pp")
    fd_h = (per.get(PRIMARY) or {}).get("false_delivery_pp")
    fd_c = (per.get("CONFORM") or {}).get("false_delivery_pp")
    tk_h = (tokens.get(PRIMARY) or {}).get("tokens_per_task")
    tk_c = (tokens.get("CONFORM") or {}).get("tokens_per_task")
    preds = {
        "P-R1": None if d_c is None else d_c > 0,
        "P-R2": None if d_c is None else d_c >= DELTA_C_MIN_PP,
        "P-R3": None if hm.get("p_adj") is None else hm["p_adj"] < ALPHA,
        "P-R4": None if (fd_h is None or fd_c is None) else fd_h < fd_c,
        "P-R5": None if (tk_h is None or tk_c is None or not tk_c)
        else tk_h <= 1.2 * tk_c,
    }
    return {
        "rep": out["rep"], "status": "ANALYZED",
        "broken_reasons": out["broken_reasons"],
        "verdict": (decision.get(PRIMARY) or {}).get("verdict"),
        "hmix_deliv_pp": (per.get(PRIMARY) or {}).get("deliv_pp_denom_measured"),
        "conform_deliv_pp": (per.get("CONFORM") or {}).get("deliv_pp_denom_measured"),
        "delta_c_pp": d_c,
        "ci95_lo_pp": pr.get("ci95_lo_pp"), "ci95_hi_pp": pr.get("ci95_hi_pp"),
        "b": pr.get("b"), "c": pr.get("c"), "n_common": pr.get("n_common"),
        "p_raw": hm.get("p_raw"), "p_adj": hm.get("p_adj"),
        "holm_significant": hm.get("significant"),
        "false_delivery_pp_hmix": fd_h, "false_delivery_pp_conform": fd_c,
        "false_delivery_n_hmix": (per.get(PRIMARY) or {}).get("false_delivery_n"),
        "false_delivery_n_conform": (per.get("CONFORM") or {}).get("false_delivery_n"),
        "tokens_per_task_hmix": tk_h, "tokens_per_task_conform": tk_c,
        "topology_variant": (out.get("topology") or {}).get("variant"),
        "max_concurrent_by_endpoint":
            (out.get("topology") or {}).get("max_concurrent_by_endpoint"),
        "predictions": preds,
        "ci_note": CI_DISCLAIMER,
    }


def aggregate(rows: list[dict]) -> dict:
    """事前註冊的**描述性**彙總（§二）。沒有一個欄位是把 n 加起來算的。"""
    done = [r for r in rows if r.get("status") == "ANALYZED"]
    verdicts = {v: sum(1 for r in done if r["verdict"] == v)
                for v in ("EFFECTIVE", "COSTLY_BUT_REAL",
                          "INCONCLUSIVE", "RULED_OUT")}
    deltas = [r["delta_c_pp"] for r in done if r["delta_c_pp"] is not None]
    same_sign = bool(deltas) and len(deltas) == len(done) and all(d > 0 for d in deltas)
    n_sig = sum(1 for r in done if r.get("holm_significant"))
    stable = (len(done) == 5 and same_sign and n_sig >= 4)
    if stable:
        statement = ("**複製穩定**：五次複製的 Δ_C 全部同號（> 0），"
                     f"且 {n_sig}/5 在各自的 Holm 家族內顯著。")
    else:
        statement = ("**逐次照實列**（宣稱規則未達成："
                     f"同號 {len(deltas)}/{len(done)}、Holm 顯著 {n_sig}/{len(done)}、"
                     f"已分析 {len(done)}/5）"
                     "——不准挑一次、不准平均、不准寫「多數支持」。")
    return {
        "reps_analyzed": len(done),
        "reps_expected": 5,
        "verdict_counts_HMIX": verdicts,
        "delta_c_pp_by_rep": {r["rep"]: r["delta_c_pp"] for r in done},
        "ci95_by_rep": {r["rep"]: [r["ci95_lo_pp"], r["ci95_hi_pp"]] for r in done},
        "holm_p_adj_by_rep": {r["rep"]: r["p_adj"] for r in done},
        "holm_significant_n": n_sig,
        "all_same_sign_positive": same_sign,
        "statement_rule": STATEMENT_RULE,
        "statement": statement,
        "prediction_hits": {
            k: {"hit": sum(1 for r in done if r["predictions"].get(k) is True),
                "n": len(done)} for k in PREDICTIONS},
        "power_expectation": POWER_EXPECTATION,
        "winners_curse_disclaimer": WINNERS_CURSE,
        "no_pooling": NO_POOLING,
        "ci_note": CI_DISCLAIMER,
        "r460_anchors_NOT_ARBITER": R460_ANCHORS,
    }


def _f(v, nd=2):
    return "n/a" if v is None else f"{v:.{nd}f}"


def render(out: dict) -> str:
    L = ["═══ R460R 五次複製彙總 ═══", ""]
    L.append(f"{'rep':>4} {'狀態':<10} {'H-MIX%':>8} {'CONF%':>8} {'Δ_C':>8} "
             f"{'95% CI':>20} {'p_adj':>9} {'裁決':<16} 拓撲")
    for r in out["reps"]:
        if r.get("status") != "ANALYZED":
            L.append(f"{r['rep']:>4} {str(r.get('status')):<10} "
                     f"（缺 {len(r.get('missing') or [])} 塊）")
            continue
        ci = f"[{_f(r['ci95_lo_pp'])}, {_f(r['ci95_hi_pp'])}]"
        L.append(f"{r['rep']:>4} {'ANALYZED':<10} {_f(r['hmix_deliv_pp']):>8} "
                 f"{_f(r['conform_deliv_pp']):>8} {_f(r['delta_c_pp']):>8} {ci:>20} "
                 f"{_f(r['p_adj'], 4):>9} {str(r['verdict']):<16} "
                 f"{r.get('topology_variant')} {r.get('max_concurrent_by_endpoint')}")
        if r["broken_reasons"]:
            L.append(f"       ⚠ broken_reasons: {r['broken_reasons']}")
    L.append("")
    L.append("── 逐次事前預測（P-R1..P-R5）")
    L.append(f"{'rep':>4}  " + "  ".join(f"{k:<6}" for k in PREDICTIONS))
    for r in out["reps"]:
        if r.get("status") != "ANALYZED":
            continue
        cells = "  ".join(
            f"{('HIT' if r['predictions'][k] else 'MISS' if r['predictions'][k] is False else 'n/a'):<6}"
            for k in PREDICTIONS)
        L.append(f"{r['rep']:>4}  {cells}")
    for k, txt in PREDICTIONS.items():
        L.append(f"   {k}：{txt}")
    gt = out.get("global_topology") or {}
    if gt.get("blocks_n"):
        L += ["", "── 跨複製的逐端點併發對帳（§六-11；事後，排程器說了不算）",
              f"塊數 {gt['blocks_n']}（複製 {gt['reps_covered']}）　"
              f"上限 {gt['caps']}",
              f"實測峰值 {gt['max_concurrent_by_endpoint']}"]
        for ep, w in sorted((gt.get("peak_witness") or {}).items()):
            L.append(f"  {ep} 峰值 {w['n']} 塊：{w['blocks']}")
        L.append("  違規："
                 + (str(gt["violations"]) if gt["violations"] else "無"))
    ag = out["aggregate"]
    L += ["", "── 彙總（描述性；**不併 n**）",
          f"已分析 {ag['reps_analyzed']}/5　H-MIX 裁決計數 {ag['verdict_counts_HMIX']}",
          f"Δ_C 逐次 {ag['delta_c_pp_by_rep']}",
          f"Holm 顯著 {ag['holm_significant_n']}/{ag['reps_analyzed']}　"
          f"全部同號(>0) {ag['all_same_sign_positive']}",
          f"宣稱規則：{ag['statement_rule']}",
          f"⇒ {ag['statement']}",
          "",
          f"⚠ {ag['power_expectation']}",
          f"⚠ {ag['winners_curse_disclaimer']}",
          f"⚠ {ag['no_pooling']}",
          f"⚠ {ag['ci_note']}",
          f"R460 錨（不是判準）：{ag['r460_anchors_NOT_ARBITER']}"]
    return "\n".join(L)


def run(reps: list[int], *, bank: str = "lcb2", rescore_turn1: bool = False,
        root: pathlib.Path = ROOT) -> dict:
    all_blocks: list[dict] = []
    full = [analyze_rep(k, bank=bank, rescore_turn1=rescore_turn1, root=root,
                        blocks_out=all_blocks)
            for k in reps]
    rows = [rep_row(o) for o in full]
    return {"reps": rows, "aggregate": aggregate(rows),
            "global_topology": global_concurrency(all_blocks),
            "full": {o["rep"]: o for o in full}}


def selftest() -> int:
    """拿 R460 那六塊當「第 0 次複製」對釘已知答案（§六 的規則一個字沒改）。

    ⚠ R460 的六塊是 `fixed` 拓撲（one_backend_6）、而且它有 P-H0；
      這裡刻意**照它原本的讀法**跑，證明本檔沒有改動 `analyze_r460` 的仲裁值。
    """
    fails: list[str] = []

    def ck(label, cond, extra=""):
        if not cond:
            fails.append(f"{label}{(' — ' + extra) if extra else ''}")

    dirs = [ROOT / "runs" / n for n in AUTHORIZED_BLOCKS]
    if any(not (d / "rows.jsonl").exists() for d in dirs):
        print("selftest: SKIP（本機沒有 R460 那六塊資料）")
        return 0
    rows, summary, calls, blocks = pool_runs(dirs)
    out = analyze(rows, summary, calls, bank=load_bank_meta("lcb2"), blocks=blocks)
    out["rep"] = 0
    out["status"] = "ANALYZED"
    r = rep_row(out)
    ck("A_no_broken", out["broken_reasons"] == [], str(out["broken_reasons"]))
    ck("B_hmix_deliv_84_17", round(r["hmix_deliv_pp"], 2) == 84.17,
       str(r["hmix_deliv_pp"]))
    ck("C_conform_deliv_70_83", round(r["conform_deliv_pp"], 2) == 70.83,
       str(r["conform_deliv_pp"]))
    ck("D_delta_c_13_33", round(r["delta_c_pp"], 2) == 13.33, str(r["delta_c_pp"]))
    ck("E_holm_p_adj_0_0112", round(r["p_adj"], 4) == 0.0112, str(r["p_adj"]))
    ck("F_verdict_effective", r["verdict"] == "EFFECTIVE", str(r["verdict"]))
    ck("G_false_delivery_14_vs_29",
       r["false_delivery_n_hmix"] == 14 and r["false_delivery_n_conform"] == 29,
       f"{r['false_delivery_n_hmix']}/{r['false_delivery_n_conform']}")
    ck("H_predictions_all_hit_on_r460",
       all(r["predictions"][k] is True for k in PREDICTIONS),
       str(r["predictions"]))
    # 彙總不准把一次當五次：只有一列時宣稱規則必須落在「逐次照實列」。
    ag = aggregate([r])
    ck("I_one_rep_is_not_stable",
       ag["reps_analyzed"] == 1 and "逐次照實列" in ag["statement"],
       ag["statement"])
    # 併 n 的路徑必須不存在（機制不是承諾）：彙總的欄位形狀自己說得出來——
    # 沒有任何一個鍵是「把五次加起來」的量。
    ck("J_aggregate_has_no_pooled_estimate",
       not any(k.startswith("pooled") or k in ("n_common", "b", "c", "delta_c_pp")
               for k in ag),
       str(sorted(ag)))
    # 宣稱規則的正向牙齒：五列同號且全顯著 ⇒ 必須判成「複製穩定」；
    # 把其中一列翻成負的 ⇒ 必須掉回「逐次照實列」。
    five = []
    for k in range(1, 6):
        c = dict(r)
        c["rep"] = k
        five.append(c)
    ag5 = aggregate(five)
    ck("K_statement_rule_fires_on_5_of_5",
       ag5["reps_analyzed"] == 5 and ag5["all_same_sign_positive"] is True
       and ag5["holm_significant_n"] == 5 and "複製穩定" in ag5["statement"]
       and list(ag5["delta_c_pp_by_rep"]) == [1, 2, 3, 4, 5],
       ag5["statement"])
    flipped = [dict(c) for c in five]
    flipped[2] = dict(flipped[2])
    flipped[2]["delta_c_pp"] = -1.0
    flipped[2]["predictions"] = dict(flipped[2]["predictions"], **{"P-R1": False})
    ag5b = aggregate(flipped)
    ck("K2_one_opposite_sign_kills_the_claim",
       ag5b["all_same_sign_positive"] is False and "逐次照實列" in ag5b["statement"],
       ag5b["statement"])

    # ── §六-11 跨複製併發：合成塊上的正反兩向牙齒（零資料依賴）────────────
    from ops.gain.analyze_r460 import ENDPOINT_1004

    def blk(name, rep, ep, lo, hi):
        return {"name": name, "rep": rep, "endpoints": [ep],
                "calls": [{"ts_ms": lo, "latency_ms": 0},
                          {"ts_ms": hi, "latency_ms": 0}]}

    three = [blk(f"b{i}", 1, ENDPOINT_1004, 0, 100) for i in range(3)]
    ck("L_three_concurrent_on_1004_is_clean",
       global_concurrency(three)["violations"] == []
       and global_concurrency(three)["max_concurrent_by_endpoint"][ENDPOINT_1004] == 3,
       str(global_concurrency(three)))
    # 第四塊來自**另一次複製**——逐次的帳看不到它，這條就是為了它存在的。
    four = three + [blk("b3", 2, ENDPOINT_1004, 50, 150)]
    g4 = global_concurrency(four)
    ck("M_a_fourth_block_from_another_rep_is_a_violation",
       any(s.startswith("endpoint_concurrency_exceeded_global") for s in g4["violations"])
       and g4["peak_witness"][ENDPOINT_1004]["n"] == 4
       and g4["reps_covered"] == [1, 2],
       str(g4["violations"]))
    gx = global_concurrency([blk("bx", 1, "http://10.0.0.1:1234/v1/chat/completions",
                                 0, 1)])
    ck("N_unregistered_endpoint_is_a_violation",
       any(s.startswith("endpoint_not_registered") for s in gx["violations"]),
       str(gx["violations"]))
    gz = global_concurrency([{"name": "bz", "rep": 1,
                              "endpoints": [ENDPOINT_1004], "calls": []}])
    ck("O_no_timestamps_is_a_violation_not_a_pass",
       any(s.startswith("block_ts_unrecorded") for s in gz["violations"]),
       str(gz["violations"]))
    print("selftest: " + ("PASS" if not fails else "FAIL\n  " + "\n  ".join(fails)))
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", nargs="+", type=int, choices=[1, 2, 3, 4, 5],
                    help="要分析哪幾次複製（預設 1..5）")
    ap.add_argument("--bank", default="lcb2", choices=["lcb2", "lcb3"])
    ap.add_argument("--rescore-turn1", action="store_true")
    ap.add_argument("--json", help="把完整報表寫成 JSON")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    out = run(args.reps or [1, 2, 3, 4, 5], bank=args.bank,
              rescore_turn1=args.rescore_turn1)
    print(render(out))
    if args.json:
        slim = {"reps": out["reps"], "aggregate": out["aggregate"],
                "global_topology": out["global_topology"]}
        pathlib.Path(args.json).write_text(
            json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON → {args.json}")
    bad = [r for r in out["reps"]
           if r.get("status") == "ANALYZED" and r.get("broken_reasons")]
    # 跨複製的併發違規與逐次的 broken_reasons 同級：都讓退出碼變 1。
    return 1 if (bad or (out["global_topology"] or {}).get("violations")) else 0


if __name__ == "__main__":
    raise SystemExit(main())
