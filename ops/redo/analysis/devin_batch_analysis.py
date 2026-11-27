#!/usr/bin/env python3
"""Devin 版（雲端修正 C6）：逐字沿用 Haiku 版的凍結分析，另加用量缺的計數、呼叫數、不可分辨條件判定。
Original: Frozen analysis for the Haiku x cchard four-arm batch (decisions/..._HARDPOOL.md appendix 2).

1. serial re-score of every delivered workspace's hidden half (one at a time) -> official score (cached in OUT/serial_rescore.jsonl)
2. per-arm metrics, paired (task, rep) differences with exact sign (McNemar) tests, post-hoc subset where arm A failed >= once
3. controller rule table, signed C-arm chain verification, time-limit-only visible failures

Usage: cchard_batch_analysis.py --root R --bank B --out OUTDIR [--skip-rescore]
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import statistics
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2]))
import ctl_metrics as M  # noqa: E402
from vacant_network.research import mcnemar_exact  # noqa: E402

ARMS = ["A", "R", "B", "C"]


def rescore(root: pathlib.Path, bank: pathlib.Path, cells: list, out: pathlib.Path) -> dict:
    cache = {}
    f = out / "serial_rescore.jsonl"
    if f.is_file():
        for ln in f.read_text().splitlines():
            r = json.loads(ln)
            cache[r["cell"]] = r
    with open(f, "a") as fh:
        for c in cells:
            if c.get("infra_void") or not c.get("delivered_attempt") or c["cell"] in cache:
                continue
            ws = root / "cells" / c["task"] / f"r{c['rep']}" / c["arm"] / f"attempt_{c['delivered_attempt']}" / "workspace"
            sp = subprocess.run([sys.executable, str(bank / c["task"] / "scorer.py"), str(bank / c["task"] / "hidden"), str(ws)],
                                capture_output=True, text=True, timeout=900)
            sc = json.loads(sp.stdout.strip().splitlines()[-1])
            r = {"cell": c["cell"], "serial_pass": bool(sc["pass"]), "tests_passed": sc["tests_passed"], "tests_total": sc["tests_total"],
                 "status": sc.get("status"), "batch_pass": bool(c.get("pass"))}
            cache[c["cell"]] = r
            fh.write(json.dumps(r) + "\n")
            fh.flush()
    return cache


def paired(cells_by: dict, ctl: str, trt: str, score: dict) -> dict:
    b = c = both = neither = 0
    keys = sorted({(t, r) for (t, r, a) in cells_by if a in (ctl, trt)})
    n = 0
    for t, r in keys:
        x, y = cells_by.get((t, r, ctl)), cells_by.get((t, r, trt))
        if not x or not y or x.get("infra_void") or y.get("infra_void"):
            continue
        n += 1
        px, py = score[x["cell"]]["serial_pass"], score[y["cell"]]["serial_pass"]
        if px and py:
            both += 1
        elif px:
            b += 1          # only control passes
        elif py:
            c += 1          # only treatment passes
        else:
            neither += 1
    return {"control": ctl, "treatment": trt, "pairs": n, "both_pass": both, "only_control": b, "only_treatment": c,
            "neither": neither, "diff_pp": round(100 * (c - b) / n, 2) if n else None, "p_exact": mcnemar_exact(b, c)}


def arm_table(cells: list, score: dict, tasks: set | None) -> dict:
    out = {}
    for arm in ARMS:
        cs = [c for c in cells if c["arm"] == arm and not c.get("infra_void") and (tasks is None or c["task"] in tasks)]
        ok = [c for c in cs if score.get(c["cell"], {}).get("serial_pass")]
        fr = [score[c["cell"]]["tests_passed"] / max(1, score[c["cell"]]["tests_total"]) for c in cs if c["cell"] in score]
        tok = [M._cell_tokens(c) for c in cs]
        cost = [0 for c in cs]            # 免費模型：沒有費用欄位
        miss = sum(1 for c in cs for a in c["attempts"] if (a.get("usage") or {}).get("usage_missing") or not a.get("usage"))
        calls = sum(((a.get("usage") or {}).get("calls") or 0) for c in cs for a in c["attempts"])
        natt = sum(len(c["attempts"]) for c in cs)
        brk = [M._cell_broken_after_pass(c) for c in cs]
        out[arm] = {
            "cells": len(cs), "success": len(ok), "rate": round(len(ok) / len(cs), 4) if cs else None,
            "mean_hidden_fraction": round(statistics.mean(fr), 4) if fr else None,
            "tokens_total": sum(t for t in tok if t), "tokens_per_success": round(sum(t for t in tok if t) / len(ok)) if ok else None,
            "cost_usd_total": None, "cost_per_success": None, "attempts_total": natt, "attempts_usage_missing": miss, "model_calls_recorded": calls,
            "broken_after_pass": f"{sum(b for b, _ in brk)}/{sum(e for _, e in brk)}",
            "mean_attempts": round(statistics.mean(c["n_attempts"] for c in cs), 3) if cs else None,
            "wall_mean_s": round(statistics.mean(c["wall_s"] for c in cs), 1) if cs else None,
            "wall_median_s": round(statistics.median(c["wall_s"] for c in cs), 1) if cs else None,
            "wall_max_s": max((c["wall_s"] for c in cs), default=None),
            "n_changed_serial_vs_batch": sum(1 for c in cs if c["cell"] in score and score[c["cell"]]["serial_pass"] != score[c["cell"]]["batch_pass"]),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--bank", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    root, bank, out = pathlib.Path(a.root), pathlib.Path(a.bank), pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    run, cells = M._load_cell_details(root)
    score = rescore(root, bank, cells, out)
    by = {(c["task"], c["rep"], c["arm"]): c for c in cells}
    res: dict = {"cells": len(cells), "infra_void": [c["cell"] for c in cells if c.get("infra_void")]}
    res["per_arm"] = arm_table(cells, score, None)
    res["pairs"] = [paired(by, x, y, score) for x, y in (("B", "C"), ("R", "C"), ("A", "R"), ("A", "B"), ("A", "C"))]
    a_fail = {t for (t, r, arm), c in by.items() if arm == "A" and not c.get("infra_void") and not score[c["cell"]]["serial_pass"]}
    res["posthoc_tasks_A_failed_at_least_once"] = sorted(a_fail)
    res["posthoc_per_arm"] = arm_table(cells, score, a_fail)
    sub = {k: v for k, v in by.items() if k[0] in a_fail}
    res["posthoc_pairs"] = [paired(sub, x, y, score) for x, y in (("B", "C"), ("R", "C"), ("A", "R"), ("A", "B"), ("A", "C"))]
    # controller rules
    rules, actions = collections.Counter(), collections.Counter()
    chains = {"verified": 0, "failed": [], "decisions": 0}
    from vacant_network import controller as ctl
    for c in cells:
        if c["arm"] != "C" or c.get("infra_void"):
            continue
        for at in c["attempts"]:
            rules[f"rule{at.get('rule')}:{at.get('action')}"] += 1
            actions[at.get("action")] += 1
        cp = root / "cells" / c["task"] / f"r{c['rep']}" / "C" / "controller_chain.ndjson"
        try:
            dec = ctl.reconstruct(cp, emit=False)
            chains["verified"] += 1
            chains["decisions"] += len(dec)
            if len(dec) != len(c["attempts"]):
                chains["failed"].append((c["cell"], f"decisions {len(dec)} != attempts {len(c['attempts'])}"))
        except Exception as e:  # noqa: BLE001
            chains["failed"].append((c["cell"], repr(e)[:120]))
    res["controller_rules_fired"] = dict(rules)
    res["chains"] = chains
    # visible failures that were only time limits (any arm, any attempt)
    tl_only = []
    for c in cells:
        for k, af in enumerate(c.get("_attempt_files") or [], 1):
            acc = af.get("acc") or {}
            fp = acc.get("first_problem") or ""
            fails = acc.get("failing_tests") or []
            if fails and not acc.get("accept") and "time limit exceeded" in fp and all(t for t in fails):
                # only time limits if every failing test is a TLE: approximate via the harness text of first problem + no other kinds
                if "wrong answer" not in fp and "runtime error" not in fp and "compile error" not in fp:
                    tl_only.append({"cell": c["cell"], "attempt": k, "failing": len(fails)})
    res["attempts_visible_failures_time_limit_only_approx"] = tl_only
    res["cells_changed_serial_vs_batch"] = [(k, v["batch_pass"], v["serial_pass"]) for k, v in score.items() if v["batch_pass"] != v["serial_pass"]]
    (out / "ANALYSIS.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    L = ["# cchard16 四臂批次（Devin swe-2-flash-medium）：凍結分析（序列重評分為正式分數；探索性）", ""]

    def tab(t):
        r = ["| 臂 | 格 | 成功 | 成功率 | hidden 比例均值 | token/成功 | 嘗試數（用量缺） | 弄壞比 | 平均嘗試 | 牆鐘均值 s | 序列≠批次內 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for arm in ARMS:
            x = t[arm]
            r.append(f"| {arm} | {x['cells']} | {x['success']} | {x['rate']} | {x['mean_hidden_fraction']} | {x['tokens_per_success']} | {x['attempts_total']}（{x['attempts_usage_missing']}） | {x['broken_after_pass']} | {x['mean_attempts']} | {x['wall_mean_s']} | {x['n_changed_serial_vs_batch']} |")
        return r

    def ptab(p):
        r = ["| 對照→處理 | 對數 | 都過 | 只對照過 | 只處理過 | 都沒過 | 差 pp | 精確 p |", "|---|---|---|---|---|---|---|---|"]
        for x in p:
            r.append(f"| {x['control']}→{x['treatment']} | {x['pairs']} | {x['both_pass']} | {x['only_control']} | {x['only_treatment']} | {x['neither']} | {x['diff_pp']} | {x['p_exact']:.3f} |")
        return r

    L += tab(res["per_arm"]) + [""] + ptab(res["pairs"]) + ["", f"## post-hoc：A 臂至少失敗一次的題（{len(a_fail)} 題：{', '.join(sorted(a_fail))}）", ""]
    L += tab(res["posthoc_per_arm"]) + [""] + ptab(res["posthoc_pairs"])
    L += ["", "## 控制器規則觸發（每次嘗試）", "", json.dumps(res["controller_rules_fired"], ensure_ascii=False),
          "", f"C 臂決策鏈驗證：{chains['verified']} 條通過（共 {chains['decisions']} 個決策）；失敗 {len(chains['failed'])}：{chains['failed'][:5]}",
          "", f"序列重評分與批次內結果不同的格：{len(res['cells_changed_serial_vs_batch'])}：{res['cells_changed_serial_vs_batch'][:10]}",
          f"infra_void 格：{len(res['infra_void'])}",
          f"唯一可見失敗是逾時的嘗試（近似判斷）：{len(tl_only)}"]
    # 不可分辨條件（雲端修正 C6，先寫後算）
    rbc = [c for c in cells if c["arm"] in "RBC" and not c.get("infra_void")]
    past1 = sum(1 for c in rbc if c["n_attempts"] >= 2)
    fire36 = sum(v for k, v in rules.items() if k.split(":")[0] in ("rule3", "rule4", "rule5", "rule6"))
    a_rate = res["per_arm"]["A"]["rate"] or 0
    cond = {"a_rate_ge_75": a_rate >= 0.75, "past_attempt1_lt_quarter": (past1 / len(rbc) if rbc else 0) < 0.25,
            "rules3to6_lt_10": fire36 < 10}
    res["indistinguishable"] = {"conditions": cond, "A_rate": a_rate, "RBC_cells": len(rbc), "RBC_past_attempt1": past1,
                                "rules_3to6_fired": fire36, "verdict_indistinguishable": any(cond.values())}
    (out / "ANALYSIS.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    L += ["", "## 不可分辨條件（雲端修正 C6，任一成立＝無法分開四臂、不下方向結論）", "", json.dumps(res["indistinguishable"], ensure_ascii=False)]
    (out / "ANALYSIS.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
