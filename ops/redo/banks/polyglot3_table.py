#!/usr/bin/env python3
"""Per-task serial hidden re-score of a polyglot3 calibration run (Haiku A arm, one run per task).

Usage: polyglot3_table.py --root R --bank B --manifest M --outdir D
Writes D/table.json and D/CALIBRATION.md; prints the headline. Hidden scoring = the task's own scorer.py, one task at a time.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    for k in ("root", "bank", "manifest", "outdir"):
        ap.add_argument("--" + k, required=True)
    a = ap.parse_args()
    root, bank, out = pathlib.Path(a.root), pathlib.Path(a.bank), pathlib.Path(a.outdir)
    man = json.loads(pathlib.Path(a.manifest).read_text())
    rows = []
    for t in man["tasks"]:
        tid = t["task"]
        cdir = root / "cells" / tid / "r1" / "A"
        cell = json.loads((cdir / "cell.json").read_text())
        att = cell["attempts"][-1]
        ws = cdir / f"attempt_{att['k']}" / "workspace"
        sp = subprocess.run([sys.executable, str(bank / tid / "scorer.py"), str(bank / tid / "hidden"), str(ws)], capture_output=True, text=True,
                            timeout=1500, env={**os.environ, "SUITE_TIMEOUT_S": "1200"})
        sc = json.loads(sp.stdout.strip().splitlines()[-1])
        rows.append({"task": tid, "lang": t["lang"], "exercise": t["exercise"], "n_vis": t["n_vis"], "n_hid": t["n_hid"],
                     "visible": f"{att.get('acc_passed')}/{att.get('acc_run')}", "hidden": f"{sc['tests_passed']}/{sc['tests_total']}",
                     "hidden_pass": bool(sc["pass"]), "status": sc.get("status"), "wall_s": att.get("wall_s"),
                     "accepted": att.get("accept")})
        print(tid, rows[-1]["hidden"], rows[-1]["hidden_pass"], flush=True)
    n, k = len(rows), sum(r["hidden_pass"] for r in rows)
    bylang = {}
    for r in rows:
        b = bylang.setdefault(r["lang"], [0, 0])
        b[1] += 1
        b[0] += r["hidden_pass"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "table.json").write_text(json.dumps({"n": n, "pass": k, "rate": k / n, "by_lang": bylang, "rows": rows}, indent=1))
    md = [f"hidden all-pass {k}/{n} = {100 * k / n:.1f}% (serial re-score); by language {bylang}", "",
          "| task | visible | hidden | pass | status |", "|---|---|---|---|---|"]
    md += [f"| {r['task']} | {r['visible']} | {r['hidden']} | {r['hidden_pass']} | {r['status']} |" for r in rows]
    (out / "CALIBRATION.md").write_text("\n".join(md) + "\n")
    print(f"HEADLINE {k}/{n} = {100 * k / n:.1f}%  {bylang}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
