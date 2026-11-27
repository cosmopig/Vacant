#!/usr/bin/env python3
"""Build the cc40 bank (competitive-programming tasks from deepmind/code_contests).

Pre-registered in decisions/DECISION_20261127_EVIDENCE_CONTROLLER_HARDPOOL.md; every rule below is that file's.
Builder-only dependency: pyarrow (not a runtime dependency of the repo).

Usage:
    python3 ops/redo/banks/build_cc40.py --data /tmp/cc_data --out /opt/ctlwork/bm_tasks/cc40 \
        --manifest ops/redo/results/ctl_hardpool_20261127/bank_cc40_MANIFEST.json
Reference solutions run with `python3 -I -S` (stdlib only).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import pathlib
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time

SEED = 20261127
BANDS = [("B1", 1200, 1500), ("B2", 1500, 1800), ("B3", 1800, 2100), ("B4", 2100, 2400), ("B5", 2400, 10**9)]
PER_BAND = 8
MAX_CASES = 60
MIN_CASES = 20
MAX_BYTES = 1 << 20
PY = "python3"
EXCL_RE = re.compile(
    r"<image>|interact|flush|any of (them|these)|print any|output any|prints? any"
    r"|if there are (several|multiple|many)|multiple (answers|solutions)|several (answers|solutions)"
    r"|any (valid|correct|possible)|in any order|you may (print|output)|absolute or relative"
    r"|relative error|absolute error|precision", re.I)
FLOAT_RE = re.compile(r"^-?\d+\.\d+$")

SCORER_SRC = pathlib.Path(__file__).with_name("build_ctl16.py")


def scorer_template() -> str:
    src = SCORER_SRC.read_text(encoding="utf-8")
    m = re.search(r"SCORER_TEMPLATE = r'''(.*?)'''\n", src, re.S)
    assert m, "SCORER_TEMPLATE not found"
    return m.group(1)


TEST_TEMPLATE = r'''"""Tests for solution.py (reads stdin, writes stdout). One test per case; output compared after
whitespace normalisation (whitespace-separated tokens must be equal)."""
import hashlib
import json
import os
import resource
import subprocess
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = "@DATA@"
_DATA_SHA256 = "@SHA@"
_LIMIT_S = @LIMIT@
_N = @N@
_state = {"timeouts": 0, "cases": None}


def _cases():
    if _state["cases"] is None:
        raw = open(os.path.join(_HERE, _DATA), "rb").read()
        if hashlib.sha256(raw).hexdigest() != _DATA_SHA256:
            raise AssertionError("data file %s was modified" % _DATA)
        _state["cases"] = json.loads(raw)
    return _state["cases"]


def _limits():
    resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))


def _clip(s, n=240):
    return s if len(s) <= n else s[:n] + "...(%d chars)" % len(s)


def _run_case(tc, i):
    if _state["timeouts"] >= 3:
        tc.fail("skipped: 3 earlier cases timed out in this run")
    case = _cases()[i]
    try:
        p = subprocess.run([sys.executable, "solution.py"], input=case["input"], capture_output=True, text=True,
                           cwd=_HERE, timeout=_LIMIT_S, preexec_fn=_limits)
    except subprocess.TimeoutExpired:
        _state["timeouts"] += 1
        tc.fail("time limit exceeded (%ss) on case %d" % (_LIMIT_S, i))
    if p.returncode != 0:
        tc.fail("runtime error (exit %d) on case %d: %s" % (p.returncode, i, _clip(p.stderr[-400:])))
    if p.stdout.split() != case["output"].split():
        tc.fail("wrong answer on case %d\ninput: %s\nexpected: %s\ngot: %s"
                % (i, _clip(case["input"]), _clip(case["output"]), _clip(p.stdout)))


class SolutionTest(unittest.TestCase):
    pass


def _mk(i):
    def t(self):
        _run_case(self, i)
    return t


for _i in range(_N):
    setattr(SolutionTest, "test_case_%02d" % _i, _mk(_i))

if __name__ == "__main__":
    unittest.main()
'''

GOAL_TMPL = """# {title}

Time limit per test: {tl} seconds. Memory limit: {ml} MB.

Write a Python 3 program that reads from standard input and writes to standard output.

{desc}
"""

CONTRACT = """# Contract

Write your solution to `solution.py` in the root of this workspace. The file exists as an empty stub; replace
its contents with a complete program that reads the input from standard input and prints the answer to
standard output, as the problem statement in `goal.md` describes.

- Put all of your code in `solution.py`. Only use the Python standard library; do not install packages.
- The tests for this task are in `solution_test.py` (with their data in `cases.json`). The tests are correct;
  don't change them or the data. Each test runs `solution.py` on one input and compares the output with the
  expected output after whitespace normalisation. A test fails if the program takes longer than {limit} seconds
  on one input. Run them with:

      python3 -m pytest -q solution_test.py

  or, without pytest:

      python3 -m unittest solution_test.py
