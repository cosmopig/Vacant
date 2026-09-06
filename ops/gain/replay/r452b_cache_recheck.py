#!/usr/bin/env python3
"""round452b — matrix／flags cache 的**渲染不變性抽查**。

為什麼需要這一支：R452b 的修法改了 `render()` 的位元組（entry point 從裸名字改成
`__vacant_ns['名字']` 查找），所以每一份用舊渲染器量出來的標籤原則上都要重量。
無損普查（1840＋455 格）已經全量重跑過、逐格相同；但殘餘表還吃兩份**更貴**的
cache——`r452_matrix_*`（1143 格 × 10 次）與 `r452_flags_*`（1104 格 × 10 次），
全量重跑約 14 分鐘。

本支的立場寫清楚，不含糊：
  - **論證**：新舊碼只差「怎麼取受測函式」。舊版靠裸名字沿 module → builtins 解析，
    新版靠 `__vacant_ns[名字]`；而 `__vacant_ns` 的內容**就是**那些 proxy，
    也就是舊版裸名字在 module scope 會找到的同一批東西。差別只在候選沒有定義
    那個名字時：舊版 `NameError`、新版 `KeyError`，兩者都是 rc≠0 ⇒ 同一個標籤。
  - **證據**：普查 2295 格全量重跑、0 格不同（`r452_census_*.json`）。
  - **抽查**：本支再從 matrix／flags 各抽一批格子真的重跑，把「論證」變成有數字的。
抽不到的不算證明。抽查有任何一格不同，殘餘表就必須全量重算——那一格會被印出來。
"""
from __future__ import annotations

import json
import pathlib
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2]))

import peer_exec_sim as sim                      # noqa: E402
import r452_suitespec as r452                    # noqa: E402

RUN = "g_r446_eq5_mbpp"
OUT = HERE / "r452b_cache_recheck.json"
SEED = 20260906


def _job(job):
    tid, kind, key, code, ep, subjects = job
    out = []
    for name, src in subjects:
        try:
            ok, _ = r452.meets_demand(src, code, 10, entry_point=ep)
        except Exception as exc:                                     # noqa: BLE001
            ok = f"error:{type(exc).__name__}"
        out.append((name, ok))
    return tid, kind, key, out


def main(n_cells: int = 60, workers: int = 6) -> None:
    tasks, cands = sim.load_pool(RUN)
    specs = r452.load_specs(RUN)
    refs = sim.canonical_refs(RUN)
    mat = r452.load_matrix(RUN)
    flg = r452.load_flags(RUN)
    rng = random.Random(SEED)

    cells = []
    for tid, per in sorted(mat.items()):
        for j in per:
            cells.append((tid, "matrix", j))
    for tid, per in sorted(flg.items()):
        for v in per:
            cells.append((tid, "flags", v))
    picked = rng.sample(cells, min(n_cells * 2, len(cells)))

    jobs = []
    for tid, kind, key in picked:
        spec = specs.get(tid)
        if spec is None or tid not in tasks:
            continue
        ep = tasks[tid].get("entry_point")
        use = (r452.single_test_spec(spec, int(key)) if kind == "matrix"
               else r452.flag_spec(spec, key))
        subjects = [(f"cand{i}", c) for i, c in enumerate(cands[tid])]
        subjects += [(f"stub{s}", src) for s, src in enumerate(sim.stub_set(ep))]
        if refs.get(tid):
            subjects.append(("ref", refs[tid]))
        jobs.append((tid, kind, key, use.render(), ep, subjects))

    t0 = time.time()
    n_runs = sum(len(j[5]) for j in jobs)
    print(f"{RUN}: cache 抽查 — {len(jobs)} 格 × ~10 次 = {n_runs} 次真沙箱，"
          f"{workers} workers", flush=True)
    same = diff = 0
    mismatches = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for tid, kind, key, res in ex.map(_job, jobs, chunksize=2):
            cached = (mat if kind == "matrix" else flg)[tid][key]
            for name, ok in res:
                want = cached.get(name)
                if ok == want or (ok is None and want is None):
                    same += 1
                else:
                    diff += 1
                    mismatches.append({"task_id": tid, "kind": kind, "cell": key,
                                       "subject": name, "rendered": ok, "cached": want})
    payload = {"run": RUN, "seed": SEED, "n_cells": len(jobs), "n_subject_runs": n_runs,
               "same": same, "mismatch": diff, "mismatches": mismatches[:50],
               "elapsed_s": round(time.time() - t0, 1)}
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"  逐格相同 {same}/{same + diff}   不同 {diff}   {time.time() - t0:.0f}s")
    for m in mismatches[:10]:
        print("   ", m)
    print("落盤：", OUT)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 60)
