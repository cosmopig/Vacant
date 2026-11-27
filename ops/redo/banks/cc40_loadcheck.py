#!/usr/bin/env python3
"""Timing check for cc40 (prereg: pick the largest N such that all reference solutions still pass both halves
when run N-wide concurrently). Re-reads the reference solutions from the pinned parquet files (manifest says which).

Usage: python3 cc40_loadcheck.py --data /tmp/cc_data --bank /opt/ctlwork/bm_tasks/cc40 --manifest <MANIFEST> --out <jsonl> --widths 32,16,8,4
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


def run_one(bank: pathlib.Path, tid: str, code: str) -> dict:
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="cc40l-") as t:
        w = pathlib.Path(t) / "w"
        shutil.copytree(bank / tid / "workspace", w)
        (w / "solution.py").write_text(code, encoding="utf-8")
        p = subprocess.run(["python3", "-m", "unittest", "solution_test"], cwd=w, capture_output=True, text=True, timeout=900)
        vis = p.returncode == 0
        sp = subprocess.run([sys.executable, str(bank / tid / "scorer.py"), str(bank / tid / "hidden"), str(w)],
                            capture_output=True, text=True, timeout=900)
        sc = json.loads(sp.stdout.strip().splitlines()[-1])
    return {"task": tid, "visible_ok": vis, "hidden_pass": sc["pass"], "wall": round(time.time() - t0, 2)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--bank", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--widths", default="32,16,8,4")
    a = ap.parse_args()
    import pyarrow.parquet as pq
    man = json.loads(pathlib.Path(a.manifest).read_text())
    want = {t["task"]: t for t in man["tasks"]}
    refs = {}
    for split in ("valid", "test"):
        f = next(pathlib.Path(a.data).glob(f"{split}*.parquet"))
        for r in pq.read_table(f).to_pylist():
            tid = f"cc_{r['cf_contest_id']}{r['cf_index']}"
            if tid in want and tid not in refs and want[tid]["split"] == split:
                py = [s for l, s in zip(r["solutions"]["language"], r["solutions"]["solution"]) if l == 3][:8]
                refs[tid] = py[want[tid]["ref_solution_idx"]]
    assert set(refs) == set(want), "missing refs"
    bank = pathlib.Path(a.bank)
    out = open(a.out, "w")
    chosen = None
    for n in [int(x) for x in a.widths.split(",")]:
        jobs = list(refs.items())
        # N-wide: submit every task so that exactly n run at once; 2 rounds so every width sees >= n concurrent runs
        jobs = (jobs * ((n + len(jobs) - 1) // len(jobs) + 1))[: max(len(jobs), n * 2)]
        t0 = time.time()
        with cf.ThreadPoolExecutor(n) as ex:
            res = list(ex.map(lambda kv: run_one(bank, kv[0], kv[1]), jobs))
        bad = [r for r in res if not (r["visible_ok"] and r["hidden_pass"])]
        rec = {"width": n, "runs": len(res), "fail": len(bad), "failed_tasks": sorted({r["task"] for r in bad}),
               "max_wall": max(r["wall"] for r in res), "elapsed": round(time.time() - t0, 1)}
        out.write(json.dumps(rec) + "\n")
        out.flush()
        print(rec, flush=True)
        if not bad and chosen is None:
            chosen = n
    print("chosen jobs:", chosen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