"""


def sha256_b(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def run_py(code_path: str, inp: str, limit: float) -> tuple[str, float, str]:
    """-> (status ok|tle|rte, wall, stdout)"""
    t0 = time.time()
    try:
        p = subprocess.run([PY, "-I", "-S", code_path], input=inp, capture_output=True, text=True, timeout=limit)
    except subprocess.TimeoutExpired:
        return "tle", time.time() - t0, ""
    except Exception:
        return "rte", time.time() - t0, ""
    return ("ok" if p.returncode == 0 else "rte"), time.time() - t0, p.stdout


def prefilter(row: dict) -> tuple[dict | None, str | None]:
    desc = row["description"] or ""
    mm = EXCL_RE.search(desc)
    if mm:
        return None, "description:" + mm.group(0).lower()
    if row.get("input_file") or row.get("output_file"):
        return None, "file_io"
    seen, cases, dropped_big = set(), [], 0
    for grp in ("public_tests", "private_tests", "generated_tests"):
        g = row[grp]
        for a, b in zip(g["input"], g["output"]):
            if a in seen:
                continue
            seen.add(a)
            if len(a.encode()) > MAX_BYTES or len(b.encode()) > MAX_BYTES:
                dropped_big += 1
                continue
            cases.append({"input": a, "output": b})
    if any(FLOAT_RE.match(tok) for c in cases for tok in c["output"].split()):
        return None, "float_output"
    if len(cases) < MIN_CASES:
        return None, f"tests<{MIN_CASES}({len(cases)})"
    rng = random.Random(f"{SEED}:{row['_name']}")
    rng.shuffle(cases)
    cases = cases[:MAX_CASES]
    nv = len(cases) // 2
    tl = row["time_limit"]["seconds"] + row["time_limit"]["nanos"] / 1e9
    tl = tl if tl > 0 else 1.0
    return {"vis": cases[:nv], "hid": cases[nv:], "tl": tl, "limit": 2 * tl + 2,
            "dropped_big": dropped_big, "n_dedup": len(seen)}, None


def validate(row: dict, pf: dict) -> dict:
    limit = pf["limit"]
    cases = pf["vis"] + pf["hid"]
    sols = [s for l, s in zip(row["solutions"]["language"], row["solutions"]["solution"]) if l == 3][:8]
    good, tried = [], []
    with tempfile.TemporaryDirectory(prefix="cc40v-") as td:
        for si, code in enumerate(sols):
            f = pathlib.Path(td) / f"s{si}.py"
            f.write_text(code, encoding="utf-8")
            mx, why = 0.0, "ok"
            for ci, c in enumerate(cases):
                st, w, out = run_py(str(f), c["input"], limit)
                mx = max(mx, w)
                if st != "ok":
                    why = f"{st}@{ci}"
                    break
                if out.split() != c["output"].split():
                    why = f"wa@{ci}"
                    break
                if w > 0.5 * limit:
                    why = f"slow@{ci}({w:.2f}s>{0.5 * limit:.2f})"
                    break
            tried.append({"idx": si, "result": why, "max_wall": round(mx, 3)})
            if why == "ok":
                good.append((si, code, mx))
            if len(good) >= 2:
                break
    return {"good": good, "tried": tried, "n_solutions": len(sols)}


def write_task(out: pathlib.Path, tid: str, row: dict, pf: dict) -> dict[str, str]:
    td = out / tid
    ws, hid = td / "workspace", td / "hidden"
    ws.mkdir(parents=True)
    hid.mkdir(parents=True)
    limit = pf["limit"]
    lim_s = int(limit) if float(limit).is_integer() else limit

    def put(path: pathlib.Path, text: str | bytes):
        path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))

    for sub, cases, dname in ((ws, pf["vis"], "cases.json"), (hid, pf["hid"], "hidden_cases.json")):
        data = json.dumps(cases, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        put(sub / dname, data)
        put(sub / "solution_test.py", TEST_TEMPLATE.replace("@DATA@", dname).replace("@SHA@", sha256_b(data))
            .replace("@LIMIT@", repr(lim_s)).replace("@N@", str(len(cases))))
    put(ws / "solution.py", "# TODO: write the solution here (read stdin, write stdout)\n")
    title = row["name"].split(". ", 1)[-1] if ". " in row["name"] else row["name"]
    ml = round(row["memory_limit_bytes"] / (1 << 20))
    put(ws / "goal.md", GOAL_TMPL.format(title=title, tl=f"{pf['tl']:g}", ml=ml, desc=row["description"].strip()))
    put(ws / "contract.md", CONTRACT.format(limit=lim_s))
    put(td / "instruction.txt", "Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file.\n")
    put(td / "scorer.py", scorer_template())
    return {str(p.relative_to(out)): sha256_b(p.read_bytes()) for p in sorted(td.rglob("*")) if p.is_file()}


def real_check(out: pathlib.Path, tid: str, ref_code: str) -> dict:
    """Run the written artefacts: ref passes visible (unittest) + scorer; empty stub fails both."""
    res = {}
    for label, code in (("ref", ref_code), ("stub", None)):
        with tempfile.TemporaryDirectory(prefix="cc40r-") as t:
            w = pathlib.Path(t) / "w"
            shutil.copytree(out / tid / "workspace", w)
            if code is not None:
                (w / "solution.py").write_text(code, encoding="utf-8")
            p = subprocess.run([PY, "-m", "unittest", "solution_test"], cwd=w, capture_output=True, text=True, timeout=900)
            vis_ok = p.returncode == 0
            sp = subprocess.run([sys.executable, str(out / tid / "scorer.py"), str(out / tid / "hidden"), str(w)],
                                capture_output=True, text=True, timeout=900)
            sc = json.loads(sp.stdout.strip().splitlines()[-1])
            res[label] = {"visible_ok": vis_ok, "hidden_pass": sc["pass"], "hidden": f"{sc['tests_passed']}/{sc['tests_total']}"}
    ok = res["ref"]["visible_ok"] and res["ref"]["hidden_pass"] and (not res["stub"]["visible_ok"]) and (not res["stub"]["hidden_pass"])
    res["ok"] = bool(ok)
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    import pyarrow.parquet as pq
    data, out = pathlib.Path(a.data), pathlib.Path(a.out)
    parq = {}
    rows, seen_ids = [], set()
    for split in ("valid", "test"):
        f = next(data.glob(f"{split}*.parquet"))
        parq[f.name] = sha256_b(f.read_bytes())
        for r in pq.read_table(f).to_pylist():
            key = (r["cf_contest_id"], r["cf_index"])
            if r["source"] != 2 or not r["cf_rating"] or r["cf_rating"] <= 0 or key in seen_ids:
                continue
            seen_ids.add(key)
            r["_name"], r["_split"] = r["name"], split
            rows.append(r)
    excluded, cand = [], {b[0]: [] for b in BANDS}
    for r in rows:
        band = next((b[0] for b in BANDS if b[1] <= r["cf_rating"] < b[2]), None)
        if band is None:
            continue
        pf, why = prefilter(r)
        if pf is None:
            excluded.append({"name": r["name"], "band": band, "reason": why})
            continue
        cand[band].append((sha256_b(f"{SEED}:{r['name']}".encode()), r["name"], r, pf))
    for b in cand:
        cand[b].sort(key=lambda x: (x[0], x[1]))
    print({b: len(v) for b, v in cand.items()}, "prefilter-excluded", len(excluded), flush=True)
    chosen: dict[str, list] = {b[0]: [] for b in BANDS}
    cursor = {b: 0 for b in cand}
    validation_log = []
    with cf.ThreadPoolExecutor(a.workers) as ex:
        while True:
            batch = []
            for b in cand:
                need = PER_BAND - len(chosen[b])
                take = cand[b][cursor[b]:cursor[b] + need]
                cursor[b] += len(take)
                batch += [(b, t) for t in take]
            if not batch:
                break
            futs = [(b, t, ex.submit(validate, t[2], t[3])) for b, t in batch]
            for b, t, fu in futs:
                v = fu.result()
                ok = len(v["good"]) >= 2
                validation_log.append({"name": t[1], "band": b, "valid": ok, "tried": v["tried"], "n_py_solutions": v["n_solutions"]})
                if ok:
                    chosen[b].append((t, v))
                else:
                    excluded.append({"name": t[1], "band": b, "reason": "validity:" + (";".join(x["result"] for x in v["tried"]) or "no_python3_solution")})
                print(b, t[1], "OK" if ok else "x", [x["result"] for x in v["tried"]], flush=True)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    files, tasks = {}, []
    for b, items in chosen.items():
        for (h, name, row, pf), v in sorted(items, key=lambda x: x[0][1]):
            tid = f"cc_{row['cf_contest_id']}{row['cf_index']}"
            files.update(write_task(out, tid, row, pf))
            si, code, mx = v["good"][0]
            rc = real_check(out, tid, code)
            tasks.append({"task": tid, "name": row["name"], "split": row["_split"], "rating": row["cf_rating"], "band": b,
                          "n_vis": len(pf["vis"]), "n_hid": len(pf["hid"]), "time_limit_s": pf["tl"], "case_limit_s": pf["limit"],
                          "ref_solution_idx": si, "ref_max_case_wall_s": round(mx, 3), "dropped_big": pf["dropped_big"],
                          "n_dedup_tests": pf["n_dedup"], "real_check": rc})
            print(tid, b, row["cf_rating"], pf["limit"], rc, flush=True)
    man = {"bank_id": out.name, "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "seed": SEED,
           "parquet_sha256": parq, "bands": BANDS, "per_band": PER_BAND, "tasks": tasks,
           "n_tasks": len(tasks), "per_band_counts": {b: len(v) for b, v in chosen.items()},
           "excluded": excluded, "validation_log": validation_log, "files_sha256": files}
    pathlib.Path(a.manifest).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.manifest).write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
    bad = [t["task"] for t in tasks if not t["real_check"]["ok"]]
    print("built", len(tasks), "bad real_check:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
