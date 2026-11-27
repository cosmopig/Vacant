#!/usr/bin/env python3
"""Build the cchard-L bank: the 39 cchard tasks plus large/worst-case tests (pre-registered in
decisions/DECISION_20261127_EVIDENCE_CONTROLLER_HAIKUBAND.md, candidate 1).

Stages:  gen   - ask `claude -p --model haiku` for an input generator per task (cached, JSONL log, spend log)
         build - run generators, keep cases on which >=2 C++ reference solutions agree within 0.5x limit, write bank + manifest
Builder-only dependency: pyarrow (run with /tmp/ccvenv/bin/python).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import pathlib
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build_cc40 as B  # noqa: E402
import build_cchard as H  # noqa: E402

WORK = pathlib.Path("/opt/ctlwork/cchardL_work")
KINDS = [("max", s) for s in range(1, 7)] + [("mid", s) for s in range(1, 4)] + [("edge", s) for s in range(1, 4)]
MAX_LARGE = 12
GEN_PROMPT = """Below is a competitive programming problem statement and one sample input.

Write a Python 3 script (standard library only) that generates ONE valid test input for this problem and prints it to standard output.
Usage: `python3 gen.py SEED KIND` where SEED is an integer (use it to seed `random.Random`) and KIND is one of:
  max  - a random input with every size parameter at (or very near) its maximum allowed by the constraints, values random within their ranges;
  mid  - a random input with size parameters about 1/10 of the maximum;
  edge - a small input that hits an extreme boundary of the constraints (smallest/largest values, degenerate structure).
