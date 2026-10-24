#!/usr/bin/env python3
"""Grade final solutions against VISIBLE + HIDDEN tests (evaluation only).

This is NOT the gate. The gate was the visible suite run by `vacant run`
at acceptance time. Here we measure delivery quality: for each cell, run
the final solution.py (if present) against the full test set
(visible + hidden) and record per-case results.

Usage: python3 grade.py [cell ...]     # default: all cells in cells/
Writes cells/<name>/grade.json and rows.jsonl + summary.json in OUT.
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

OUT = pathlib.Path(os.environ.get(
    "SB_OUT", "/home/user1/dev/Vacant/runs/sb_qwen27_freshhint_20260925"))
PER_TEST_TIMEOUT_S = 30


def grade_one(tid: str, sol: pathlib.Path) -> dict:
    t = json.loads((OUT / "tasks" / f"{tid}.json").read_text(encoding="utf-8"))
    ep = t["entry_point"]
    rec = {"task_id": tid, "entry_point": ep,
           "n_visible": len(t["visible"]), "n_hidden": len(t["hidden"]),
           "visible_ok": None, "full_ok": None, "cases": []}
    if not sol or not sol.exists():
        rec["error"] = "no final_solution.py in this cell"
        return rec

    def run_case(idx: str, args, expected) -> dict:
        # python -I (isolated ⇒ safe path) drops the script dir from sys.path,
        # so the probe bootstraps its own path — same shape as the gate driver
        # (acceptance.py DRIVER_SRC: sys.path.insert(0, WS)).
        src = ("import os, sys\n"
               "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
               f"from solution import {ep}\n"
               f"got = {ep}({', '.join(repr(a) for a in args)})\n"
               f"exp = {expected!r}\n"
               f"assert got == exp, f'MISMATCH: got={{got!r}} exp={{exp!r}}'\n")
        with tempfile.TemporaryDirectory(prefix="sbgrade_") as d:
            ws = pathlib.Path(d)
            (ws / "solution.py").write_bytes(sol.read_bytes())
            (ws / "_probe.py").write_text(src, encoding="utf-8")
            p = subprocess.run(
                [sys.executable, "-I", str(ws / "_probe.py")],
                cwd=ws, capture_output=True, text=True,
                timeout=PER_TEST_TIMEOUT_S)
            ok = p.returncode == 0
            msg = "" if ok else (p.stderr or p.stdout)[-300:].strip()
            return {"case": idx, "ok": ok, "message": msg}

    vis_cases = [run_case(f"v{i}", c["args"], c["expected"])
                 for i, c in enumerate(t["visible"], 1)]
    hid_cases = [run_case(f"h{i}", c["args"], c["expected"])
                 for i, c in enumerate(t["hidden"], 1)]
    rec["cases"] = vis_cases + hid_cases
    rec["visible_ok"] = all(c["ok"] for c in vis_cases)
    rec["full_ok"] = all(c["ok"] for c in rec["cases"])
    return rec


def main() -> int:
    cells_dir = OUT / "cells"
    cells = sorted(p.name for p in cells_dir.iterdir() if p.is_dir()) if cells_dir.is_dir() else []
    if len(sys.argv) > 1:
        cells = sys.argv[1:]
    rows = []
    for name in cells:
        tid = name.split("__")[0]
        sol = cells_dir / name / "final_solution.py"
        rec = grade_one(tid, sol)
        rec["cell"] = name
        rec["arm"] = name.split("__")[1]
        (cells_dir / name / "grade.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        rows.append(rec)
        print(f"[{name}] visible={rec['visible_ok']} full={rec['full_ok']}",
              flush=True)
    (OUT / "rows.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
