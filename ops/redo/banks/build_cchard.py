#!/usr/bin/env python3
"""Build the cchard bank (Codeforces rating >= 2400 from deepmind/code_contests, not in cc40; oracle = Python 3 or C++).

Pre-registered in decisions/DECISION_20261127_EVIDENCE_CONTROLLER_HARDPOOL.md (附錄 1). Reuses build_cc40 helpers.
Builder-only dependency: pyarrow.

Usage: build_cchard.py --data D --out /opt/ctlwork/bm_tasks/cchard --manifest M --cc40-manifest M40
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

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build_cc40 as B  # noqa: E402

MAX_TASKS = 40
MIN_RATING = 2400
CXX = ["g++", "-O2", "-std=gnu++17"]

TEST_TEMPLATE = r'''"""Tests for the solution (solution.cpp if present, else solution.py; reads stdin, writes stdout). One test per case;
output compared after whitespace normalisation (whitespace-separated tokens must be equal)."""
import hashlib
import json
import os
import resource
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = "@DATA@"
_DATA_SHA256 = "@SHA@"
_LIMIT_S = @LIMIT@
_N = @N@
_state = {"timeouts": 0, "cases": None, "cmd": None, "cerr": None}


def _cases():
    if _state["cases"] is None:
        raw = open(os.path.join(_HERE, _DATA), "rb").read()
        if hashlib.sha256(raw).hexdigest() != _DATA_SHA256:
            raise AssertionError("data file %s was modified" % _DATA)
        _state["cases"] = json.loads(raw)
    return _state["cases"]


def _prepare():
    if _state["cmd"] is not None or _state["cerr"] is not None:
        return
    src = os.path.join(_HERE, "solution.cpp")
    if os.path.isfile(src):
        out = os.path.join(tempfile.mkdtemp(prefix="solbin-"), "sol")
        try:
            p = subprocess.run(["g++", "-O2", "-std=gnu++17", "-o", out, src], capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            _state["cerr"] = "compile timed out (60s)"
            return
        if p.returncode != 0:
            _state["cerr"] = "compile error: " + p.stderr[:400]
            return
        _state["cmd"] = [out]
    else:
        _state["cmd"] = [sys.executable, "solution.py"]


def _limits():
    resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))


def _clip(s, n=240):
    return s if len(s) <= n else s[:n] + "...(%d chars)" % len(s)


def _run_case(tc, i):
    if _state["timeouts"] >= 3:
        tc.fail("skipped: 3 earlier cases timed out in this run")
    case = _cases()[i]
    _prepare()
    if _state["cerr"]:
        tc.fail(_state["cerr"])
    try:
        p = subprocess.run(_state["cmd"], input=case["input"], capture_output=True, text=True,
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

CONTRACT = """# Contract

Write your solution to `solution.py` (Python 3) or `solution.cpp` (C++17) in the root of this workspace, as you prefer.
`solution.py` exists as an empty stub. The program reads the input from standard input and prints the answer to
standard output, as the problem statement in `goal.md` describes.

- If `solution.cpp` exists it is compiled with `g++ -O2 -std=gnu++17` and run; otherwise `solution.py` is run with Python 3.
- Only the standard library of the language; do not install packages.
- The tests for this task are in `solution_test.py` (with their data in `cases.json`). The tests are correct;
  don't change them or the data. Each test runs the program on one input and compares the output with the
  expected output after whitespace normalisation. A test fails if the program takes longer than {limit} seconds
  on one input. Run them with:

      python3 -m pytest -q solution_test.py

  or, without pytest:

      python3 -m unittest solution_test.py
"""

GOAL_TMPL = """# {title}

Time limit per test: {tl} seconds. Memory limit: {ml} MB.

Write a program in Python 3 or C++17 that reads from standard input and writes to standard output.

