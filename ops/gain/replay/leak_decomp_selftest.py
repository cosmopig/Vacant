#!/usr/bin/env python3
"""`leak_decomp.py` 的植入缺陷自檢——乾淨 PASS 單獨不算數。

每一項都把一份**唯讀快照的複本**改壞，要求尺翻成 BROKEN（rc=2）。
M7 是反向的：它證明判準 §四 的 P-R668-1 **沒有牙齒**（植入缺陷之後仍然 PASS），
這條結果本身就是 round668 的產物，不是自檢失敗。
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE / "leak_decomp.py"


def run(d: pathlib.Path, extra=()):
    return subprocess.run(
        [sys.executable, str(TOOL), "--run", str(d), *extra],
        capture_output=True, text=True)


def prep(src_rows: pathlib.Path, src_summary: pathlib.Path, tmp: pathlib.Path,
         mutate_rows=None, mutate_summary=None) -> pathlib.Path:
    d = pathlib.Path(tempfile.mkdtemp(dir=tmp))
    rows = [json.loads(l) for l in src_rows.read_text(encoding="utf-8").splitlines() if l.strip()]
    summary = json.loads(src_summary.read_text(encoding="utf-8"))
    if mutate_rows:
        rows = mutate_rows(rows)
    if mutate_summary:
        summary = mutate_summary(summary)
    (d / "rows.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    (d / "summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    return d


def force_terminal(summary):
    for a in summary["arms"].values():
        a["terminal"] = True
    return summary


def main() -> int:
    src_rows = pathlib.Path(sys.argv[1])
    src_summary = pathlib.Path(sys.argv[2])
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="leakdecomp_selftest_"))
    ok = True

    def first_conform(rows, fn):
        for r in rows:
            if r["arm"] == "CONFORM":
                fn(r)
                break
        return rows

    cases = [
        ("CLEAN  乾淨快照（未收官）",
         dict(), 0),
        ("M1  summary.leaked 被竄改 + terminal=True",
         dict(mutate_summary=lambda s: (force_terminal(s), s["arms"]["CONFORM"].update(
             {"leaked": s["arms"]["CONFORM"]["leaked"] + 3}), s)[-1]), 2),
        ("M2  一列 CONFORM 抽掉 accepted 欄位",
         dict(mutate_rows=lambda rows: first_conform(rows, lambda r: r.pop("accepted"))), 2),
        ("M3  accepted 變成字串 'False'（bool('False') 是 True）",
         dict(mutate_rows=lambda rows: first_conform(
             rows, lambda r: r.update({"accepted": "False"}))), 2),
        ("M4  CONFORM 的 task_id 重複（字典會安靜蓋掉）",
         dict(mutate_rows=lambda rows: rows + [
             dict(next(r for r in rows if r["arm"] == "CONFORM"))]), 2),
        ("M5  CONFORM 一列都沒有（安靜量不到）",
         dict(mutate_rows=lambda rows: [r for r in rows if r["arm"] != "CONFORM"]), 2),
        ("M6  summary.arms 少了受測臂",
         dict(mutate_summary=lambda s: (s["arms"].pop("CONFORM"), s)[-1]), 2),
        ("M7  rows 翻一列 meets_demand + terminal=True（跨來源該抓到）",
         dict(mutate_rows=lambda rows: first_conform(
             rows, lambda r: r.update({"meets_demand": not r["meets_demand"]})),
              mutate_summary=force_terminal), 2),
        ("M8  summary 少 accepted_and_meets_demand 欄位",
         dict(mutate_summary=lambda s: (
             s["arms"]["CONFORM"].pop("accepted_and_meets_demand"), s)[-1]), 2),
    ]

    for name, kw, want in cases:
        d = prep(src_rows, src_summary, tmp, **kw)
        p = run(d)
        got = p.returncode
        mark = "OK  " if got == want else "FAIL"
        if got != want:
            ok = False
        note = (p.stderr.strip().splitlines() or [""])[0][:110]
        print(f"{mark} {name}: rc={got}（要 {want}）  {note}")

    # M9（反向）：單源恆等式沒有牙齒——把 meets_demand 翻掉之後 leaked 與
    # measured−refused−deliv 會同步改變，恆等式照樣成立。用 terminal=False
    # （跨來源檢查降級成 skew）把跨來源那條擋掉，單獨看恆等式那條。
    d = prep(src_rows, src_summary, tmp,
             mutate_rows=lambda rows: first_conform(
                 rows, lambda r: r.update({"meets_demand": not r["meets_demand"]})))
    p = run(d)
    taut = p.returncode == 0
    print(f"{'OK  ' if taut else 'FAIL'} M9（反向）翻掉 meets_demand 但 terminal=False："
          f"rc={p.returncode}（要 0）⇒ 單源恆等式**沒有**抓到 ⇒ P-R668-1 是恆等式不是檢定")
    if not taut:
        ok = False

    shutil.rmtree(tmp, ignore_errors=True)
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
