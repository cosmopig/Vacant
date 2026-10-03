#!/usr/bin/env python3
"""i1001 步驟 1：LCB 計分器（scorers/code_suite.py，C5 同一份）在這個 staged 樹上的三個核對。零模型呼叫。

    python3 verify_lcb_scorer.py --staged <staged 根> --manifests <colab_banks_20260927 根> --c5x <解開的 c5 cells 根> \
        --probe-v12 ops/gain/data/lcb_probe_solutions.json --probe-v3 ops/gain/data/lcb_v3_probe_solutions.json \
        --ids-from pool_lcb.json --out verify_lcb.json

1. 正控制：repo 既有的手寫探針解（v1/v2 各 12、v3 12；其餘 LCB 題沒有參考解）⇒ 必須 pass:true。
2. 負控制：每一題放 `def <entry>(*a, **k): return None` ⇒ 必須 pass:false 且有 JSON 輸出。
3. 重算 C5：把歸檔的 app_final/solution.py（沒有檔＝沒交）餵進同一份計分器，和歸檔的 score.json 逐欄比
   （pass／visible_pass／false_done／hidden.passed／hidden.total）。不一致的列出來、不吞掉。
計分器吃 `scorer.py <hidden 目錄> <工作區>`；這裡每次用一個新的暫存工作區。
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time


def score(staged_task: pathlib.Path, solution_text: str | None, timeout: int = 900) -> dict:
    with tempfile.TemporaryDirectory() as d:
        app = pathlib.Path(d) / "app"
        app.mkdir()
        if solution_text is not None:
            (app / "solution.py").write_text(solution_text)
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, str(staged_task / "scorer.py"), str(staged_task / "hidden"), str(app)],
                               capture_output=True, text=True, timeout=timeout, cwd=d)
        except subprocess.TimeoutExpired:
            return {"_infra": "timeout"}
        lines = [l for l in r.stdout.splitlines() if l.strip()]
        if not lines:
            return {"_infra": "no output", "_stderr": r.stderr[-300:]}
        try:
            out = json.loads(lines[-1])
        except ValueError:
            return {"_infra": "bad json", "_last": lines[-1][:200]}
        out["_wall_s"] = round(time.time() - t0, 2)
        return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--staged", required=True, type=pathlib.Path)
    ap.add_argument("--manifests", required=True, type=pathlib.Path)
    ap.add_argument("--c5x", type=pathlib.Path)
    ap.add_argument("--probe-v12", type=pathlib.Path)
    ap.add_argument("--probe-v3", type=pathlib.Path)
    ap.add_argument("--ids-from", type=pathlib.Path, help="只核對這個池裡的題（預設：staged 裡全部）")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    a = ap.parse_args()

    tasks: list[tuple[str, str]] = []
    if a.ids_from:
        tasks = [(r["bank"], r["id"]) for r in json.loads(a.ids_from.read_text())["pool"]]
    else:
        for b in sorted(p.name for p in a.staged.iterdir() if p.is_dir()):
            tasks += [(b, t.name) for t in sorted((a.staged / b).iterdir()) if t.is_dir()]
    entry = {}
    for b in {b for b, _ in tasks}:
        m = json.loads((a.manifests / b / "bank_manifest.json").read_text())["tasks"]
        entry.update({(b, k): v["entry_point"] for k, v in m.items()})

    res: dict = {"schema": "i1001.verify_lcb/1", "n_tasks": len(tasks)}
    ex = cf.ThreadPoolExecutor(a.workers)

    # 2. 負控制
    def stub(bt):
        b, t = bt
        return bt, score(a.staged / b / t, f"def {entry[bt]}(*a, **k):\n    return None\n")
    stubs = list(ex.map(stub, tasks))
    bad_stub = [(f"{b}/{t}", r) for (b, t), r in stubs if r.get("pass") is not False]
    res["negative_stub"] = {"n": len(stubs), "pass_false": sum(1 for _, r in stubs if r.get("pass") is False),
                            "violations": [{"task": k, "result": r} for k, r in bad_stub]}
    # 負控制 2：沒交
    nosub = list(ex.map(lambda bt: (bt, score(a.staged / bt[0] / bt[1], None)), tasks))
    res["negative_no_solution"] = {"n": len(nosub), "pass_false": sum(1 for _, r in nosub if r.get("pass") is False and r.get("note")),
                                   "violations": [{"task": f"{b}/{t}", "result": r} for (b, t), r in nosub if not (r.get("pass") is False and r.get("note"))]}

    # 1. 正控制
    probe: dict[str, str] = {}
    for p in (a.probe_v12, a.probe_v3):
        if p:
            probe.update(json.loads(p.read_text()))
    where = {t: (b, t) for b, t in tasks}
    pos = []
    if a.ids_from is None:
        for tid, code in sorted(probe.items()):
            if tid in where:
                b = where[tid][0]
                pos.append(((b, tid), score(a.staged / b / tid, code)))
    else:   # 池裡只有部分探針題；其餘在 staged 全樹裡找
        for tid, code in sorted(probe.items()):
            for b in ("lcb_v1", "lcb_v2", "lcb_v3"):
                if (a.staged / b / tid).is_dir():
                    pos.append(((b, tid), score(a.staged / b / tid, code)))
    res["positive_reference"] = {"n": len(pos), "pass_true": sum(1 for _, r in pos if r.get("pass") is True),
                                 "rows": [{"task": f"{b}/{t}", "pass": r.get("pass"), "hidden": r.get("hidden") and [r["hidden"]["passed"], r["hidden"]["total"]],
                                           "wall_s": r.get("_wall_s")} for (b, t), r in pos]}

    # 3. 重算 C5
    if a.c5x:
        def rescore(bt):
            b, t = bt
            outs = {}
            for arm in ("A", "C361"):
                cell = a.c5x / "cells" / f"c5-{arm}-{b}-{t}-s1"
                if not (cell / "score.json").is_file():
                    outs[arm] = {"skipped": "no archived score.json"}
                    continue
                arch = json.loads((cell / "score.json").read_text().strip().splitlines()[-1])
                sol = cell / "app_final" / "solution.py"
                got = score(a.staged / b / t, sol.read_text() if sol.is_file() else None)
                keys = ("pass", "visible_pass", "false_done")
                diff = {k: [arch.get(k), got.get(k)] for k in keys if arch.get(k) != got.get(k)}
                for k in ("hidden", "visible"):
                    ah, gh = arch.get(k), got.get(k)
                    ap_, gp_ = (ah and [ah.get("passed"), ah.get("total")]), (gh and [gh.get("passed"), gh.get("total")])
                    if ap_ != gp_:
                        diff[k + "_passed_total"] = [ap_, gp_]
                outs[arm] = {"match": not diff, "diff": diff, "archived_pass": arch.get("pass")}
            return bt, outs
        rs = list(ex.map(rescore, tasks))
        n = sum(1 for _, o in rs for v in o.values() if "match" in v)
        mm = [{"task": f"{b}/{t}", "arm": arm, **v} for (b, t), o in rs for arm, v in o.items() if v.get("match") is False]
        res["rescore_c5"] = {"n_cells": n, "n_match": n - len(mm), "mismatches": mm}
    a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk not in ("rows", "violations", "mismatches")}) for k, v in res.items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
