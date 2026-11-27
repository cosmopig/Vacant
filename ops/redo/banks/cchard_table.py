#!/usr/bin/env python3
"""Per-task calibration table for cchard (Haiku A arm, one run per task): hidden counts via the task's scorer.py,
delivered language, and for failures a one-line type from the first failing hidden/visible test message.

Usage: cchard_table.py --root R --bank B --manifest M --outdir D
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import statistics
import subprocess
import sys
import tempfile


def first_failure(bank: pathlib.Path, tid: str, ws: pathlib.Path, which: str) -> str:
    with tempfile.TemporaryDirectory(prefix="cchf-") as t:
        w = pathlib.Path(t) / "w"
        shutil.copytree(ws, w)
        if which == "hidden":
            for f in (bank / tid / "hidden").iterdir():
                shutil.copy2(f, w / f.name)
        p = subprocess.run([sys.executable, "-m", "unittest", "solution_test"], cwd=w, capture_output=True, text=True, timeout=900)
        out = p.stderr
        for pat, name in (("compile error", "compile error"), ("time limit exceeded", "time limit"), ("runtime error", "runtime error"),
                          ("wrong answer", "wrong answer")):
            if pat in out:
                m = re.findall(r"(wrong answer|time limit exceeded|runtime error|compile error)", out)
                kinds = sorted(set(m))
                return name + (f" (also: {', '.join(k for k in kinds if k != pat)})" if len(kinds) > 1 else "")
        return "other"


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
        sp = subprocess.run([sys.executable, str(bank / tid / "scorer.py"), str(bank / tid / "hidden"), str(ws)],
                            capture_output=True, text=True, timeout=900)
        sc = json.loads(sp.stdout.strip().splitlines()[-1])
        cpp = (ws / "solution.cpp")
        py = (ws / "solution.py")
        stub = "# TODO: write the solution here (read stdin, write stdout)\n"
        lang = "cpp" if cpp.is_file() and cpp.stat().st_size > 0 else ("py" if py.is_file() and py.read_text() != stub else "none")
        ftype = None
        if not sc["pass"]:
            ftype = "no file" if lang == "none" else first_failure(bank, tid, ws, "hidden")
        u = att.get("usage") or {}
        rows.append({"task": tid, "rating": t["rating"], "lang": lang, "vis": f"{att['acc_passed']}/{att['acc_run']}",
                     "visok": bool(att["accept"]), "hid": f"{sc['tests_passed']}/{sc['tests_total']}", "hidpass": bool(sc["pass"]),
                     "harness_grade_pass": att.get("grade_pass"), "frac": round(sc["tests_passed"] / max(1, sc["tests_total"]), 3),
                     "wall": att["wall_s"], "tok_in_incl_cache": u.get("input"), "tok_out": u.get("output"), "calls": u.get("calls"),
                     "cost": u.get("cost_usd"), "void": cell.get("infra_void"), "timed_out": att.get("timed_out"), "failure": ftype})
    out.mkdir(parents=True, exist_ok=True)
    (out / "table.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    L = ["| 題 | 難度 | 交付語言 | 驗收（可見）通過 | hidden 通過 | hidden 比例 | 失敗型態 | 牆鐘 s | 輸入 token（含快取） | 輸出 token | 費用 USD |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['task']} | {r['rating']} | {r['lang']} | {r['vis']} | {r['hid']} | {r['frac']:.2f} | {r['failure'] or ''} | {r['wall']} | {r['tok_in_incl_cache']} | {r['tok_out']} | {r['cost']:.4f} |")
    tot = sum(r["cost"] or 0 for r in rows)
    npass = sum(r["hidpass"] for r in rows)
    L += ["", f"**hidden 全過 {npass}/{len(rows)}（{npass / len(rows):.1%}）**；harness 評分記錄 {sum(bool(r['harness_grade_pass']) for r in rows)}/{len(rows)}；"
          f"infra_void {sum(bool(r['void']) for r in rows)}；逾時 {sum(bool(r['timed_out']) for r in rows)}；總費用 ${tot:.4f}；"
          f"牆鐘中位數 {statistics.median(r['wall'] for r in rows):.1f}s、平均 {statistics.mean(r['wall'] for r in rows):.1f}s、最長 {max(r['wall'] for r in rows):.1f}s。"]
    (out / "CALIBRATION_haiku_cchard_A.md").write_text("# Haiku 校準：A 臂單次，cchard（評分 ≥2400；不進正式分析）\n\n" + "\n".join(L) + "\n")
    print("\n".join(L[-2:]))
    for r in rows:
        if not r["hidpass"]:
            print(r["task"], r["rating"], r["lang"], r["vis"], r["hid"], r["frac"], r["failure"])
    print("langs", {k: sum(1 for r in rows if r["lang"] == k) for k in ("cpp", "py", "none")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