The output must follow the input format exactly and satisfy every constraint and guarantee in the statement (for example: distinct values, connected graphs/trees,
a promised solution exists, sum-of-n limits over all test cases in one file). If the format has a number of test cases, choose it so the whole input respects the sum limits.
Keep the total output under 900000 bytes. Reply with only the script in one ```python code block.

=== PROBLEM ===
{desc}

=== SAMPLE INPUT ===
{sample}
"""
SPEND = pathlib.Path(__file__).parents[1] / "results/ctl_haikuband_20261127/SPEND.jsonl"


def load_rows(data, tids):
    import pyarrow.parquet as pq
    rows = {}
    for split in ("valid", "test"):
        f = next(pathlib.Path(data).glob(f"{split}*.parquet"))
        for r in pq.read_table(f).to_pylist():
            tid = f"cc_{r['cf_contest_id']}{r['cf_index']}"
            if tid in tids and tid not in rows and r["source"] == 2:
                r["_name"] = r["name"]
                rows[tid] = r
    return rows


def spend(rec):
    with open(SPEND, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def gen_one(tid, row, log):
    d = WORK / tid
    d.mkdir(parents=True, exist_ok=True)
    if (d / "gen.py").exists():
        return tid, "cached"
    sample = (row["public_tests"]["input"] or [""])[0][:3000]
    prompt = GEN_PROMPT.format(desc=row["description"].strip()[:12000], sample=sample)
    for attempt in range(2):
        t0 = time.time()
        p = subprocess.run(["claude", "-p", "--model", "haiku", "--output-format", "json", "--tools", "", "--no-session-persistence"],
                           input=prompt, capture_output=True, text=True, timeout=600, cwd=tempfile.gettempdir())
        try:
            j = json.loads(p.stdout)
        except Exception:
            j = {"result": "", "total_cost_usd": 0, "error": p.stdout[:200] + p.stderr[:200]}
        m = re.search(r"```python\n(.*?)```", j.get("result", ""), re.S)
        rec = {"stage": "cchardL_gen", "task": tid, "attempt": attempt, "cost": j.get("total_cost_usd", 0), "wall": round(time.time() - t0, 1),
               "prompt_sha256": B.sha256_b(prompt.encode()), "response": j.get("result", ""), "ok_block": bool(m)}
        log.write(json.dumps(rec, ensure_ascii=False) + "\n")
        log.flush()
        spend({"stage": "cchardL_gen", "task": tid, "usd": j.get("total_cost_usd", 0)})
        if not m:
            continue
        (d / "gen.py").write_text(m.group(1), encoding="utf-8")
        ok = True
        for kind, seed in (("edge", 1), ("max", 1)):
            try:
                q = subprocess.run([sys.executable, "-I", str(d / "gen.py"), str(seed), kind], capture_output=True, text=True, timeout=120)
                if q.returncode != 0 or not q.stdout.strip():
                    ok = False
            except subprocess.TimeoutExpired:
                ok = False
        if ok:
            return tid, "ok"
        (d / "gen.py").rename(d / f"gen_bad{attempt}.py")
    return tid, "failed"


def cpp_refs(row, pf, td):
    """C++ solutions (<=12 considered) that pass all original cases within 0.5x limit (same criterion as cchard)."""
    limit = pf["limit"]
    cases = pf["vis"] + pf["hid"]
    out = []
    sols = [s for l, s in zip(row["solutions"]["language"], row["solutions"]["solution"]) if l == 2][:12]
    for si, code in enumerate(sols):
        exe = H.compile_cpp(code, td, f"s{si}")
        if exe is None:
            continue
        good = True
        for c in cases:
            st, w, o = H.run_cmd([exe], c["input"], limit)
            if st != "ok" or o.split() != c["output"].split() or w > 0.5 * limit:
                good = False
                break
        if good:
            out.append((exe, code))
        if len(out) >= 4:
            break
    return out


def large_cases(tid, row, pf):
    limit = pf["limit"]
    with tempfile.TemporaryDirectory(prefix="cchl-") as t:
        td = pathlib.Path(t)
        refs = cpp_refs(row, pf, td)
        info = {"n_refs": len(refs), "cands": []}
        if len(refs) < 2:
            return [], info, None
        kept = []
        for kind, seed in KINDS:
            c = {"kind": kind, "seed": seed}
            try:
                q = subprocess.run([sys.executable, "-I", str(WORK / tid / "gen.py"), str(seed), kind], capture_output=True, text=True, timeout=120)
            except subprocess.TimeoutExpired:
                c["result"] = "gen_timeout"
                info["cands"].append(c)
                continue
            inp = q.stdout
            if q.returncode != 0 or not inp.strip() or len(inp.encode()) > B.MAX_BYTES:
                c["result"] = "gen_fail_or_big"
                info["cands"].append(c)
                continue
            outs, walls, bad = [], [], None
            for r, _ in refs:
                st, w, o = H.run_cmd([r], inp, limit)
                walls.append(round(w, 3))
                if st != "ok":
                    bad = st
                    break
                if w > 0.5 * limit:
                    bad = "slow"
                    break
                outs.append(o)
            if bad is None and len(outs) >= 2 and all(o.split() == outs[0].split() for o in outs) and len(outs[0].encode()) <= B.MAX_BYTES and outs[0].strip():
                c["result"] = "keep"
                c["bytes"] = len(inp.encode())
                c["max_wall"] = max(walls)
                kept.append({"input": inp, "output": outs[0]})
            else:
                c["result"] = bad or ("disagree" if len(outs) >= 2 and outs[0].strip() else "empty_output")
            c["walls"] = walls
            info["cands"].append(c)
        return kept, info, refs[0][1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["gen", "build"])
    ap.add_argument("--data", default="/tmp/cc_data")
    ap.add_argument("--cchard-manifest", required=True)
    ap.add_argument("--out", default="/opt/ctlwork/bm_tasks/cchardL")
    ap.add_argument("--manifest")
    ap.add_argument("--logdir", required=True)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    man0 = json.loads(pathlib.Path(a.cchard_manifest).read_text())
    tids = [t["task"] for t in man0["tasks"]]
    rows = load_rows(a.data, set(tids))
    assert set(rows) == set(tids), set(tids) - set(rows)
    logdir = pathlib.Path(a.logdir)
    logdir.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    if a.stage == "gen":
        with open(logdir / "gen_calls.jsonl", "a") as log, cf.ThreadPoolExecutor(a.workers) as ex:
            for tid, st in ex.map(lambda t: gen_one(t, rows[t], log), tids):
                print(tid, st, flush=True)
        return 0
    out = pathlib.Path(a.out)
    pfs = {}
    for tid in tids:
        pf, why = B.prefilter(rows[tid])
        assert pf is not None
        t0 = next(t for t in man0["tasks"] if t["task"] == tid)
        assert (len(pf["vis"]), len(pf["hid"])) == (t0["n_vis"], t0["n_hid"]), tid
        pfs[tid] = pf
    infos = {}
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = {tid: ex.submit(large_cases, tid, rows[tid], pfs[tid]) for tid in tids if (WORK / tid / "gen.py").exists()}
        for tid, fu in futs.items():
            infos[tid] = fu.result()
            print(tid, "refs", infos[tid][1]["n_refs"], "kept", len(infos[tid][0]), flush=True)
    with open(logdir / "large_case_candidates.jsonl", "w") as f:
        for tid in tids:
            if tid in infos:
                f.write(json.dumps({"task": tid, **infos[tid][1]}) + "\n")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    files, tasks, excluded = {}, [], []
    for tid in tids:
        kept, info, refcode = infos.get(tid, ([], {"n_refs": None, "cands": []}, None))
        row, pf = rows[tid], pfs[tid]
        rng = random.Random(f"{B.SEED}:{row['_name']}:L")
        rng.shuffle(kept)
        kept = kept[:MAX_LARGE]
        nv = len(kept) // 2
        if len(kept) < 4 or nv < 2 or len(kept) - nv < 2:
            excluded.append({"task": tid, "reason": f"large_kept={len(kept)}", "refs": info["n_refs"]})
            continue
        pfL = dict(pf)
        pfL["vis"] = pf["vis"] + kept[:nv]
        pfL["hid"] = pf["hid"] + kept[nv:]
        t0 = next(t for t in man0["tasks"] if t["task"] == tid)
        files.update(H.write_task(out, tid, row, pfL))
        rc = H.real_check(out, tid, 2, refcode)
        tasks.append({"task": tid, "name": row["name"], "rating": t0["rating"], "n_vis": len(pfL["vis"]), "n_hid": len(pfL["hid"]),
                      "n_large_vis": nv, "n_large_hid": len(kept) - nv, "case_limit_s": pf["limit"], "n_refs": info["n_refs"],
                      "large_kinds_kept": sorted({c["kind"] for c in info["cands"] if c["result"] == "keep"}), "real_check": rc})
        print(tid, "built", rc["ok"], flush=True)
    man = {"bank_id": out.name, "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source_bank": "cchard",
           "cchard_manifest_sha256": B.sha256_b(pathlib.Path(a.cchard_manifest).read_bytes()), "n_tasks": len(tasks), "tasks": tasks,
           "excluded": excluded, "files_sha256": files}
    pathlib.Path(a.manifest).write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
    bad = [t["task"] for t in tasks if not t["real_check"]["ok"]]
    print("built", len(tasks), "excluded", len(excluded), "bad real_check", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
