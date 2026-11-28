#!/usr/bin/env python3
"""實驗 T：agent 越界讀取的逐筆掃描＋排除越界格的敏感度（2026-11-28，判讀之後才發現；**非預註冊**）。

探索批次的 9B agent 沒有檔案沙箱。對每一次 agent 執行（c0 與各臂每一輪）的工具呼叫（參數），找出指到工作區外的路徑，分類：
  mat_cycle0       私有教材目錄的 cycle_0 頁面（內容和伺服器給的凍結頁一樣，但繞過 egress 紀錄）
  mat_future       教材目錄的 cycle_1 以上（未來版本，值可能不同）
  mat_answer       教材目錄的 manifest／SOURCES（答案）
  pair_site        同一對 c0 的 site_frozen（凍結頁；繞過 egress 紀錄）
  pair_flags       同一對 c0 的 flags.json（紀錄算出的標記）
  pair_other       同一對其他臂的檔（例如別臂的輸出）
  other_site／other_flags／other_cell  別組／別次的同類檔
路徑一律去識別（只留 組／次／臂／類別）。
敏感度：用 `expT_metrics.score_cell`＋`paired_comparison`（和預註冊同一份評分、同一個 bootstrap），兩個版本：
  (a) 整對排除：這一對（組、次）任何一臂任何一輪有越界；
  (b) 只排除讀到 flags.json（pair_flags／other_flags）或未來版本頁面（mat_future）或答案（mat_answer）的對。
用法：expT_escape.py <root> --out-dir DIR
"""
from __future__ import annotations
import argparse, collections, json, os, pathlib, re, sys
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "ops" / "d2"))
import scan_leak as S  # noqa: E402
from ops.d2 import expT_metrics as M  # noqa: E402

def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("root"); ap.add_argument("--out-dir", required=True)
    a = ap.parse_args(); root = pathlib.Path(a.root).resolve(); out = pathlib.Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    d2 = str(root.parent)
    pm = re.compile(re.escape(d2) + r"/(realrev\w*?)/sets/(s\d+)/(cycle_(\d)|manifest[\w.]*|SOURCES[\w.]*|template\.md)")
    pc = re.compile(re.escape(str(root)) + r"/cells/([\w-]+)/(r\d)/([\w]+)/?([\w.\-]*)")
    recs = []
    for log in sorted((root / "cells").glob("*/r*/*/**/agent.log")):
        rel = log.relative_to(root / "cells").parts
        sid, rep, arm = rel[0], int(rel[1][1:]), rel[2]
        rnd = rel[3] if rel[3].startswith("round_") else "c0"
        for tn, args, res in S.calls(log):
            err = ('"isError": true' in res) or ("No such file" in res)
            for m in pm.finditer(args):
                g = m.group(3)
                kind = ("mat_cycle0" if m.group(4) == "0" else "mat_future") if m.group(4) is not None else ("mat_template" if g == "template.md" else "mat_answer")
                recs.append({"set": sid, "rep": rep, "arm": arm, "round": rnd, "tool": tn, "kind": kind, "detail": f"{m.group(1)}/{m.group(2)}/{g}", "tool_error": err})
            for m in pc.finditer(args):
                tsid, trep, tarm, sub = m.group(1), int(m.group(2)[1:]), m.group(3), m.group(4)
                same = (tsid, trep) == (sid, rep)
                if same and tarm == arm:
                    continue
                what = "site" if sub == "site_frozen" else ("flags" if sub == "flags.json" else "cell")
                kind = ("pair_" if same else "other_") + ("other" if (same and what == "cell") else what)
                recs.append({"set": sid, "rep": rep, "arm": arm, "round": rnd, "tool": tn, "kind": kind,
                             "detail": f"{tsid}/r{trep}/{tarm}/{sub}", "tool_error": err})
    with open(out / "expT_escape_calls.jsonl", "w") as f:
        for r in recs: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    runs = collections.defaultdict(set)
    for r in recs: runs[(r["set"], r["rep"], r["arm"], r["round"])].add(r["kind"])
    summ = {"calls": len(recs), "agent_runs_with_escape": len(runs),
            "agent_runs_total": sum(1 for _ in (root / "cells").glob("*/r*/*/**/agent.log")),
            "by_kind_calls": dict(collections.Counter(r["kind"] for r in recs)),
            "runs_by_arm": dict(collections.Counter(k[2] for k in runs)),
            "c0_runs_with_escape": sum(1 for k in runs if k[3] == "c0")}
    strong = {"pair_flags", "other_flags", "mat_future", "mat_answer"}
    pairs_any = {(k[0], k[1]) for k in runs}
    pairs_strong = {(k[0], k[1]) for k, v in runs.items() if v & strong}
    summ["pairs_excluded_a_any"] = len(pairs_any); summ["pairs_excluded_b_flags_future"] = len(pairs_strong)
    summ["pairs_excluded_by_arm_a"] = dict(collections.Counter(k[2] for k in runs))
    summ["pairs_excluded_by_arm_b"] = dict(collections.Counter(k[2] for k, v in runs.items() if v & strong))
    # rescore
    run = json.loads((root / "RUN.json").read_text()); plan = run["plan_body"]; truth = M.load_manifests_with_truth(plan)
    reps = int(plan.get("reps") or 2); arms = list(plan["arms"]); by_key = {}
    for sid, st in truth.items():
        for rep in range(1, reps + 1):
            rd = root / "cells" / sid / f"r{rep}"; c0 = (rd / "c0" / "report.md").read_text(errors="replace")
            for arm in arms:
                cd = json.loads((rd / arm / "cell.json").read_text())
                by_key[(sid, rep, arm)] = M.score_cell(cd, c0, (rd / arm / "report.md").read_text(errors="replace"), st, chain_path=None, verify_chain=False)
    sets = list(truth)
    def comps(excl):
        bk = {k: v for k, v in by_key.items() if (k[0], k[1]) not in excl}
        res = {}
        for t, c in (("T", "G"), ("T", "TB"), ("T", "TO"), ("TE", "TER"), ("T", "A"), ("G", "A"), ("TB", "A"), ("TO", "A")):
            pc_ = M.paired_comparison(bk, sets, reps, treatment=t, control=c)
            res[f"{t}_vs_{c}"] = {k: pc_[k] for k in pc_ if not isinstance(pc_[k], dict) and not (isinstance(pc_[k], list) and len(pc_[k]) > 2)}
        return res
    sens = {"all": comps(set()), "a_exclude_any_escape_pairs": comps(pairs_any), "b_exclude_flags_future_pairs": comps(pairs_strong)}
    (out / "expT_escape_summary.json").write_text(json.dumps({"summary": summ, "excluded_pairs_a": sorted(map(list, pairs_any)),
                                                             "excluded_pairs_b": sorted(map(list, pairs_strong)), "sensitivity": sens}, ensure_ascii=False, indent=1))
    print(json.dumps(summ, ensure_ascii=False))
    for v, r in sens.items():
        print(v, {k: (r[k]["paired_cells"], r[k]["per_set_correct_prop_diff"], r[k]["per_set_correct_prop_diff_ci95"]) for k in r})

if __name__ == "__main__":
    main()
