#!/usr/bin/env python3
"""ctl_cal_table — ctl37 校準表（A 臂單次）。重新用每題 scorer.py 對交付的工作區獨立評分（hidden 半邊），
另列 harness 自己的評分紀錄、可見半邊通過數、牆鐘、token（Devin：沒有費用欄位）。

Usage: ctl_cal_table.py --root <run root> --bank <bank> --outdir <dir> [--title ...]
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
    ap.add_argument("--bank", default="/opt/ctlwork/bm_tasks/ctl37")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--title", default="校準：A 臂單次，ctl37")
    ap.add_argument("--name", default="CALIBRATION")
    a = ap.parse_args()
    root, bank, out = pathlib.Path(a.root), pathlib.Path(a.bank), pathlib.Path(a.outdir)
    man = json.loads((bank / "MANIFEST.json").read_text())
    rows = []
    for tid in sorted(man["tasks"]):
        cdir = root / "cells" / tid / "r1" / "A"
        try:
            cell = json.loads((cdir / "cell.json").read_text())
        except OSError:
            rows.append({"task": tid, "missing": True})
            continue
        att = cell["attempts"][-1] if cell.get("attempts") else None
        row = {"task": tid, "void": cell.get("infra_void"), "voids": cell.get("voids"), "n_attempts": cell.get("n_attempts")}
        if att is None:
            rows.append(row)
            continue
        ws = cdir / f"attempt_{att['k']}" / "workspace"
        sp = subprocess.run([sys.executable, str(bank / tid / "scorer.py"), str(bank / tid / "hidden"), str(ws)],
                            capture_output=True, text=True, timeout=600)
        sc = json.loads(sp.stdout.strip().splitlines()[-1])
        u = att.get("usage") or {}
        row.update({"vis": f"{att['acc_passed']}/{att['acc_run']}", "visok": bool(att["accept"]),
                    "hid": f"{sc['tests_passed']}/{sc['tests_total']}", "hidpass": bool(sc["pass"]),
                    "harness_grade_pass": att.get("grade_pass"),
                    "frac": round(sc["tests_passed"] / max(1, sc["tests_total"]), 3), "wall": att["wall_s"],
                    "tok_in_incl_cache": u.get("input"), "tok_out": u.get("output"), "calls": u.get("calls"),
                    "cache_read": u.get("cache_read"), "timed_out": att.get("timed_out"), "rc": att.get("rc"),
                    "workspace_changed": att.get("workspace_changed")})
        rows.append(row)
    out.mkdir(parents=True, exist_ok=True)
    (out / "table.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    ok = [r for r in rows if "hid" in r]
    L = ["| 題 | 可見驗收 | hidden 通過 | hidden 比例 | 牆鐘 s | 呼叫 | 輸入 token（含快取） | 輸出 token | 逾時 | void |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "hid" not in r:
            L.append(f"| {r['task']} | — | — | — | — | — | — | — | — | {r.get('void') or ('missing' if r.get('missing') else '—')} |")
            continue
        L.append(f"| {r['task']} | {r['vis']} | {r['hid']} | {r['frac']:.2f} | {r['wall']} | {r['calls']} | {r['tok_in_incl_cache']} | {r['tok_out']} | {r['timed_out']} | {r['void'] or ''} |")
    L.append("")
    if ok:
        L.append(f"**hidden 全過 {sum(r['hidpass'] for r in ok)}/{len(ok)}（分母＝有評分的題 {len(ok)}；總題數 {len(rows)}）**；"
                 f"hidden 通過比例平均 {statistics.mean(r['frac'] for r in ok):.3f}；可見驗收全過 {sum(r['visok'] for r in ok)}/{len(ok)}；"
                 f"harness 自己的評分 {sum(bool(r['harness_grade_pass']) for r in ok)}/{len(ok)}；"
                 f"infra_void {sum(bool(r.get('void')) for r in rows)}；逾時 {sum(bool(r['timed_out']) for r in ok)}；"
                 f"牆鐘中位數 {statistics.median(r['wall'] for r in ok):.1f}s、平均 {statistics.mean(r['wall'] for r in ok):.1f}s、最長 {max(r['wall'] for r in ok):.1f}s。")
    (out / f"{a.name}.md").write_text(f"# {a.title}\n\n" + "\n".join(L) + "\n")
    print("\n".join(L[-1:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
