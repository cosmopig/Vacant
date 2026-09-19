"""對既有題庫的 `visible_check` 實跑變異致死率（`vacant_network/suitemutate.py` 的量測入口）。

這支在架構裡承重什麼
====================
`gain_run.probe_instrument` 對 `visible_check` 只驗兩件事：參考解會過、`return None`
的壞樁被擋。那是**一個**變異體的刻度。CONFORM 臂用 `visible_check` 當出貨閘門
（`arm_conform` 通過就早停），所以「閘門到底有多緊」直接決定 P-C1／P-C3 怎麼讀。
本腳本把那把尺換成 `suitemutate` 的 N 個變異體，回答：**我們實際用的可見驗收套件，
擋得住我們造得出來的錯的幾成。**

⚠ 這裡量到的數字**不進任何閘門**。`suitegauge.GaugeOutcome.ok` 的語意
  （壞樁全被擋才算合格）一個字都沒有動，r452c 那批歸檔資料維持可比。
  致死率是另外算、另外報的診斷量，不是新的合格線。

⚠ 誠實邊界（與 `suitemutate` 模組 docstring 同一條）：致死率永遠是**下界**——
  運算子表有限，且等價變異體不可判定。100% 只代表「這 N 種錯都被擋住」，
  **不**代表驗收涵蓋需求。

參考解全是**驗證者側**的物件（`gain_run._canonical_solutions`，V/GT 分離照舊）：
不進任何 prompt、不進 worker。用法：

    PYTHONPATH=. python ops/gain/mutation_score_banks.py \
        --bank lcb2 --limit 20 --out ops/gain/data/suite_mutation_scores.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.gain.gain_run import _canonical_solutions, _gauge_runner  # noqa: E402
from vacant_network.codebench import (  # noqa: E402
    EvalPlusHumanEvalLoader,
    EvalPlusMBPPLoader,
    LiveCodeBenchLoader,
)
from vacant_network.suitemutate import score_suite  # noqa: E402

BANKS = {
    "lcb": ("v1", "lcb"), "lcb2": ("v2", "lcb2"), "lcb3": ("v3", "lcb3"),
}


def _loader(bank: str):
    if bank in BANKS:
        return LiveCodeBenchLoader(version=BANKS[bank][0])
    if bank == "evalplus":
        return EvalPlusMBPPLoader()
    if bank == "humanevalplus":
        return EvalPlusHumanEvalLoader()
    raise SystemExit(f"未知 bank：{bank}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", default="lcb2")
    ap.add_argument("--seed", default="r535_mutation")
    ap.add_argument("--limit", type=int, default=20, help="每題的變異體上限")
    ap.add_argument("--tasks", type=int, default=0, help="取前 N 題（0＝有參考解的全部）")
    ap.add_argument("--timeout", type=int, default=10)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    refs = _canonical_solutions(args.bank)
    tasks = [t for t in _loader(args.bank).iter_tasks(args.seed) if refs.get(t["task_id"])]
    if args.tasks:
        tasks = tasks[: args.tasks]
    rows = []
    t_start = time.time()
    for t in tasks:
        t0 = time.time()
        out = score_suite(
            t["visible_check"]["code"], refs[t["task_id"]],
            entry_point=t.get("entry_point"), runner=_gauge_runner,
            timeout_s=args.timeout, limit=args.limit, seed=args.seed,
        )
        d = out.as_dict()
        d["task_id"] = t["task_id"]
        d["entry_point"] = t.get("entry_point")
        d["seconds"] = round(time.time() - t0, 2)
        rows.append(d)
        print(f"{t['task_id']:<28} killed={out.killed:>2}/{out.total:<2} "
              f"score={(out.score if out.score is not None else float('nan')):.3f} "
              f"ref={int(out.ref_passed)} norm={int(bool(out.normalized_passed))} "
              f"{d['seconds']:>6.2f}s", flush=True)
        for m in out.survivors:
            print(f"    alive [{m.operator}] L{m.lineno}: {m.before}  =>  {m.after}",
                  flush=True)
    scored = [r["score"] for r in rows if r["score"] is not None and r["ref_passed"]]
    summary = {
        "bank": args.bank, "seed": args.seed, "limit": args.limit,
        "n_tasks": len(rows), "n_scored": len(scored),
        "n_ref_fail": sum(1 for r in rows if not r["ref_passed"]),
        "n_norm_fail": sum(1 for r in rows if r["normalized_passed"] is False),
        "median": statistics.median(scored) if scored else None,
        "mean": statistics.fmean(scored) if scored else None,
        "min": min(scored) if scored else None,
        "max": max(scored) if scored else None,
        "perfect": sum(1 for s in scored if s == 1.0),
        "total_seconds": round(time.time() - t_start, 2),
        "total_runs": sum(r["total"] + 2 for r in rows),
    }
    summary["seconds_per_run"] = round(
        summary["total_seconds"] / max(1, summary["total_runs"]), 3)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.out:
        p = pathlib.Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"summary": summary, "rows": rows},
                                ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"→ {p}")


if __name__ == "__main__":
    main()
