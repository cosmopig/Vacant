#!/usr/bin/env python3
"""Per-task calibration table for cc40 (Haiku A arm, one run per task). Re-scores each delivered workspace with the
task's scorer.py to get hidden pass counts (independent of the harness's own grade record, which it also prints).

Usage: cc40_table.py --root <run root> --bank <bank> --manifest <MANIFEST> --outdir <dir>
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import subprocess
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--bank", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--outdir", required=True)
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
                            capture_output=True, text=True, timeout=600)
        sc = json.loads(sp.stdout.strip().splitlines()[-1])
        u = att.get("usage") or {}
        tok_in = (u.get("input") or 0)
        rows.append({"task": tid, "rating": t["rating"], "band": t["band"], "vis": f"{att['acc_passed']}/{att['acc_run']}",
                     "visok": bool(att["accept"]), "hid": f"{sc['tests_passed']}/{sc['tests_total']}", "hidpass": bool(sc["pass"]),
                     "harness_grade_pass": att.get("grade_pass"), "frac": round(sc["tests_passed"] / max(1, sc["tests_total"]), 3),
                     "wall": att["wall_s"], "tok_in_incl_cache": tok_in, "tok_out": u.get("output"), "calls": u.get("calls"),
                     "cost": u.get("cost_usd"), "void": cell.get("infra_void"), "timed_out": att.get("timed_out")})
    out.mkdir(parents=True, exist_ok=True)
    (out / "table.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    lines = ["| 題 | 評分帶 | 難度 | 驗收（可見）通過 | hidden 通過 | hidden 比例 | 牆鐘 s | 輸入 token（含快取） | 輸出 token | 費用 USD |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['task']} | {r['band']} | {r['rating']} | {r['vis']} | {r['hid']} | {r['frac']:.2f} | {r['wall']} | {r['tok_in_incl_cache']} | {r['tok_out']} | {r['cost']:.4f} |")
    tot = sum(r["cost"] or 0 for r in rows)
    lines.append("")
    lines.append(f"**hidden 全過 {sum(r['hidpass'] for r in rows)}/{len(rows)}**；harness 自己的評分記錄 {sum(bool(r['harness_grade_pass']) for r in rows)}/{len(rows)}；"
                 f"infra_void {sum(bool(r['void']) for r in rows)}；逾時 {sum(bool(r['timed_out']) for r in rows)}；總費用 ${tot:.4f}；"
                 f"牆鐘中位數 {statistics.median(r['wall'] for r in rows):.1f}s、平均 {statistics.mean(r['wall'] for r in rows):.1f}s、最長 {max(r['wall'] for r in rows):.1f}s。")
    lines.append("")
    lines.append("| 評分帶 | 題數 | hidden 全過 | 比率 | 費用 USD | 平均牆鐘 s |")
    lines.append("|---|---|---|---|---|---|")
    for b, lo, hi in man["bands"]:
        g = [r for r in rows if r["band"] == b]
        if g:
            lines.append(f"| {b} [{lo},{hi if hi < 10**8 else '∞'}) | {len(g)} | {sum(r['hidpass'] for r in g)} | {sum(r['hidpass'] for r in g) / len(g):.2f} | "
                         f"{sum(r['cost'] or 0 for r in g):.4f} | {statistics.mean(r['wall'] for r in g):.1f} |")
    (out / "CALIBRATION_haiku_cc40_A.md").write_text("# Haiku 校準：A 臂單次，cc40（code_contests 40 題；不進正式分析）\n\n" + "\n".join(lines) + "\n")
    print("\n".join(lines[-14:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
