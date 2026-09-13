"""離線重放（roster 角度）：把 ON 臂的 gen 候選補進候選池標記。

這支**不打任何模型端點**。候選全部來自 runs/<run>/calls.jsonl 已落盤的 response。
標記方法直接沿用 exec_select.py 的 `visible_grade`（只讀 visible_check）與
gain_run.meets_demand（只寫 hidden_ok 計分欄位），確保與既有 cache 同一把尺。

寫入 ops/gain/replay/cache_roster/<run>.jsonl（自己的檔，不動別人的 cache）。
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

import exec_select as ES  # noqa: E402  沿用同一套標記函式

OUT = HERE / "cache_roster"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--arms", default="ON")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    arms = tuple(x for x in a.arms.split(",") if x)
    OUT.mkdir(parents=True, exist_ok=True)
    ES._init()
    for run in a.runs.split(","):
        cands = ES.load_candidates(run)
        jobs = [(run, arm, tid, i, c)
                for (arm, tid), lst in sorted(cands.items())
                if tid in ES._TASKS and arm in arms
                for i, c in enumerate(lst) if c["role"] == "gen"]
        outp = OUT / f"{run}.jsonl"
        done = set()
        if outp.exists():
            for ln in outp.open():
                r = json.loads(ln)
                done.add((r["arm"], r["task_id"], r["idx"]))
        jobs = [j for j in jobs if (j[1], j[2], j[3]) not in done]
        print(f"{run}: {len(jobs)} gen candidates to score ({arms})", flush=True)
        with outp.open("a", encoding="utf-8") as f, \
                cf.ProcessPoolExecutor(a.workers, initializer=ES._init) as ex:
            for n, rec in enumerate(ex.map(ES._work, jobs, chunksize=2), 1):
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                if n % 25 == 0:
                    f.flush()
                    print(f"  {n}/{len(jobs)}", flush=True)
        print(f"{run}: done -> {outp}", flush=True)


if __name__ == "__main__":
    main()
