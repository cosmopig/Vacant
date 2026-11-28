#!/usr/bin/env python3
"""實驗 T 確認批次：用紀錄挑初稿（事前登記的比較；2026-11-28 在任何確認批次模型呼叫之前凍結）。

每組有 K 份初稿（同一份計畫、rep 1..K 的 c0）。四種挑法，每組各挑一份：
  (i)   record：紀錄分數最高。分數＝`expT_metrics.collect_offline_drafts` 的 evidence_score
        ＝supported_count − flagged_count（flagged 含空白行），同分取空白較少，再同分取 rep 編號最小。
        —— 和探索批次次要分析（`expT_metrics.analyze_draft_selection`）逐字同一個定義。
  (ii)  nonblank：只數非空白行最多（n_claims − blank_count；不需要紀錄），同分取 rep 編號最小。
  (iii) random：K 份的平均（期望值）。
  (iv)  oracle：答案鍵挑最好的（上限）。
主要比較（以組為群集的 bootstrap，2,000 次，種子 20261128）：
  (i)−(iii)：正確行比例差 ≥5pp 且區間下界 >0；
  (i)−(ii)：≥3pp 且區間下界 >0，才算「紀錄比數空白多帶來東西」。
另報：各挑法的已填行精確度、(i) 離 (iv) 多遠。
用法：expTc_select.py <root> [--k K] [--json OUT]
"""
from __future__ import annotations
import argparse, json, pathlib, random, sys
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from ops.d2 import expT_metrics as M  # noqa: E402
SD = M.SD

def boot_ci(vals, n_boot=2000, seed=20261128):
    rng = random.Random(seed); n = len(vals); bs = []
    for _ in range(n_boot):
        s = [vals[rng.randrange(n)] for _ in range(n)]; bs.append(sum(s) / n)
    bs.sort(); return [round(bs[int(0.025 * n_boot)], 4), round(bs[int(0.975 * n_boot) - 1], 4)]

def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("root"); ap.add_argument("--k", type=int); ap.add_argument("--json")
    a = ap.parse_args(); root = pathlib.Path(a.root)
    plan = json.loads((root / "RUN.json").read_text())["plan_body"]; truth = M.load_manifests_with_truth(plan)
    reps = a.k or int(plan.get("reps") or 2)
    drafts = M.collect_offline_drafts(root, truth, list(truth), reps)
    rows = []; d_rr = []; d_rn = []; d_ro = []
    for sid in sorted(drafts):
        ds = sorted(drafts[sid], key=lambda d: d["rep"])
        if len(ds) < reps:
            continue  # 預註冊：K 份不齊的組不進主要比較（另列）
        claims = truth[sid]["claims"]; tr = truth[sid]["truth"]
        for d in ds:
            vals = SD.parse_report((root / "cells" / sid / f"r{d['rep']}" / "c0" / "report.md").read_text(errors="replace"), claims)
            filled = [c for c in claims if vals.get(c["id"]) is not None]
            d["filled"] = len(filled)
            d["filled_correct"] = sum(1 for c in filled if M.strict_status(vals.get(c["id"]), c["id"], tr, 0) == "correct")
        rec = max(ds, key=lambda d: (int(d["evidence_score"]), -int(d["blank_count"])))   # 同 analyze_draft_selection；max 取第一個＝rep 最小
        nb = max(ds, key=lambda d: int(d["n_claims"]) - int(d["blank_count"]))
        ora = max(ds, key=lambda d: float(d["correct_prop"]))
        rnd = sum(float(d["correct_prop"]) for d in ds) / len(ds)
        fp = lambda d: (d["filled_correct"] / d["filled"]) if d["filled"] else None
        rows.append({"set": sid, "k": len(ds), "record_rep": rec["rep"], "nonblank_rep": nb["rep"], "oracle_rep": ora["rep"],
                     "record": rec["correct_prop"], "nonblank": nb["correct_prop"], "random": rnd, "oracle": ora["correct_prop"],
                     "record_fprec": fp(rec), "nonblank_fprec": fp(nb),
                     "random_fprec": (sum(x["filled_correct"] for x in ds) / sum(x["filled"] for x in ds)) if sum(x["filled"] for x in ds) else None,
                     "oracle_fprec": fp(ora), "same_pick_record_nonblank": rec["rep"] == nb["rep"]})
        d_rr.append(rec["correct_prop"] - rnd); d_rn.append(rec["correct_prop"] - nb["correct_prop"]); d_ro.append(rec["correct_prop"] - ora["correct_prop"])
    n = len(rows); mean = lambda k: round(sum(r[k] for r in rows) / n, 4)
    mfp = lambda k: round(sum(r[k] for r in rows if r[k] is not None) / max(1, sum(1 for r in rows if r[k] is not None)), 4)
    out = {"k": reps, "sets": n, "record": mean("record"), "nonblank": mean("nonblank"), "random": mean("random"), "oracle": mean("oracle"),
           "fprec": {k: mfp(k + "_fprec") for k in ("record", "nonblank", "random", "oracle")},
           "record_minus_random": round(sum(d_rr) / n, 4), "record_minus_random_ci95": boot_ci(d_rr),
           "record_minus_nonblank": round(sum(d_rn) / n, 4), "record_minus_nonblank_ci95": boot_ci(d_rn, seed=20261129),
           "record_minus_oracle": round(sum(d_ro) / n, 4), "same_pick_record_nonblank": sum(r["same_pick_record_nonblank"] for r in rows)}
    rr_lo = out["record_minus_random_ci95"][0]; rn_lo = out["record_minus_nonblank_ci95"][0]
    out["readout"] = {
        "record_vs_random": "record_beats_random" if out["record_minus_random"] >= 0.05 and rr_lo > 0 else "no_evidence_record_beats_random",
        "record_vs_nonblank": "record_adds_over_nonblank" if out["record_minus_nonblank"] >= 0.03 and rn_lo > 0 else "no_evidence_record_adds_over_nonblank"}
    out["per_set"] = rows
    print(json.dumps({k: v for k, v in out.items() if k != "per_set"}, ensure_ascii=False))
    if a.json: pathlib.Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
