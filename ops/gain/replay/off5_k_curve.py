#!/usr/bin/env python3
"""離線重放：OFF5 的 5 次呼叫，錢花在哪裡才有用？

零模型呼叫——只讀 `runs/<run>/calls.jsonl` 裡已經落盤的 5 個候選回應全文。
沙箱執行是本機的、免費（不算預算）；只做這件事：

  1. 對每個 task 的 5 個候選各跑一次 hidden_check（算分用，只准量測不准選）
     與一次 behavior_signature（OFF5 多數決真正吃的訊號，只看 visible/base）。
  2. 因為只有 5 個候選，k=1..5 的所有子集（C(5,k)=5,10,10,5,1）**窮舉**，
     不做蒙地卡羅抽樣——這比「抽很多次」更強：是精確期望值，不是估計值。
     子集內部，OFF5 真正的規則在「票數平手」與「同票桶內選哪個候選」都有
     一次 rng.choice；這裡同樣不抽樣一次，而是對平手桶、桶內成員做均勻加權
     平均，算出該子集的精確期望通過率。
  3. Oracle 上界：子集內只要有一個候選過 hidden_check 就算過——這是**明講的
     上界**，允許用 hidden_check 是因為它不是可出貨的機制，只是天花板。

輸出兩層：
  - 每個 run 各自的 k-curve（majority-vote 精確期望 vs oracle 精確期望）
  - 三個 run 併池的 k-curve，外加對 task 做 bootstrap（預設 5000 次）取
    majority@k 與 oracle@k 的 95% CI，用來判斷「在哪個 k 飽和」有沒有統計意義。

用法：
  # 第一步：建候選快取（本機沙箱執行，慢，見下方計時；輸出到 scratch，不寫 runs/）
  ops/gain/replay/off5_k_curve.py build --out <cache.json> [run ...]
  # 第二步：分析快取，印報告
  ops/gain/replay/off5_k_curve.py analyze <cache.json> [--resamples 5000]
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault(
    "VACANT_EVALPLUS_PATH", ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"
)

from ops.gain.gain_run import (  # noqa: E402
    behavior_signature, extract_code, load_tasks, meets_demand,
)
from ops.gain.brain_cline import InfraVoid  # noqa: E402

DEFAULT_RUNS = [
    "g_r441_gemma_only_mbpp_b",
    "g_r356_3arm_20260830",
    "g_onoff5_371_r123_20260825",
]

# ── 建快取：每個候選只跑一次 hidden_check + 一次 behavior_signature ──────
_TASKS: dict = {}


def _init(seed: str) -> None:
    global _TASKS
    os.chdir(ROOT)
    _TASKS = {t["task_id"]: t for t in load_tasks("evalplus", seed, 0)}


def _score_one(job):
    run, tid, idx, agent_id, code = job
    t = _TASKS.get(tid)
    if t is None:
        return {"run": run, "task_id": tid, "idx": idx, "agent_id": agent_id,
                "error": "task_not_in_bank"}
    ep = t.get("entry_point")
    rec = {"run": run, "task_id": tid, "idx": idx, "agent_id": agent_id}
    try:
        hidden_ok, _ = meets_demand(code, t["hidden_check"]["code"], entry_point=ep)
        rec["hidden_pass"] = bool(hidden_ok)
    except InfraVoid as e:
        rec["hidden_pass"] = None
        rec["error"] = f"hidden_infra_void:{e}"[:160]
    try:
        rec["sig"] = behavior_signature(code, t)
    except InfraVoid as e:
        rec["sig"] = None
        rec.setdefault("error", f"sig_infra_void:{e}"[:160])
    return rec


def _off5_candidates_for_run(run: str) -> tuple[str, list[tuple]]:
    """回傳 (seed, jobs)；jobs 只含『rows.jsonl 確實有 OFF5 列』的 task 的
    恰好 5 個成功（ok=True）gen 呼叫，依 calls.jsonl 的檔案順序（＝呼叫序）。

    這條篩選跟 arm_off5() 的真實語意對齊：InfraVoid 會讓整題不落 row，
    calls.jsonl 裡屬於該題的重試失敗（ok=False）不是「第 6 個候選」，只是
    重試雜訊；round441 這種完整 run 沒有任何重試，round356/onoff5_371 有——
    見本檔開發時的探測（True-count!=5 的 task 精確等於 rows.jsonl 缺席的 task）。
    """
    run_dir = ROOT / "runs" / run
    rows = [json.loads(l) for l in (run_dir / "rows.jsonl").read_text().splitlines() if l.strip()]
    off5_rows = [r for r in rows if r["arm"] == "OFF5"]
    if not off5_rows:
        return "", []
    seed = off5_rows[0]["seed"]
    off5_task_ids = {r["task_id"] for r in off5_rows}
    by_task: dict[str, list[tuple]] = {}
    for line in (run_dir / "calls.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        m = c.get("meta") or {}
        if c.get("role") != "gen" or m.get("arm") != "OFF5" or not c.get("ok"):
            continue
        tid = m.get("task_id")
        if tid not in off5_task_ids:
            continue
        code = extract_code(c.get("response") or "")
        by_task.setdefault(tid, []).append((c.get("agent_id"), code))
    jobs = []
    skipped = 0
    for tid, cands in by_task.items():
        if len(cands) != 5:
            skipped += 1
            continue
        for idx, (aid, code) in enumerate(cands):
            jobs.append((run, tid, idx, aid, code))
    print(f"  {run}: OFF5 rows={len(off5_rows)}  usable(5/5 candidates)={len(by_task) - skipped}"
          f"  skipped(!=5 successful calls, should be 0)={skipped}", flush=True)
    return seed, jobs


def cmd_build(args) -> None:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    all_results = []
    for run in args.runs:
        print(f"── {run}", flush=True)
        seed, jobs = _off5_candidates_for_run(run)
        if not jobs:
            print(f"  ⚠ no OFF5 candidates found, skipping")
            continue
        print(f"  {len(jobs)} candidate executions (={len(jobs)//5} tasks x 5)", flush=True)
        with ProcessPoolExecutor(max_workers=args.workers, initializer=_init,
                                  initargs=(seed,)) as ex:
            for i, r in enumerate(ex.map(_score_one, jobs, chunksize=4), 1):
                all_results.append(r)
                if i % 100 == 0:
                    print(f"    {i}/{len(jobs)}", flush=True)
        out.write_text(json.dumps(all_results))  # incremental checkpoint after each run
        print(f"  checkpointed -> {out} ({len(all_results)} total records so far)", flush=True)
    print(f"done -> {out} ({len(all_results)} records)")


# ── 分析：窮舉 C(5,k) 子集，算 majority-vote 與 oracle 的精確期望通過率 ──

def _subset_expectations(hidden: list[bool], sig: list[str], k: int):
    """回傳 (majority_vote 精確期望, oracle 精確期望)，對大小 k 的所有子集平均。"""
    idxs = range(len(hidden))
    maj_vals, orc_vals = [], []
    for S in itertools.combinations(idxs, k):
        orc_vals.append(1.0 if any(hidden[i] for i in S) else 0.0)
        buckets: dict[str, list[int]] = {}
        for i in S:
            buckets.setdefault(sig[i], []).append(i)
        max_votes = max(len(v) for v in buckets.values())
        tied = [v for v in buckets.values() if len(v) == max_votes]
        bucket_rates = [sum(hidden[i] for i in b) / len(b) for b in tied]
        maj_vals.append(sum(bucket_rates) / len(bucket_rates))
    return sum(maj_vals) / len(maj_vals), sum(orc_vals) / len(orc_vals)


def _load_cache(path: Path):
    records = json.loads(path.read_text())
    by_run_task: dict[tuple, dict[int, dict]] = {}
    for r in records:
        by_run_task.setdefault((r["run"], r["task_id"]), {})[r["idx"]] = r
    tasks = {}  # (run, task_id) -> (hidden[5], sig[5])
    dropped = 0
    for key, byidx in by_run_task.items():
        if len(byidx) != 5:
            dropped += 1
            continue
        ok = True
        hidden, sig = [], []
        for i in range(5):
            rec = byidx.get(i)
            if rec is None or rec.get("hidden_pass") is None or rec.get("sig") is None:
                ok = False
                break
            hidden.append(bool(rec["hidden_pass"]))
            sig.append(rec["sig"])
        if not ok:
            dropped += 1
            continue
        tasks[key] = (hidden, sig)
    return tasks, dropped


def cmd_analyze(args) -> None:
    tasks, dropped = _load_cache(Path(args.cache))
    print(f"loaded {len(tasks)} usable tasks (dropped {dropped} incomplete/void candidates)\n")

    # per-task curves, cached once (5 subsets sizes each)
    per_task_curve: dict[tuple, dict[int, tuple]] = {}
    for key, (hidden, sig) in tasks.items():
        per_task_curve[key] = {k: _subset_expectations(hidden, sig, k) for k in range(1, 6)}

    runs = sorted({key[0] for key in tasks})

    def report(keys: list[tuple], label: str):
        print(f"=== {label}  (n={len(keys)} tasks) ===")
        print(f"{'k':>2}  {'majority-vote':>14}  {'oracle':>8}  {'gap(headroom)':>14}")
        for k in range(1, 6):
            maj = sum(per_task_curve[key][k][0] for key in keys) / len(keys)
            orc = sum(per_task_curve[key][k][1] for key in keys) / len(keys)
            print(f"{k:>2}  {maj*100:>13.2f}%  {orc*100:>7.2f}%  {(orc-maj)*100:>13.2f}pp")
        print()

    for run in runs:
        keys = [key for key in tasks if key[0] == run]
        report(keys, run)

    all_keys = list(tasks.keys())
    report(all_keys, "POOLED (all 3 runs)")

    # bootstrap CI over tasks, pooled
    rng = random.Random(args.seed)
    B = args.resamples
    boot_maj = {k: [] for k in range(1, 6)}
    boot_orc = {k: [] for k in range(1, 6)}
    n = len(all_keys)
    for _ in range(B):
        sample = [all_keys[rng.randrange(n)] for _ in range(n)]
        for k in range(1, 6):
            boot_maj[k].append(sum(per_task_curve[key][k][0] for key in sample) / n)
            boot_orc[k].append(sum(per_task_curve[key][k][1] for key in sample) / n)
    print(f"=== POOLED bootstrap 95% CI over tasks (B={B} resamples) ===")
    print(f"{'k':>2}  {'majority [95% CI]':>26}  {'oracle [95% CI]':>24}  {'gap [95% CI]':>20}")
    for k in range(1, 6):
        mv = sorted(boot_maj[k]); ov = sorted(boot_orc[k])
        gapv = sorted(o - m for o, m in zip(boot_orc[k], boot_maj[k]))
        lo, hi = int(0.025 * B), int(0.975 * B) - 1
        print(f"{k:>2}  {mv[B//2]*100:>6.2f}% [{mv[lo]*100:.2f}, {mv[hi]*100:.2f}]"
              f"  {ov[B//2]*100:>6.2f}% [{ov[lo]*100:.2f}, {ov[hi]*100:.2f}]"
              f"  {gapv[B//2]*100:>6.2f}pp [{gapv[lo]*100:.2f}, {gapv[hi]*100:.2f}]")
    print()

    # marginal step k -> k+1 for majority-vote, with bootstrap CI on the *paired* diff
    print("=== POOLED marginal gain of one more sample (majority-vote), paired bootstrap ===")
    for k in range(1, 5):
        diffs = []
        for _ in range(B):
            sample = [all_keys[rng.randrange(n)] for _ in range(n)]
            d = sum(per_task_curve[key][k + 1][0] - per_task_curve[key][k][0] for key in sample) / n
            diffs.append(d)
        diffs.sort()
        lo, hi = int(0.025 * B), int(0.975 * B) - 1
        point = sum(per_task_curve[key][k + 1][0] - per_task_curve[key][k][0] for key in all_keys) / n
        print(f"  k={k}->k+1={k+1}: +{point*100:.3f}pp  [95% CI {diffs[lo]*100:.3f}, {diffs[hi]*100:.3f}]"
              f"  {'(CI excludes 0 -- real gain)' if diffs[lo] > 0 else '(CI includes 0 -- indistinguishable from no gain)'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("runs", nargs="*", default=DEFAULT_RUNS)
    b.add_argument("--out", required=True)
    b.add_argument("--workers", type=int, default=10)
    b.set_defaults(func=cmd_build)

    a = sub.add_parser("analyze")
    a.add_argument("cache")
    a.add_argument("--resamples", type=int, default=5000)
    a.add_argument("--seed", type=int, default=1234)
    a.set_defaults(func=cmd_analyze)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
