#!/usr/bin/env python3
"""i1001 步驟 3：任務題庫（dabench／databench／polyglot_py）的 staged 樹上的計分器量具。零模型呼叫。

    python3 verify_task_banks.py --staged <staged 根> [--reference-root <task_banks_20260927 根>] --out verify_task_banks.json

和 `gauge_task3.py`（第二批的量具，逐字複製）同一組案例，但**跑的是 staged 樹裡的 `scorer.py` 與 `hidden/`**——
就是 cell.sh 會用的那一份，不是題庫原始目錄：
- reference：資料題＝`hidden/<id>/expected.json` 的標準答案寫成答案檔；polyglot＝官方參考解（`--reference-root` 才有；
  沒給就略過 polyglot 的正控制並在輸出記下 `positive_skipped`）；必須 pass:true。
- missing／empty／wrong／stub：必須 pass:false 且 scorer 有輸出 JSON（沒輸出＝那一格會被判 infra_void）。
- polyglot 另加 `ref_tampered_test`：參考解＋工作區測試檔被改壞 ⇒ 仍 pass:true（計分只用原件）。
任何一格不符預期都具名寫進 `failures`。只用標準函式庫（計分器自己要 pandas／numpy：databench）。
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

import gauge_task3 as G

BANKS = ("dabench", "databench", "polyglot_py")


def run_one(task_dir: pathlib.Path, answer_file: str, text: str | None, extra: dict | None = None) -> dict:
    ws = pathlib.Path(tempfile.mkdtemp(prefix="vt_"))
    try:
        shutil.copytree(task_dir / "workspace", ws, dirs_exist_ok=True)
        if text is not None:
            (ws / answer_file).write_text(text)
        for name, body in (extra or {}).items():
            (ws / name).write_text(body)
        p = subprocess.run([sys.executable, str(task_dir / "scorer.py"), str(task_dir / "hidden"), str(ws)],
                           capture_output=True, text=True, timeout=900, cwd=str(ws.parent))
        lines = [l for l in p.stdout.splitlines() if l.strip()]
        if not lines:
            return {"pass": None, "note": f"NO OUTPUT rc={p.returncode} stderr={p.stderr[-300:]}"}
        try:
            return json.loads(lines[-1])
        except ValueError:
            return {"pass": None, "note": f"bad json: {lines[-1][:200]}"}
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def cases_for(bank: str, tdir: pathlib.Path, ref_root: pathlib.Path | None):
    exp = json.loads((tdir / "hidden" / "expected.json").read_text())
    if bank == "polyglot_py":
        contract = (tdir / "workspace" / "contract.md").read_text()
        stub = contract.split("```python\n", 1)[1].split("\n```", 1)[0] + "\n"
        wrong = "# deliberately wrong\ndef _placeholder_not_the_real_api():\n    return None\n"
        sol = exp["solution_file"]
        ref = None
        if ref_root is not None and (ref_root / bank / "reference" / tdir.name / "example.py").is_file():
            ref = (ref_root / bank / "reference" / tdir.name / "example.py").read_text()
        cs = {"missing": (None, None), "empty": ("", None), "wrong": (wrong, None), "stub": (stub, None)}
        if ref is not None:
            cs["reference"] = (ref, None)
            test_name = next(p.name for p in (tdir / "workspace").iterdir() if p.name.endswith("_test.py"))
            cs["ref_tampered_test"] = (ref, {test_name: "def test_nothing():\n    pass\n"})
        return sol, cs
    if bank == "dabench":
        labels = exp["common_answers"]
        ref = "".join(f"@{n}[{v}]\n" for n, v in labels)
        wrong = "".join(f"@{n}[{G.perturb_dabench(v)}]\n" for n, v in labels)
    else:
        ref = exp["answer"] + "\n"
        wrong = G.wrong_answer_databench(exp["answer"], exp["type"]) + "\n"
    return "answer.txt", {"reference": (ref, None), "missing": (None, None), "empty": ("", None), "wrong": (wrong, None),
                          "stub": ("I could not determine the answer from the data provided.\n", None)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--staged", required=True, type=pathlib.Path)
    ap.add_argument("--reference-root", type=pathlib.Path)
    ap.add_argument("--banks", nargs="*", default=list(BANKS))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    a = ap.parse_args()
    expect_pass = {"reference": True, "ref_tampered_test": True}
    jobs = []
    for bank in a.banks:
        for tdir in sorted(p for p in (a.staged / bank).iterdir() if p.is_dir()):
            answer_file, cs = cases_for(bank, tdir, a.reference_root)
            for case, (text, extra) in cs.items():
                jobs.append((bank, tdir, answer_file, case, text, extra))

    def go(j):
        bank, tdir, af, case, text, extra = j
        got = run_one(tdir, af, text, extra)
        exp = expect_pass.get(case, False)
        return {"bank": bank, "id": tdir.name, "case": case, "expect_pass": exp, "got_pass": got.get("pass"),
                "ok": got.get("pass") is exp, "status": got.get("status"), "note": got.get("note")}

    with cf.ThreadPoolExecutor(a.workers) as ex:
        rows = list(ex.map(go, jobs))
    fails = [r for r in rows if not r["ok"]]
    summ = {}
    for b in a.banks:
        br = [r for r in rows if r["bank"] == b]
        pos = [r for r in br if r["expect_pass"]]
        neg = [r for r in br if not r["expect_pass"]]
        summ[b] = {"n_tasks": len({r["id"] for r in br}), "positive": f"{sum(r['ok'] for r in pos)}/{len(pos)}",
                   "negative": f"{sum(r['ok'] for r in neg)}/{len(neg)}", "n_failures": sum(1 for r in br if not r["ok"])}
    out = {"schema": "i1001.verify_task_banks/1", "summary": summ, "n_rows": len(rows), "n_failures": len(fails),
           "failures": fails, "python": sys.version.split()[0], "rows": rows}
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({"summary": summ, "n_failures": len(fails)}, ensure_ascii=False))
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
