"""補跑：把 hidden_ok=False 的候選用更長的 timeout 重跑一次。

為什麼需要：本機在重放期間負載極高（load average >900，同時有數個 sibling
replay 在跑），`meets_demand` 的 10 秒 wall timeout 會把「其實會過」的候選
判成 False（對 OFF 臂 179 題的對帳量到 3 筆這種假陰性，見報告）。
假陰性只會往一個方向錯，所以**只重跑 False**：True 不可能是假陽性。
真正錯的候選會在第一個失敗的 assert 就丟例外、幾乎不花時間，所以這一輪很便宜。

仍然只碰 hidden_check（計分側），不改任何 policy 讀得到的欄位。
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import exec_select as E  # noqa: E402

OUT = E.CACHE / "hidden_retry.jsonl"


def _retry(job):
    run, arm, tid, idx, code = job
    t = E._TASKS[tid]
    rec = {"run": run, "arm": arm, "task_id": tid, "idx": idx}
    try:
        ok, _ = E.meets_demand(code, t["hidden_check"]["code"], timeout_s=40,
                               entry_point=t.get("entry_point"))
        rec["hidden_ok2"] = ok
    except E.InfraVoid as e:
        rec["err"] = str(e)
    return rec


def main(runs, workers):
    E._init()
    done = set()
    if OUT.exists():
        for ln in OUT.open():
            try:
                r = json.loads(ln)
            except Exception:
                continue
            done.add((r["run"], r["arm"], r["task_id"], r["idx"]))
    jobs = []
    for run in runs:
        cands = E.load_candidates(run)
        for ln in (E.CACHE / f"{run}.jsonl").open(encoding="utf-8"):
            r = json.loads(ln)
            if r.get("hidden_ok") is not False:
                continue
            # visible 失敗 ⇒ hidden 必敗（hidden 的 assert 是 visible 的超集，
            # 同一份 preamble、同一個 canonical）。這些不需要重跑。
            if not r.get("visible_ok"):
                continue
            key = (run, r["arm"], r["task_id"], r["idx"])
            if key in done:
                continue
            lst = cands.get((r["arm"], r["task_id"]))
            if not lst or r["idx"] >= len(lst):
                continue
            jobs.append((run, r["arm"], r["task_id"], r["idx"], lst[r["idx"]]["code"]))
    print(f"retrying {len(jobs)} hidden-False candidates", flush=True)
    with OUT.open("a", encoding="utf-8") as f, \
            cf.ProcessPoolExecutor(workers, initializer=E._init) as ex:
        for n, rec in enumerate(ex.map(_retry, jobs, chunksize=2), 1):
            f.write(json.dumps(rec) + "\n")
            if n % 50 == 0:
                f.flush()
                print(f"  {n}/{len(jobs)}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main(sys.argv[1].split(","), int(sys.argv[2]) if len(sys.argv) > 2 else 8)
