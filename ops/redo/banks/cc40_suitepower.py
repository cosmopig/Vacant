#!/usr/bin/env python3
"""Model-free suite-power measurement for code_contests tasks (no model data involved).

For each task in a manifest: run up to K incorrect Python 3 solutions (dataset field `incorrect_solutions`) on the
visible half and the hidden half (same case list as the bank), and record how many each half rejects; also the
fraction of hidden cases whose expected output equals the most common expected output (answer diversity).

Usage: cc40_suitepower.py --data D --bank B --manifest M --out OUT.jsonl [--k 10] [--workers 3]
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import json
import pathlib
import subprocess
import tempfile
import time


def runs_ok(path: str, cases: list, limit: float) -> bool:
    """True if the program reproduces every expected output within the limit (WA/RTE/TLE on any case = False)."""
    for c in cases:
        try:
            p = subprocess.run(["python3", "-I", "-S", path], input=c["input"], capture_output=True, text=True, timeout=limit)
        except subprocess.TimeoutExpired:
            return False
        if p.returncode != 0 or p.stdout.split() != c["output"].split():
            return False
    return True


def one(task: dict, bank: pathlib.Path, row: dict, k: int) -> dict:
    tid = task["task"]
    vis = json.loads((bank / tid / "workspace" / "cases.json").read_text())
    hid = json.loads((bank / tid / "hidden" / "hidden_cases.json").read_text())
    lim = task["case_limit_s"]
    inc = [s for l, s in zip(row["incorrect_solutions"]["language"], row["incorrect_solutions"]["solution"]) if l == 3][:k]
    killed_v = killed_h = killed_any = 0
    with tempfile.TemporaryDirectory(prefix="cc40p-") as td:
        for i, code in enumerate(inc):
            f = pathlib.Path(td) / f"i{i}.py"
            f.write_text(code, encoding="utf-8")
            pv = runs_ok(str(f), vis, lim)
            ph = runs_ok(str(f), hid, lim)
            killed_v += (not pv)
            killed_h += (not ph)
            killed_any += (not (pv and ph))
    modal = collections.Counter(" ".join(c["output"].split()) for c in hid).most_common(1)[0][1] / len(hid)
    return {"task": tid, "rating": task["rating"], "n_incorrect": len(inc), "killed_visible": killed_v,
            "killed_hidden": killed_h, "killed_either": killed_any,
            "kill_rate_hidden": round(killed_h / len(inc), 3) if inc else None,
            "modal_output_fraction_hidden": round(modal, 3),
            "distinct_outputs_hidden": len({" ".join(c["output"].split()) for c in hid})}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--bank", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    import pyarrow.parquet as pq
    man = json.loads(pathlib.Path(a.manifest).read_text())
    want = {t["task"]: t for t in man["tasks"]}
    rows = {}
    for split in ("valid", "test"):
        f = next(pathlib.Path(a.data).glob(f"{split}*.parquet"))
        for r in pq.read_table(f).to_pylist():
            tid = f"cc_{r['cf_contest_id']}{r['cf_index']}"
            if tid in want and tid not in rows and want[tid]["split"] == split:
                rows[tid] = r
    t0 = time.time()
    with cf.ThreadPoolExecutor(a.workers) as ex, open(a.out, "w") as out:
        futs = [ex.submit(one, want[t], pathlib.Path(a.bank), rows[t], a.k) for t in want]
        for fu in futs:
            r = fu.result()
            out.write(json.dumps(r) + "\n")
            out.flush()
            print(r, flush=True)
    print("elapsed", round(time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
