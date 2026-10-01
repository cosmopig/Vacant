#!/usr/bin/env python3
"""analyze_i1001 — i1001 的分析：兩個主要檢定（K 對 R、C 對 A；精確 McNemar、Holm）＋描述。

    python3 analyze_i1001.py --chunks <本機 chunk 目錄> --out <輸出目錄>
    python3 analyze_i1001.py --cells  <解開的 cells 目錄>  --out <輸出目錄>

這支在架構裡承重什麼：這一批要回答的問題只有兩個，而且都是「同一題配對」的問題——
  1. K（CONFORM：用可見驗收把關、不過就帶著回報就地再來、最多 3 段、只放行過的）對 R（RETRY-NOSUITE：逾時或沒交件才在複本上
     重來、沒有任何回饋、最多 3 段）：指標＝「被放行 且 隱藏測試全過」（K）對「隱藏測試全過」（R）。
     兩者共用 A 的第 1 段，所以差別只來自「有沒有可見驗收＋回報」。只有 K 能跑的題庫（LCB）。
  2. C（零設定 Vacant）對 A（沒裝）：指標＝隱藏測試全過；A 計第 1 段的工作區快照。
兩個都用精確 McNemar（只看不一致對，二項、p=0.5，雙尾），α＝0.05，**Holm 校正兩個主要檢定**。
排除：infra_void（列出、不算進任何一組的失敗）；同一格有重跑（`v2`）時只取最後一次。
其餘全是描述：每個題庫、每種題池角色、救回／傷害（A 沒過 C 過、A 過 C 沒過）、錯交（交了但隱藏沒過）、session 數、token、牆鐘、
Vacant 的退回、K 的接受／放行、R 的重試、篩選階段的天花板決定。
不能說的：「Vacant 讓 agent 做得更好」不帶條件；把探索性的分項（題庫、角色）當成檢定；把機制替身的冒煙結果當成證據。
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib
import statistics
import sys
import tarfile
from typing import Any, Iterable


# ── 統計 ────────────────────────────────────────────────────────────────────────────────────────


def binom_two_sided(b: int, c: int) -> float:
    """配對二元的 McNemar 精確（雙尾）：對不一致對 b、c 做 p=0.5 的二項檢定（同 vacant_network.research.mcnemar_exact）。"""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) * (0.5 ** n))


def holm(pvals: list[float]) -> list[float]:
    """Holm step-down 校正後 p（順序同輸入；同 vacant_network.research.holm_bonferroni）。"""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: (pvals[i], i))
    out = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        out[i] = running
    return out


# ── 讀紀錄 ──────────────────────────────────────────────────────────────────────────────────────

WANT = {"meta.json", "score.json"}


def load_from_dir(root: pathlib.Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        rec: dict[str, Any] = {"cell": d.name, "done": (d / "DONE").exists(), "meta": None, "score": None}
        for f in WANT:
            p = d / f
            if p.is_file():
                rec[f.split(".")[0]] = _parse(p.read_text(), f == "score.json")
        out[d.name] = rec
    return out


def _parse(text: str, last_line: bool) -> Any:
    try:
        if last_line:
            lines = [x for x in text.strip().splitlines() if x.strip()]
            return json.loads(lines[-1])
        return json.loads(text)
    except (ValueError, IndexError):
        return None


def load_from_chunks(chunk_dir: pathlib.Path) -> tuple[dict[str, dict], dict[str, Any]]:
    """直接從 chunk_*.tar.xz 串流讀 meta.json／score.json／DONE（不解壓整包）；另回傳 `_run_*` 格的紀錄（計畫、天花板決定）。"""
    out: dict[str, dict] = {}
    run_records: dict[str, Any] = {}
    for tp in sorted(chunk_dir.glob("chunk_*.tar.xz")):
        with tarfile.open(tp, "r:xz") as t:
            for m in t:
                if not m.isfile():
                    continue
                parts = m.name.split("/")
                if len(parts) != 3 or parts[0] != "cells":
                    continue
                cell, fname = parts[1], parts[2]
                if cell.startswith("_run_"):
                    if fname in ("ceiling_decision.json", "plan.json", "meta.json"):
                        run_records.setdefault(cell, {})[fname] = _parse(t.extractfile(m).read().decode(), False)
                    continue
                if fname not in WANT and fname != "DONE":
                    continue
                rec = out.setdefault(cell, {"cell": cell, "done": False, "meta": None, "score": None})
                if fname == "DONE":
                    rec["done"] = True
                else:
                    rec[fname.split(".")[0]] = _parse(t.extractfile(m).read().decode(), fname == "score.json")
    return out, run_records


# ── 一格 → 一列 ─────────────────────────────────────────────────────────────────────────────────


def row_of(rec: dict) -> dict | None:
    m = rec.get("meta")
    if not m or not rec.get("done"):
        return None
    sc = rec.get("score") or {}
    sessions = m.get("sessions") or []
    led = [s.get("ledger") or {} for s in sessions]
    k = m.get("k") or {}
    released = bool(k.get("released")) if m.get("arm") == "K" else None
    passed = bool(sc.get("pass")) if (not m.get("void")) else None
    if m.get("arm") == "K":
        metric = bool(released and passed) if passed is not None else None
    else:
        metric = passed
    delivered = (released if m.get("arm") == "K" else bool(m.get("delivered")))
    return {"cell": m["cell"], "phase": m.get("phase") or "main", "unit": m["unit"], "bank": m["bank"], "task": m["task"],
            "arm": m["arm"], "sample": m.get("sample", 1), "attempt": m.get("attempt", 1), "role": m.get("role"),
            "screened": m.get("screened"), "void": bool(m.get("void")), "void_reason": m.get("void_reason"),
            "group_void": bool(m.get("group_void")), "pass": passed, "metric": metric, "delivered": delivered,
            "released": released, "wrong_delivery": bool(delivered and passed is False),
            "visible_pass": sc.get("visible_pass"), "false_done": sc.get("false_done"),
            "timeout": bool(m.get("timeout")), "n_sessions": m.get("n_sessions"), "wall_s": m.get("wall_s"),
            "prompt_tokens": sum(int(x.get("prompt_tokens") or 0) for x in led),
            "completion_tokens": sum(int(x.get("completion_tokens") or 0) for x in led),
            "calls": sum(int(x.get("calls") or 0) for x in led),
            "install_rc": m.get("install_rc"), "c_arm_ok": m.get("c_arm_ok"), "stop_reached": m.get("stop_reached"),
            "retry_needed": m.get("retry_needed"), "retry_reasons": m.get("retry_reasons"),
            "k_attempts": [a.get("rc") for a in (k.get("attempts") or [])] if k else None,
            "k_on": m.get("k_on"), "workspace_has_bridge_contract": m.get("workspace_has_bridge_contract"),
            "sendbacks": sum(int(s.get("sendbacks") or 0) for s in sessions),
            "sessions": sessions}


def final_rows(raw: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    """每個 (phase, unit, arm, sample) 取最後一次 attempt；回傳 (最終列, 被重跑取代的 void 列)。"""
    rows = [r for r in (row_of(x) for x in raw.values()) if r]
    best: dict[tuple, dict] = {}
    for r in rows:
        key = (r["phase"], r["unit"], r["arm"], r["sample"])
        if key not in best or r["attempt"] > best[key]["attempt"]:
            best[key] = r
    final = list(best.values())
    superseded = [r for r in rows if best[(r["phase"], r["unit"], r["arm"], r["sample"])] is not r]
    return final, superseded


# ── 配對檢定 ────────────────────────────────────────────────────────────────────────────────────


def paired(rows: list[dict], x_arm: str, y_arm: str, phase: str = "main", *, x_metric: str = "metric",
           y_metric: str = "metric", restrict: Iterable[str] | None = None) -> dict:
    """x 組對 y 組：同一 (unit, sample) 兩邊都有、都不是 void 才進配對。b＝y 過 x 沒過、c＝x 過 y 沒過（x 是基準組）。"""
    by: dict[tuple, dict[str, dict]] = collections.defaultdict(dict)
    for r in rows:
        if r["phase"] != phase:
            continue
        if restrict is not None and r["bank"] not in set(restrict):
            continue
        by[(r["unit"], r["sample"])][r["arm"]] = r
    pairs, excluded = [], []
    for key, d in sorted(by.items()):
        if x_arm in d and y_arm in d and not d[x_arm]["void"] and not d[y_arm]["void"] \
                and d[x_arm][x_metric] is not None and d[y_arm][y_metric] is not None:
            pairs.append((key, d[x_arm], d[y_arm]))
        elif x_arm in d or y_arm in d:
            excluded.append({"unit": key[0], "sample": key[1],
                             "why": {a: ("void: " + str(d[a]["void_reason"])) if d[a]["void"] else "ok" for a in (x_arm, y_arm) if a in d}
                             | {a: "missing" for a in (x_arm, y_arm) if a not in d}})
    b = sum(1 for _, x, y in pairs if y[y_metric] and not x[x_metric])
    c = sum(1 for _, x, y in pairs if x[x_metric] and not y[y_metric])
    both = sum(1 for _, x, y in pairs if x[x_metric] and y[y_metric])
    neither = len(pairs) - b - c - both
    return {"x": x_arm, "y": y_arm, "pairs": len(pairs), "x_pass": both + c, "y_pass": both + b, "b_y_only": b, "c_x_only": c,
            "both": both, "neither": neither, "p_mcnemar_exact_two_sided": binom_two_sided(b, c),
            "excluded": excluded,
            "y_only_units": [k[0] for k, x, y in pairs if y[y_metric] and not x[x_metric]],
            "x_only_units": [k[0] for k, x, y in pairs if x[x_metric] and not y[y_metric]]}


def arm_desc(rows: list[dict], arm: str, phase: str = "main", units: set | None = None) -> dict:
    rs = [r for r in rows if r["arm"] == arm and r["phase"] == phase and not r["void"] and (units is None or (r["unit"], r["sample"]) in units)]
    w = [r["wall_s"] for r in rs if r["wall_s"] is not None]
    return {"n": len(rs), "pass": sum(1 for r in rs if r["pass"]), "metric_pass": sum(1 for r in rs if r["metric"]),
            "delivered": sum(1 for r in rs if r["delivered"]), "wrong_deliveries": sum(1 for r in rs if r["wrong_delivery"]),
            "not_delivered": sum(1 for r in rs if not r["delivered"]), "timeouts": sum(1 for r in rs if r["timeout"]),
            "sessions_total": sum(r["n_sessions"] or 0 for r in rs),
            "sessions_mean": round(statistics.mean([r["n_sessions"] or 0 for r in rs]), 3) if rs else None,
            "wall_s_total": round(sum(w), 1), "wall_s_median": statistics.median(w) if w else None,
            "calls": sum(r["calls"] for r in rs), "prompt_tokens": sum(r["prompt_tokens"] for r in rs),
            "completion_tokens": sum(r["completion_tokens"] for r in rs)}


def screening_table(rows: list[dict]) -> dict:
    out: dict[str, Any] = {}
    for bank in sorted({r["bank"] for r in rows if r["phase"] == "screen"}):
        rs = [r for r in rows if r["phase"] == "screen" and r["bank"] == bank and r["arm"] == "A"]
        ok = [r for r in rs if not r["void"]]
        out[bank] = {"n": len(rs), "void": len(rs) - len(ok), "pass": sum(1 for r in ok if r["pass"]),
                     "unsolved": sorted(r["task"] for r in ok if r["pass"] is False)}
    return out


def audit_sessions(rows: list[dict]) -> dict:
    ss = [s for r in rows for s in r["sessions"] if not s.get("shared_with_A")]
    gaps = [s["max_gap_after_final_s"] for s in ss if s.get("max_gap_after_final_s") is not None]
    return {"sessions": len(ss), "done_reasons": dict(collections.Counter(s.get("done_reason") for s in ss)),
            "late_write_after_done": sum(1 for s in ss if s.get("late_write_after_done")),
            "max_gap_after_final_s": max(gaps) if gaps else None, "idle_s": sorted({s.get("idle_s") for s in ss if s.get("idle_s")}),
            "submit_unconfirmed": sum(1 for s in ss if s.get("submit_unconfirmed")),
            "trust_dialog": sum(1 for s in ss if s.get("trust_dialog")),
            "typed_mismatch": sum(1 for s in ss if s.get("typed_ok") is False),
            "exit_not_clean": sum(1 for s in ss if s.get("exit_clean") is False),
            "compactions": sum(int(s.get("compactions") or 0) for s in ss)}


def analyze(raw: dict[str, dict], run_records: dict | None = None) -> dict:
    rows, superseded = final_rows(raw)
    kbank_units = {r["bank"] for r in rows if r["arm"] == "K"}
    ca = paired(rows, "A", "C")
    kr = paired(rows, "R", "K", restrict=kbank_units)
    p_raw = [kr["p_mcnemar_exact_two_sided"], ca["p_mcnemar_exact_two_sided"]]
    adj = holm(p_raw)
    main_units = {(r["unit"], r["sample"]) for r in rows if r["phase"] == "main"}
    res: dict[str, Any] = {
        "primary": {"K_vs_R": {**kr, "metric": "K: released AND hidden pass; R: hidden pass", "p_holm": adj[0]},
                    "C_vs_A": {**ca, "metric": "hidden pass", "p_holm": adj[1]},
                    "alpha": 0.05, "holm_family": ["K_vs_R", "C_vs_A"],
                    "significant_after_holm": {"K_vs_R": adj[0] < 0.05, "C_vs_A": adj[1] < 0.05}},
        "arms": {arm: arm_desc(rows, arm) for arm in ("A", "C", "R", "K")},
        "by_bank": {}, "by_role": {}, "screening": screening_table(rows),
        "void_final": [{"cell": r["cell"], "arm": r["arm"], "phase": r["phase"], "reason": r["void_reason"]} for r in rows if r["void"]],
        "void_superseded_by_rerun": [{"cell": r["cell"], "arm": r["arm"], "reason": r["void_reason"]} for r in superseded if r["void"]],
        "group_void_flags": [r["cell"] for r in rows if r["group_void"]],
        "k_unavailable_units": sorted({r["unit"] for r in rows if r["arm"] == "A" and r["phase"] == "main" and r["k_on"] is False
                                       and r["bank"] in kbank_units}),
        "audit": audit_sessions(rows),
        "n_units_main": len(main_units)}
    for bank in sorted({r["bank"] for r in rows if r["phase"] == "main"}):
        res["by_bank"][bank] = {"C_vs_A": paired(rows, "A", "C", restrict=[bank]),
                                "K_vs_R": paired(rows, "R", "K", restrict=[bank]) if bank in kbank_units else None}
        res["by_bank"][bank] = {k: ({kk: vv for kk, vv in v.items() if kk not in ("excluded", "y_only_units", "x_only_units")} if v else None)
                                for k, v in res["by_bank"][bank].items()}
    for role in sorted({r["role"] for r in rows if r["phase"] == "main" and r["role"]}):
        us = {(r["unit"], r["sample"]) for r in rows if r["phase"] == "main" and r["role"] == role}
        res["by_role"][role] = {arm: arm_desc(rows, arm, units=us) for arm in ("A", "C", "R", "K")}
    # 救回／傷害（C 對 A；K／R 對 A）：描述
    by: dict[tuple, dict[str, dict]] = collections.defaultdict(dict)
    for r in rows:
        if r["phase"] == "main":
            by[(r["unit"], r["sample"])][r["arm"]] = r
    rescue = collections.Counter()
    for _k, d in by.items():
        a = d.get("A")
        if not a or a["void"]:
            continue
        for arm in ("C", "R", "K"):
            x = d.get(arm)
            if x and not x["void"] and x["metric"] is not None:
                if not a["metric"] and x["metric"]:
                    rescue[f"{arm}_rescues_A_failure"] += 1
                if a["metric"] and not x["metric"]:
                    rescue[f"{arm}_loses_A_success"] += 1
    res["vs_A_descriptive"] = dict(rescue)
    ks = [r for r in rows if r["arm"] == "K" and r["phase"] == "main" and not r["void"]]
    res["K_diagnostics"] = {"n": len(ks), "released": sum(1 for r in ks if r["released"]),
                            "accepted_at_attempt": dict(collections.Counter(
                                next((i + 1 for i, rc in enumerate(r["k_attempts"] or []) if rc == 0), 0) for r in ks)),
                            "released_but_hidden_fail": sum(1 for r in ks if r["released"] and r["pass"] is False),
                            "never_released": sum(1 for r in ks if not r["released"])}
    rs_ = [r for r in rows if r["arm"] == "R" and r["phase"] == "main" and not r["void"]]
    res["R_diagnostics"] = {"n": len(rs_), "retried": sum(1 for r in rs_ if r["retry_needed"]),
                            "retry_reasons": dict(collections.Counter(x for r in rs_ for x in (r["retry_reasons"] or [])))}
    cs = [r for r in rows if r["arm"] == "C" and r["phase"] == "main" and not r["void"]]
    res["C_diagnostics"] = {"n": len(cs), "c_arm_ok": sum(1 for r in cs if r["c_arm_ok"]), "stop_reached": sum(1 for r in cs if r["stop_reached"]),
                            "cells_with_sendback": sum(1 for r in cs if r["sendbacks"]), "sendbacks_total": sum(r["sendbacks"] for r in cs),
                            "install_fail": sum(1 for r in cs if r["install_rc"] not in (0, None))}
    if run_records:
        res["run_records"] = {k: {"ceiling_decision": v.get("ceiling_decision.json")} for k, v in run_records.items()}
    res["_rows"] = rows
    return res


# ── 報告 ────────────────────────────────────────────────────────────────────────────────────────


def _p(x: float) -> str:
    return f"{x:.4g}"


def markdown(res: dict) -> str:
    pr = res["primary"]
    kr, ca = pr["K_vs_R"], pr["C_vs_A"]
    L = ["# i1001 分析報告（互動式 pi：沒裝／零設定 Vacant／重試／可見驗收把關）", "",
         "## 主要檢定（精確 McNemar、雙尾、Holm 校正兩個）", "",
         "| 檢定 | 指標 | 配對 | x 組過 | y 組過 | 只有 y 過（b） | 只有 x 過（c） | p（未校正） | p（Holm） | α=0.05 |", "|---|---|---|---|---|---|---|---|---|---|",
         f"| K 對 R（x＝R、y＝K） | 被放行且隱藏全過 ／ 隱藏全過 | {kr['pairs']} | {kr['x_pass']} | {kr['y_pass']} | {kr['b_y_only']} | {kr['c_x_only']} | "
         f"{_p(kr['p_mcnemar_exact_two_sided'])} | {_p(kr['p_holm'])} | {'顯著' if pr['significant_after_holm']['K_vs_R'] else '不顯著'} |",
         f"| C 對 A（x＝A、y＝C） | 隱藏全過 | {ca['pairs']} | {ca['x_pass']} | {ca['y_pass']} | {ca['b_y_only']} | {ca['c_x_only']} | "
         f"{_p(ca['p_mcnemar_exact_two_sided'])} | {_p(ca['p_holm'])} | {'顯著' if pr['significant_after_holm']['C_vs_A'] else '不顯著'} |",
         "", "不顯著 ＝ **這一批沒有量到差別**，不是「沒有差別」；顯著也只說明這個題池、這個模型、這個設定（見下面的誠實邊界）。", "",
         "## 各組描述（主跑、非 void）", "", "| 組 | n | 隱藏全過 | 指標過 | 交了 | 錯交（交了但隱藏沒過） | 沒交 | 逾時 | session 總數 | 牆鐘中位數(s) | 輸入 token | 輸出 token |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for arm, d in res["arms"].items():
        L.append(f"| {arm} | {d['n']} | {d['pass']} | {d['metric_pass']} | {d['delivered']} | {d['wrong_deliveries']} | {d['not_delivered']} | "
                 f"{d['timeouts']} | {d['sessions_total']} | {d['wall_s_median']} | {d['prompt_tokens']} | {d['completion_tokens']} |")
    L += ["", "K、R 的 session 數／token／牆鐘含與 A 共用的第 1 段。", "", "## 篩選階段（只跑 A；天花板規則 ≥ 9/10 丟題庫）", "",
          "| 題庫 | 跑了 | void | A 答對 | 沒解開的題 |", "|---|---|---|---|---|"]
    for bank, d in res["screening"].items():
        L.append(f"| {bank} | {d['n']} | {d['void']} | {d['pass']} | {', '.join(d['unsolved']) or '—'} |")
    for k, v in (res.get("run_records") or {}).items():
        cd = v.get("ceiling_decision")
        if cd:
            L += ["", f"天花板決定（{k}）：丟掉的題庫＝{cd.get('dropped_banks')}"]
            for b, x in cd["banks"].items():
                L.append(f"- {b}：{x['reason']}")
    L += ["", "## 各題庫（描述，不是檢定）", "", "| 題庫 | C 對 A 配對 | A 過 | C 過 | 只有 C 過 | 只有 A 過 | K 對 R 配對 | R 過 | K 過 | 只有 K 過 | 只有 R 過 |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for bank, d in res["by_bank"].items():
        c, k = d["C_vs_A"], d["K_vs_R"]
        L.append(f"| {bank} | {c['pairs']} | {c['x_pass']} | {c['y_pass']} | {c['b_y_only']} | {c['c_x_only']} | " +
                 (f"{k['pairs']} | {k['x_pass']} | {k['y_pass']} | {k['b_y_only']} | {k['c_x_only']} |" if k else "— | — | — | — | — |"))
    L += ["", "## 救回／傷害（描述，相對於 A）", "", "```json", json.dumps(res["vs_A_descriptive"], ensure_ascii=False, indent=1), "```", "",
          "## K／R／C 的過程", "", "```json", json.dumps({"K": res["K_diagnostics"], "R": res["R_diagnostics"], "C": res["C_diagnostics"]},
                                                      ensure_ascii=False, indent=1), "```", "",
          "## infra_void 與完成偵測稽核", "",
          f"- 最終仍 void 的格：{len(res['void_final'])}；被重跑取代的 void：{len(res['void_superseded_by_rerun'])}；"
          f"K 起不來的單位：{len(res['k_unavailable_units'])}。（逐格清單在 report.json）",
          f"- 完成偵測：session {res['audit']['sessions']} 段；`late_write_after_done`＝{res['audit']['late_write_after_done']}"
          f"（非 0 ⇒ IDLE_S 太短）；最終 stop 之後的最大間隔＝{res['audit']['max_gap_after_final_s']} s（IDLE_S＝{res['audit']['idle_s']}）；"
          f"完成原因＝{res['audit']['done_reasons']}；送出未確認＝{res['audit']['submit_unconfirmed']}；信任對話框＝{res['audit']['trust_dialog']}；"
          f"打字不符＝{res['audit']['typed_mismatch']}。", "",
          "## 誠實邊界", "",
          "- 題池不是隨機抽樣的全體：LCB 部分是 C5 的 A 失敗題（93）＋種子抽的 A 成功對照（40），任務題庫是通過天花板規則的題庫；"
          "結論只說這個題池。",
          "- A、R、K 共用 A 的第 1 段，工作區有 bridge 寫的 `.vacant/contract.json`（沒裝 Vacant 時不起作用）；C 的工作區沒有契約"
          "（有契約會關掉零設定檢查）。這個差別已記進每格 meta.json。",
          "- K 的 bridge 是 non-adversarial 的基準輔助；放行的成品由計分器另行計分，K 的「放行」只代表可見驗收過了。",
          "- 互動式「跑完」是從 session 檔推論的（安靜 IDLE_S 秒）；稽核數字在上面。",
          "- ❌「Vacant 讓 agent 做得更好」不帶條件；❌ 把分項（題庫、角色）當成檢定；❌ 外推到真人互動使用。"]
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--chunks", type=pathlib.Path)
    g.add_argument("--cells", type=pathlib.Path)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    a = ap.parse_args(argv)
    if a.chunks:
        raw, runrec = load_from_chunks(a.chunks)
    else:
        raw, runrec = load_from_dir(a.cells), {}
        for d in sorted(a.cells.glob("_run_*")):
            cd = d / "ceiling_decision.json"
            if cd.is_file():
                runrec[d.name] = {"ceiling_decision.json": _parse(cd.read_text(), False)}
    res = analyze(raw, runrec)
    rows = res.pop("_rows")
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "report.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n")
    (a.out / "cells.jsonl").write_text("".join(json.dumps({k: v for k, v in r.items() if k != "sessions"}, ensure_ascii=False) + "\n" for r in rows))
    md = markdown(res)
    (a.out / "report.md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