{desc}
"""


def compile_cpp(code: str, td: pathlib.Path, name: str) -> str | None:
    src = td / f"{name}.cpp"
    src.write_text(code, encoding="utf-8")
    exe = td / name
    try:
        p = subprocess.run(CXX + ["-o", str(exe), str(src)], capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        return None
    return str(exe) if p.returncode == 0 else None


def run_cmd(cmd: list[str], inp: str, limit: float) -> tuple[str, float, str]:
    t0 = time.time()
    try:
        p = subprocess.run(cmd, input=inp, capture_output=True, text=True, timeout=limit)
    except subprocess.TimeoutExpired:
        return "tle", time.time() - t0, ""
    except Exception:
        return "rte", time.time() - t0, ""
    return ("ok" if p.returncode == 0 else "rte"), time.time() - t0, p.stdout


def validate(row: dict, pf: dict) -> dict:
    limit = pf["limit"]
    cases = pf["vis"] + pf["hid"]
    sols = [(l, s) for l, s in zip(row["solutions"]["language"], row["solutions"]["solution"]) if l in (2, 3)][:12]
    good, tried = [], []
    with tempfile.TemporaryDirectory(prefix="cchv-") as t:
        td = pathlib.Path(t)
        for si, (lang, code) in enumerate(sols):
            if lang == 3:
                f = td / f"s{si}.py"
                f.write_text(code, encoding="utf-8")
                cmd = ["python3", "-I", "-S", str(f)]
            else:
                exe = compile_cpp(code, td, f"s{si}")
                if exe is None:
                    tried.append({"idx": si, "lang": "cpp", "result": "compile_fail", "max_wall": 0})
                    continue
                cmd = [exe]
            mx, why = 0.0, "ok"
            for ci, c in enumerate(cases):
                st, w, out = run_cmd(cmd, c["input"], limit)
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
            tried.append({"idx": si, "lang": "py3" if lang == 3 else "cpp", "result": why, "max_wall": round(mx, 3)})
            if why == "ok":
                good.append((si, lang, code, mx))
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

    def put(path: pathlib.Path, text):
        path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))

    for sub, cases, dname in ((ws, pf["vis"], "cases.json"), (hid, pf["hid"], "hidden_cases.json")):
        data = json.dumps(cases, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        put(sub / dname, data)
        put(sub / "solution_test.py", TEST_TEMPLATE.replace("@DATA@", dname).replace("@SHA@", B.sha256_b(data))
            .replace("@LIMIT@", repr(lim_s)).replace("@N@", str(len(cases))))
    put(ws / "solution.py", "# TODO: write the solution here (read stdin, write stdout)\n")
    title = row["name"].split(". ", 1)[-1] if ". " in row["name"] else row["name"]
    ml = round(row["memory_limit_bytes"] / (1 << 20))
    put(ws / "goal.md", GOAL_TMPL.format(title=title, tl=f"{pf['tl']:g}", ml=ml, desc=row["description"].strip()))
    put(ws / "contract.md", CONTRACT.format(limit=lim_s))
    put(td / "instruction.txt", "Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file.\n")
    put(td / "scorer.py", B.scorer_template())
    return {str(p.relative_to(out)): B.sha256_b(p.read_bytes()) for p in sorted(td.rglob("*")) if p.is_file()}


def real_check(out: pathlib.Path, tid: str, lang: int, ref_code: str) -> dict:
    res = {}
    for label, code in (("ref", ref_code), ("stub", None)):
        with tempfile.TemporaryDirectory(prefix="cchr-") as t:
            w = pathlib.Path(t) / "w"
            shutil.copytree(out / tid / "workspace", w)
            if code is not None:
                (w / ("solution.py" if lang == 3 else "solution.cpp")).write_text(code, encoding="utf-8")
            p = subprocess.run(["python3", "-m", "unittest", "solution_test"], cwd=w, capture_output=True, text=True, timeout=1200)
            sp = subprocess.run([sys.executable, str(out / tid / "scorer.py"), str(out / tid / "hidden"), str(w)],
                                capture_output=True, text=True, timeout=1200)
            sc = json.loads(sp.stdout.strip().splitlines()[-1])
            res[label] = {"visible_ok": p.returncode == 0, "hidden_pass": sc["pass"], "hidden": f"{sc['tests_passed']}/{sc['tests_total']}"}
    res["ok"] = bool(res["ref"]["visible_ok"] and res["ref"]["hidden_pass"] and not res["stub"]["visible_ok"] and not res["stub"]["hidden_pass"])
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--cc40-manifest", required=True)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    import pyarrow.parquet as pq
    in40 = {t["task"] for t in json.loads(pathlib.Path(a.cc40_manifest).read_text())["tasks"]}
    out = pathlib.Path(a.out)
    parq, rows, seen = {}, [], set()
    for split in ("valid", "test"):
        f = next(pathlib.Path(a.data).glob(f"{split}*.parquet"))
        parq[f.name] = B.sha256_b(f.read_bytes())
        for r in pq.read_table(f).to_pylist():
            key = (r["cf_contest_id"], r["cf_index"])
            tid = f"cc_{key[0]}{key[1]}"
            if r["source"] != 2 or not r["cf_rating"] or r["cf_rating"] < MIN_RATING or key in seen or tid in in40:
                continue
            seen.add(key)
            r["_name"], r["_split"], r["_tid"] = r["name"], split, tid
            rows.append(r)
    excluded, cands = [], []
    for r in rows:
        pf, why = B.prefilter(r)
        if pf is None:
            excluded.append({"name": r["name"], "rating": r["cf_rating"], "reason": why})
        else:
            cands.append((r["cf_rating"], r["_tid"], r, pf))
    cands.sort(key=lambda x: (x[0], x[1]))
    print("rated>=2400 not in cc40:", len(rows), "prefilter ok:", len(cands), flush=True)
    qualified, vlog = [], []
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = [(c, ex.submit(validate, c[2], c[3])) for c in cands]
        for c, fu in futs:
            v = fu.result()
            ok = len(v["good"]) >= 2
            vlog.append({"task": c[1], "rating": c[0], "valid": ok, "tried": v["tried"], "n_solutions": v["n_solutions"]})
            if ok:
                qualified.append((c, v))
            else:
                excluded.append({"name": c[2]["name"], "rating": c[0], "reason": "validity:" + (";".join(x["result"] for x in v["tried"]) or "no_py3_or_cpp_solution")})
            print(c[1], c[0], "OK" if ok else "x", [x["result"] for x in v["tried"]][:6], flush=True)
    n_qual = len(qualified)
    qualified = qualified[:MAX_TASKS]
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    files, tasks = {}, []
    for (rating, tid, row, pf), v in qualified:
        files.update(write_task(out, tid, row, pf))
        si, lang, code, mx = v["good"][0]
        rc = real_check(out, tid, lang, code)
        tasks.append({"task": tid, "name": row["name"], "split": row["_split"], "rating": rating, "n_vis": len(pf["vis"]),
                      "n_hid": len(pf["hid"]), "time_limit_s": pf["tl"], "case_limit_s": pf["limit"], "ref_solution_idx": si,
                      "ref_lang": "py3" if lang == 3 else "cpp", "ref_max_case_wall_s": round(mx, 3),
                      "dropped_big": pf["dropped_big"], "n_dedup_tests": pf["n_dedup"], "real_check": rc})
        print(tid, rating, pf["limit"], rc["ok"], flush=True)
    man = {"bank_id": out.name, "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "seed": B.SEED,
           "parquet_sha256": parq, "n_rated_ge_2400_not_cc40": len(rows), "n_prefilter_ok": len(cands),
           "n_qualified_total": n_qual, "n_tasks": len(tasks), "tasks": tasks, "excluded": excluded,
           "validation_log": vlog, "files_sha256": files}
    pathlib.Path(a.manifest).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.manifest).write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
    bad = [t["task"] for t in tasks if not t["real_check"]["ok"]]
    print("qualified", n_qual, "built", len(tasks), "bad real_check:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
