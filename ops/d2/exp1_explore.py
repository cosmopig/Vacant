#!/usr/bin/env python3
"""實驗一探索性資料：對每個已跑完的批次跑 exp1_flags.py（只描述，已看過彙總結果）。
結果寫到 ~/dev/ops/d2_results/<名>/exp1_flags.json。私有 root 用環境變數 D2_PRIVATE。
用法：D2_PRIVATE=... exp1_explore.py [名字…]"""
import json
import os
import pathlib
import subprocess
import sys

HOME = pathlib.Path.home()
RUNS, RES = HOME / "dev/ops/d2_runs", HOME / "dev/ops/d2_results"
PRIV = pathlib.Path(os.environ["D2_PRIVATE"])
BATCHES = {   # 結果名 → run root
    "main_qwen9b_1003": RUNS / "main_qwen9b_1003", "main_haiku": RUNS / "main_haiku", "heldout_qwen9b": RUNS / "heldout_qwen9b",
    "r1_12b_merged": RUNS / "r1_12b_merged", "r2main_qwen9b_1003": RUNS / "r2main_qwen9b_1003", "r2main_haiku": RUNS / "r2main_haiku",
    "r2heldout_qwen9b_1004": RUNS / "r2heldout_qwen9b_1004", "r2heldoutb_qwen9b_1003": RUNS / "r2heldoutb_qwen9b_1003",
    "r2_12b_merged": RUNS / "r2_12b_merged", "r3_merged": RUNS / "r3_merged", "r3haiku": RUNS / "r3haiku",
    "r3h3": PRIV / "r3h3", "r4_merged": PRIV / "r4_merged", "r4haiku": PRIV / "r4haiku", "r4h3seen": PRIV / "r4h3seen",
    "r5h3b": PRIV / "r5h3b", "r5seen4b": PRIV / "r5seen4b", "r5real_haiku": PRIV / "r5real_haiku", "r5real_merged": PRIV / "r5real_merged",
}
ARMS = ["a", "b", "b2", "d", "d2", "d_diff", "d_diff_real"]
names = sys.argv[1:] or list(BATCHES)
for nm in names:
    root = BATCHES[nm]
    out = RES / nm / "exp1_flags.json"
    if not (root / "RUN.json").exists() or not (RES / nm / "score.json").exists():
        print(nm, "skip (no RUN.json or score.json)")
        continue
    plan = json.loads((root / "RUN.json").read_text())["plan_body"]
    if isinstance(plan, str):
        plan = json.loads(plan)
    mat = os.path.expandvars(os.path.expanduser(plan["materials"]["dir"]))
    s1 = next(iter(sorted((root / "cells").glob("s*"))))
    arms = [a for a in ARMS if (s1 / a / "final").exists()]
    r = subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name("exp1_flags.py")), "--root", str(root), "--materials", mat,
                        "--score", str(RES / nm / "score.json"), "--arms", ",".join(arms), "--out", str(out)],
                       capture_output=True, text=True)
    if r.returncode:
        print(nm, "ERROR", r.stderr[-400:])
        continue
    o = json.loads(out.read_text())["overall"]
    print(nm, arms, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in o.items() if k in ("units", "flagged_share", "errors", "recall", "recall_lower95", "rate_ratio")}, flush=True)
