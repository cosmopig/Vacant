#!/usr/bin/env python3
"""e006_verdict — e006 預註冊假說判定量具（唯讀，僅 --out 給定時寫該檔）。

依據 e006 封包 §3（ops/vlab/packets/e006_opencode_polyglot.md，發射前寫死）：
- 4 組 A_vs_X（C/H/M/S）McNemar 雙尾 p 跑 Holm–Bonferroni α=0.05 確認線；未校正 p 只作描述。
- 成本紅線：任一臂 calls_per_success 或 tokens_per_success > 2×A 且通過率未顯著提升 ⇒「不划算」；成本必須與結果一起報告。
- M 臂需 events.jsonl 真第二 agent 證據（opencode_cell_audit 的 per-cell second_agent_verified）；無 ⇒ H-review(M) 降級 UNKNOWN（量不到，不是負結果；e005 已 UNKNOWN 一次，e006 再缺仍記 UNKNOWN、不計臂失敗、報告中註記為機制訊號）。
- 不顯著 ⇒ 未建立（不是負結果）；顯著但成本 > 2×A ⇒「有效但昂貴」；H-stakes(a) 只是講、無真實後果。

規則：不改共用量具（cell.py/labd.py/report.py）；不內嵌任何真實結果數據（合成 mock 只活在 --selftest）；無網路依賴。
介面參考 ops/vlab/tools/e004_verdict.py（同結構，e006 schema/notes）。

用法：
  python3 ops/vlab/tools/e006_verdict.py --selftest
  python3 ops/vlab/tools/e006_verdict.py <exp> [--runs-dir DIR] [--report PATH]
      [--audit PATH] [--alpha 0.05] [--out PATH] [--json]

退出碼：0 產出判定（含 UNKNOWN）；1 無 REPORT.json（無事可做）；2 REPORT.json 格式不符。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ARMS = ("C", "H", "M", "S")
HYP = {"C": "H-acc", "H": "H-review(H)", "M": "H-review(M)", "S": "H-stakes(a)"}


def num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def holm_adjust(pvals):
    """優先 vacant_network.research.holm_bonferroni；import 失敗用內嵌 step-down（同一演算法）。"""
    try:
        from vacant_network.research import holm_bonferroni
        return list(holm_bonferroni(list(pvals))), "vacant_network.research.holm_bonferroni"
    except Exception:
        m = len(pvals)
        adj, running = [0.0] * m, 0.0
        for rank, i in enumerate(sorted(range(m), key=lambda i: (pvals[i], i))):
            running = max(running, min(1.0, (m - rank) * pvals[i]))
            adj[i] = running
        return adj, "inline (step-down)"


def cost_redline(per_arm, audit_per_arm=None):
    """各臂 vs A 的成本比；over_2x_A_cost：True/False/None（None = 有維度量不到，不判違規也不判過）。
    若 REPORT.json 成本為 0.0 或缺失（如 OpenCode 無 cell.json metrics），可由 audit_per_arm 補充。
    """
    a = per_arm.get("A") if isinstance(per_arm.get("A"), dict) else {}
    bc, bt = num(a.get("calls_per_success")), num(a.get("tokens_per_success"))
    if (not bc or not bt) and isinstance(audit_per_arm, dict):
        aud_a = audit_per_arm.get("A") if isinstance(audit_per_arm.get("A"), dict) else {}
        if not bc:
            bc = num(aud_a.get("calls_per_success"))
        if not bt:
            bt = num(aud_a.get("tokens_per_success"))
    base = {"calls_per_success": bc, "tokens_per_success": bt}
    out = {}
    for x in ARMS:
        d = per_arm.get(x) if isinstance(per_arm.get(x), dict) else {}
        c, t = num(d.get("calls_per_success")), num(d.get("tokens_per_success"))
        if (c is None or t is None or c == 0.0 or t == 0.0) and isinstance(audit_per_arm, dict):
            aud_x = audit_per_arm.get(x) if isinstance(audit_per_arm.get(x), dict) else {}
            if c is None or c == 0.0:
                c = num(aud_x.get("calls_per_success"))
            if t is None or t == 0.0:
                t = num(aud_x.get("tokens_per_success"))
        cc, tt = (c / bc) if (c is not None and bc) else None, (t / bt) if (t is not None and bt) else None
        co, to = (cc > 2.0) if cc is not None else None, (tt > 2.0) if tt is not None else None
        over = True if (co is True or to is True) else (False if (co is False and to is False) else None)
        out[x] = {"calls_vs_A": cc, "tokens_vs_A": tt, "over_2x_A_cost": over, "not_worth_it": None}
    return {"A_base": base, "arms": out}


def m_evidence(audit_summary):
    """M 臂第二 agent 證據：verified_cells>=1 才算「有」；量不到（無 audit／無 M）一律不視為有。"""
    if not isinstance(audit_summary, dict):
        return {"source": "no_audit", "verified_cells": None, "unknown_cells": None, "evidence_present": False}
    s = audit_summary.get("summary") if isinstance(audit_summary.get("summary"), dict) else audit_summary
    m = (s.get("per_arm") or {}).get("M") if isinstance(s, dict) else None
    if isinstance(m, dict):
        v, u = num(m.get("second_agent_verified_cells")), num(m.get("second_agent_unknown_cells"))
    else:
        v = u = None
    if v is None and u is None:
        return {"source": "audit_without_M", "verified_cells": None, "unknown_cells": None, "evidence_present": False}
    return {"source": "audit", "verified_cells": int(v or 0), "unknown_cells": int(u) if u is not None else None,
            "evidence_present": int(v or 0) >= 1}


def evaluate_hypotheses(report_data, audit_summary, alpha: float = 0.05):
    """e006 封包 §3 的 4 項假說判定（H-acc / H-review(H) / H-review(M) / H-stakes(a)）。"""
    paired = report_data.get("paired") if isinstance(report_data, dict) else None
    if not isinstance(paired, dict):
        raise ValueError("REPORT.json 缺 paired 區塊（格式不符）")
    per_arm = report_data.get("per_arm") if isinstance(report_data.get("per_arm"), dict) else {}
    raw = {x: (num((paired.get("A_vs_" + x) or {}).get("mcnemar_p_two_sided"))
               if isinstance(paired.get("A_vs_" + x), dict) else None) for x in ARMS}
    order = [x for x in ARMS if raw[x] is not None]
    adj, impl = {x: None for x in ARMS}, "none"
    if order:
        corr, impl = holm_adjust([raw[x] for x in order])
        adj.update(zip(order, corr))
    aud_s = audit_summary.get("summary") if isinstance(audit_summary, dict) and "summary" in audit_summary else audit_summary
    aud_arm = aud_s.get("per_arm") if isinstance(aud_s, dict) else None
    cost = cost_redline(per_arm, aud_arm)
    ev = m_evidence(audit_summary)
    hyp = {}
    for x in ARMS:
        blk = paired.get("A_vs_" + x)
        a_only = num(blk.get("A_only")) if isinstance(blk, dict) else None
        x_only = num(blk.get(x + "_only")) if isinstance(blk, dict) else None
        p, pa = raw[x], adj[x]
        sig = pa is not None and pa < alpha
        e = {"arm": x, "p_raw": p, "p_holm": pa, "significant_at_alpha": sig,
             "A_only": a_only, "X_only": x_only, "cost_over_2x_A": cost["arms"][x]["over_2x_A_cost"]}
        if p is None:
            e.update(state="UNKNOWN", reason="配對缺失、未測（不進 Holm 集）——UNKNOWN，不是沒有")
        elif a_only is None or x_only is None:
            e.update(state="UNKNOWN", reason="配對計數缺失（量不到方向）——UNKNOWN，不是沒有")
        elif x == "M" and not ev["evidence_present"]:
            e.update(state="UNKNOWN", second_agent=ev,
                     reason="無第二 agent 證據 ⇒ 降級「提示式自檢」、記 UNKNOWN（量不到，不是負結果）；"
                            "e005 已 UNKNOWN 一次，e006 再缺仍記 UNKNOWN、不計臂失敗、報告中註記為機制訊號")
        else:
            if x == "M":
                e["second_agent"] = ev
            over = e["cost_over_2x_A"]
            if sig and x_only > a_only:
                if over is True:
                    e.update(state="EFFECTIVE_BUT_EXPENSIVE", reason="顯著但成本 > 2×A ⇒ 有效但昂貴")
                elif over is None:
                    a_missing = (not cost["A_base"]["calls_per_success"] and not cost["A_base"]["tokens_per_success"])
                    d_arm = per_arm.get(x) if isinstance(per_arm.get(x), dict) else {}
                    aud_arm_d = aud_arm.get(x) if isinstance(aud_arm, dict) else None
                    x_calls = num(d_arm.get("calls_per_success")) or (num(aud_arm_d.get("calls_per_success")) if isinstance(aud_arm_d, dict) else None)
                    x_tok = num(d_arm.get("tokens_per_success")) or (num(aud_arm_d.get("tokens_per_success")) if isinstance(aud_arm_d, dict) else None)
                    x_missing = (not x_calls and not x_tok)
                    if a_missing and x_missing:
                        who = f"A 臂與 {x} 臂成本缺失"
                    elif a_missing:
                        who = "A 臂成本缺失"
                    elif x_missing:
                        who = f"{x} 臂成本缺失"
                    else:
                        who = "成本維度不全"
                    e.update(state="CONFIRMED_COST_UNKNOWN", reason=f"顯著且方向為正，但成本紅線量不到（{who}）")
                else:
                    e.update(state="CONFIRMED", reason="Holm 後顯著、X_only > A_only、成本 ≤ 2×A")
            else:
                e.update(state="NOT_ESTABLISHED", reason="不顯著（或方向非正）⇒ 未建立（不是負結果）")
        if x == "S":
            e["note"] = "利害 (a) 只是講、無真實後果；未建立 ≠「利害提示無用」（禁止這樣寫）"
        hyp[HYP[x]] = e
    for x in ARMS:  # 成本紅線：>2×A 且未顯著提升 ⇒ 不划算（成本必須與結果一起報告）
        h = hyp[HYP[x]]
        if h["p_raw"] is None:
            improved = None
        elif h["A_only"] is None or h["X_only"] is None:
            improved = False if not h["significant_at_alpha"] else None
        else:
            improved = h["significant_at_alpha"] and h["X_only"] > h["A_only"]
        o = cost["arms"][x]["over_2x_A_cost"]
        if o is None or (o is True and improved is None):
            cost["arms"][x]["not_worth_it"] = None
        else:
            cost["arms"][x]["not_worth_it"] = bool(o) and not improved
    return {"schema": "vacant.e006_verdict/1", "alpha": alpha, "m_in_holm_set": len(order), "holm_impl": impl,
            "cost_redline_2xA": cost, "hypotheses": hyp,
            "notes": ["不顯著 ⇒ 未建立（不是負結果）；顯著但成本 > 2×A ⇒「有效但昂貴」",
                      "M 臂審查者呼叫在獨立 agent 行程、不在 cell 的 events.jsonl ⇒ M 成本指標是下界",
                      "M 臂條款（承接 e005）：第二 agent 證據仍缺 ⇒ 再記 UNKNOWN、不計臂失敗、報告中註記為機制訊號",
                      "C 臂為 bf1a9f1a 版本行為；模型為 gemma-4-12b 本地量化（H-12 類邊界）：結果不外推到別的模型/預算/任務庫",
                      "labd 串行 + PAR=2：e002 同結構 170 格實際 wall ≈ 10h，本盤估同量級"]}


def render_text(r):
    L = [f"e006_verdict m={r['m_in_holm_set']} alpha={r['alpha']} holm={r['holm_impl']}"]
    for name, h in r["hypotheses"].items():
        L.append(f"{name:<13} arm={h['arm']} state={h['state']} p_raw={h['p_raw']} p_holm={h['p_holm']} "
                 f"A_only={h['A_only']} X_only={h['X_only']} cost_over_2x_A={h['cost_over_2x_A']}")
        if h.get("reason"):
            L.append(f"  reason: {h['reason']}")
        if h.get("note"):
            L.append(f"  note: {h['note']}")
    b = r["cost_redline_2xA"]["A_base"]
    L.append("cost(2×A 紅線): " + " | ".join(
        f"{x}: calls={d['calls_vs_A']} tokens={d['tokens_vs_A']} over={d['over_2x_A_cost']} not_worth_it={d['not_worth_it']}"
        for x, d in r["cost_redline_2xA"]["arms"].items()) + f"  [A base calls={b['calls_per_success']} tokens={b['tokens_per_success']}]")
    L += [f"note: {n}" for n in r["notes"]]
    return "\n".join(L)


def _mock_report():
    return {"exp": "mock_e006",
            "per_arm": {"A": {"n": 20, "pass": 10, "calls_per_success": 10.0, "tokens_per_success": 1000.0},
                        "C": {"n": 20, "pass": 14, "calls_per_success": 9.0, "tokens_per_success": 900.0},
                        "H": {"n": 20, "pass": 8, "calls_per_success": 25.0, "tokens_per_success": 1000.0},
                        "M": {"n": 20, "pass": 15, "calls_per_success": 9.0, "tokens_per_success": 900.0},
                        "S": {"n": 20, "pass": 11, "calls_per_success": 9.0, "tokens_per_success": 900.0}},
            "paired": {"A_vs_C": {"pairs": 20, "A_only": 2, "C_only": 8, "mcnemar_p_two_sided": 0.01},
                       "A_vs_H": {"pairs": 20, "A_only": 8, "H_only": 3, "mcnemar_p_two_sided": 0.20},
                       "A_vs_M": {"pairs": 20, "A_only": 1, "M_only": 9, "mcnemar_p_two_sided": 0.008},
                       "A_vs_S": {"pairs": 20, "A_only": 5, "S_only": 6, "mcnemar_p_two_sided": 0.40}}}


def _mock_audit(verified):
    return {"summary": {"per_arm": {"M": {"cells": 20, "second_agent_verified_cells": verified,
                                         "second_agent_unknown_cells": 20 - verified}}}}


def selftest():
    r = evaluate_hypotheses(_mock_report(), _mock_audit(0))
    h = r["hypotheses"]
    # 1) Holm 順序：raw 0.008/0.01/0.2/0.4 (m=4) → adj M=C=0.032 ≤ H=S=0.4，且各自 ≥ raw
    assert abs(h["H-acc"]["p_holm"] - 0.032) < 1e-9 and abs(h["H-review(M)"]["p_holm"] - 0.032) < 1e-9
    assert abs(h["H-review(H)"]["p_holm"] - 0.4) < 1e-9 and abs(h["H-stakes(a)"]["p_holm"] - 0.4) < 1e-9
    for x in ARMS:
        e = h[HYP[x]]
        assert e["p_holm"] >= e["p_raw"] - 1e-12
    # 2) 成本紅線：C/M/S ≤ 2×A → False；H calls 25 > 20 → True 且未顯著 ⇒ not_worth_it
    c = r["cost_redline_2xA"]["arms"]
    assert c["C"]["over_2x_A_cost"] is False and c["M"]["over_2x_A_cost"] is False and c["S"]["over_2x_A_cost"] is False
    assert c["H"]["over_2x_A_cost"] is True and c["H"]["not_worth_it"] is True
    # 3) 判定態：C CONFIRMED；H 未建立；M 無第二 agent 證據 ⇒ UNKNOWN；S 未建立（禁止寫「無用」）
    assert h["H-acc"]["state"] == "CONFIRMED" and h["H-review(H)"]["state"] == "NOT_ESTABLISHED"
    assert h["H-review(M)"]["state"] == "UNKNOWN" and h["H-review(M)"]["second_agent"]["evidence_present"] is False
    assert h["H-stakes(a)"]["state"] == "NOT_ESTABLISHED" and "無用" in h["H-stakes(a)"]["note"]
    # 4) M 臂證據在 ⇒ 同 p 值改走正常判定（CONFIRMED）
    r2 = evaluate_hypotheses(_mock_report(), _mock_audit(5))
    assert r2["hypotheses"]["H-review(M)"]["state"] == "CONFIRMED"
    # 5) 缺配對 ⇒ UNKNOWN 且 Holm 集 m=3；A 臂成本缺失 ⇒ 顯著也只得 CONFIRMED_COST_UNKNOWN
    rep3 = _mock_report()
    rep3["per_arm"]["A"]["calls_per_success"] = None
    del rep3["paired"]["A_vs_S"]
    r3 = evaluate_hypotheses(rep3, _mock_audit(5))
    assert r3["m_in_holm_set"] == 3 and r3["hypotheses"]["H-stakes(a)"]["state"] == "UNKNOWN"
    assert r3["hypotheses"]["H-acc"]["state"] == "CONFIRMED_COST_UNKNOWN"
    assert r3["cost_redline_2xA"]["arms"]["C"]["over_2x_A_cost"] is None
    # 6) audit 完全缺失 ⇒ M 降級 UNKNOWN（量不到，不是沒有）
    assert evaluate_hypotheses(_mock_report(), None)["hypotheses"]["H-review(M)"]["state"] == "UNKNOWN"
    # 7) e006 schema 與 M 臂 UNKNOWN reason 帶 e005 承接註記（機制訊號）
    assert r["schema"] == "vacant.e006_verdict/1"
    assert "機制訊號" in h["H-review(M)"]["reason"] and "e005" in h["H-review(M)"]["reason"]
    print("e006_verdict selftest PASS")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="e006 預註冊假說判定量具（唯讀）")
    ap.add_argument("exp", nargs="?", default=None)
    ap.add_argument("--runs-dir", default="/srv/vlab/runs")
    ap.add_argument("--report", default=None)
    ap.add_argument("--audit", default=None)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    runs = Path(a.runs_dir)
    rpath = Path(a.report) if a.report else (runs / a.exp / "REPORT.json" if a.exp else None)
    if rpath is None:
        ap.error("需要 exp 位置參數或 --report")
    if not rpath.is_file():
        print(f"無事可做：{rpath} 不存在（實驗未完賽或路徑錯）", file=sys.stderr)
        return 1
    try:
        report_data = json.loads(rpath.read_text())
        evaluate_hypotheses(report_data, None, alpha=a.alpha)  # 格式先驗，避免半路 SystemExit
    except ValueError as e:
        print(f"REPORT.json 格式不符：{e}", file=sys.stderr)
        return 2
    audit_summary = None
    apath = Path(a.audit) if a.audit else runs / (a.exp or "") / "AUDIT.json"
    if apath.is_file():
        try:
            audit_summary = json.loads(apath.read_text())
        except Exception:
            audit_summary = None
    r = evaluate_hypotheses(report_data, audit_summary, alpha=a.alpha)
    r["exp"] = a.exp or rpath.parent.name
    r["report"] = str(rpath)
    r["audit"] = str(apath) if audit_summary is not None else None
    payload = json.dumps(r, ensure_ascii=False, indent=2)
    print(payload if a.json else render_text(r))
    if a.out:
        op = Path(a.out)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(payload + "\n")
        print(f"# wrote {op}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
