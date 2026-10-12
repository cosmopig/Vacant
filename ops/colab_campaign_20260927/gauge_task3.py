#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第二批（任務導向三題庫）的計分器量具：對每一題，把正控制（參考答案／參考解）與四種負控制
（沒交、空檔、錯答案、stub）放進一份工作區副本，跑 staged 的 `scorer.py`（`scorers/<bank>.py`），
量「判成 0 之前先證明量得動」（`PLAN_BATCH2_TASK3.md` 步驟 4；記憶
`instruments-lie-before-you-conclude-zero.md`）。**零模型呼叫**，只跑計分器本身。

正控制的答案／解**直接取自 `hidden/<id>/expected.json`（資料題）或 `reference/<id>/example.py`
（polyglot）**，不重新執行參考解——三個 pilot 各自的 `gauge_bank.py` 已經驗過這兩者算滿分
（README §五：`label_verbatim`／官方參考解 30/30、30/30、34/34），這裡只驗**新介面**
（cell.sh 的位置參數＋`scorer.py`）沒有把判準搬壞。

負控制：
- `missing`：工作區沒有答案／解答檔。
- `empty`：答案／解答檔存在但是空的。
- `wrong`：依型別造的錯答案（資料題）／不含必要符號的占位解（polyglot，對 34 題通用）。
- `stub`：一句「我不知道」的自由文字（資料題）／官方骨架（polyglot，contract.md 裡逐字貼的那份，
  NotImplementedError；README 記過官方 stub 在 3 題會拿到部分測試分但主指標 `pass` 仍是 0）。

任何一題任何一格 `pass` 不符預期 ⇒ 具名寫進 `failures`，不安靜丟掉（步驟 4）。
結果印出摘要並寫 `task3_gauge.json`（每題每種輸入一列）。

用法：
    python3 gauge_task3.py --banks-root <ops/vacantrun/task_banks_20260927 的路徑> \
        --scorers-root <ops/colab_campaign_20260927/scorers 的路徑> --out task3_gauge.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent


def run_scorer(scorer: pathlib.Path, hidden_dir: pathlib.Path, workspace: pathlib.Path) -> dict:
    p = subprocess.run([sys.executable, str(scorer), str(hidden_dir), str(workspace)],
                        capture_output=True, text=True, timeout=120)
    lines = [ln for ln in p.stdout.splitlines() if ln.strip()]
    if not lines:
        return {"pass": False, "note": f"NO OUTPUT (rc={p.returncode}); stderr={p.stderr[-500:]}"}
    try:
        return json.loads(lines[-1])
    except ValueError:
        return {"pass": False, "note": f"unparseable stdout last line: {lines[-1]!r}"}


# ── 資料題（dabench／databench）的答案造法 ─────────────────────────────

def perturb_dabench(v: str) -> str:
    """出處：ops/vacantrun/task_banks_20260927/dabench/gauge_bank.py::perturb（逐字）。"""
    try:
        x = float(v)
    except ValueError:
        return v + "_x"
    return repr(x + 1.0 + abs(x) * 0.5)


def wrong_answer_databench(truth: str, typ: str) -> str:
    """出處：ops/vacantrun/task_banks_20260927/databench/gauge_bank.py::wrong_answer（逐字）。"""
    if typ == "boolean":
        return "False" if truth.strip().lower() in ("true", "yes", "y") else "True"
    if typ == "number":
        x = float("".join(c for c in truth if c.isdigit() or c in ".-"))
        return repr(x * 1.5 + 1.0)
    if typ == "category":
        return "zzz_not_a_value"
    items = [s.strip() for s in truth.strip("[]").split(",")]
    if typ == "list[number]":
        items[0] = repr(float("".join(c for c in items[0] if c.isdigit() or c in ".-")) + 1000.5)
        return "[" + ", ".join(items) + "]"
    items[0] = "'zzz_not_a_value'"
    return "[" + ", ".join(items) + "]"


def data_cases(bank: str, tid: str, templates: pathlib.Path, hidden: pathlib.Path) -> dict[str, str | None]:
    exp = json.loads((hidden / tid / "expected.json").read_text())
    if bank == "dabench":
        labels = exp["common_answers"]
        reference = "".join(f"@{n}[{v}]\n" for n, v in labels)
        wrong = "".join(f"@{n}[{perturb_dabench(v)}]\n" for n, v in labels)
    else:
        reference = exp["answer"] + "\n"
        wrong = wrong_answer_databench(exp["answer"], exp["type"]) + "\n"
    return {"reference": reference, "missing": None, "empty": "",
            "wrong": wrong, "stub": "I could not determine the answer from the data provided.\n"}


def code_cases(tid: str, templates: pathlib.Path, hidden: pathlib.Path,
               reference: pathlib.Path) -> tuple[dict[str, str | None], str]:
    exp = json.loads((hidden / tid / "expected.json").read_text())
    sol_file = exp["solution_file"]
    ref_src = (reference / tid / "example.py").read_text()
    contract = (templates / tid / "contract.md").read_text()
    stub = contract.split("```python\n", 1)[1].split("\n```", 1)[0] + "\n"
    wrong = "# deliberately wrong: does not define the names the tests import\n" \
            "def _placeholder_not_the_real_api():\n    return None\n"
    return {"reference": ref_src, "missing": None, "empty": "", "wrong": wrong,
            "stub": stub}, sol_file


def write_case(ws: pathlib.Path, filename: str, text: str | None) -> None:
    if text is None:
        return
    (ws / filename).write_text(text)


def gauge_bank(bank: str, banks_root: pathlib.Path, scorers_root: pathlib.Path) -> list[dict]:
    templates, hidden = banks_root / bank / "templates", banks_root / bank / "hidden"
    scorer = scorers_root / f"{bank}.py"
    is_code = bank == "polyglot_py"
    reference = banks_root / bank / "reference" if is_code else None
    rows = []
    for tid in sorted(p.name for p in templates.iterdir() if p.is_dir()):
        if is_code:
            cases, answer_file = code_cases(tid, templates, hidden, reference)
        else:
            cases, answer_file = data_cases(bank, tid, templates, hidden), "answer.txt"
        expect = {"reference": True, "missing": False, "empty": False, "wrong": False, "stub": False}
        for case, text in cases.items():
            ws = pathlib.Path(tempfile.mkdtemp(prefix=f"gauge_{bank}_"))
            try:
                shutil.copytree(templates / tid, ws, dirs_exist_ok=True)
                write_case(ws, answer_file, text)
                got = run_scorer(scorer, hidden / tid, ws)
            finally:
                shutil.rmtree(ws, ignore_errors=True)
            ok = bool(got.get("pass")) == expect[case]
            rows.append({"bank": bank, "id": tid, "case": case, "expect_pass": expect[case],
                         "got_pass": got.get("pass"), "ok": ok, "note": got.get("note"),
                         "status": got.get("status")})
            mark = "OK " if ok else "BAD"
            print(f"{mark} {bank:12s} {tid:20s} {case:10s} expect={expect[case]!s:5s} "
                  f"got={got.get('pass')!s:5s} {got.get('note') or ''}")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--banks-root", required=True, type=pathlib.Path)
    ap.add_argument("--scorers-root", required=True, type=pathlib.Path)
    ap.add_argument("--out", default=str(HERE / "task3_gauge.json"))
    a = ap.parse_args()

    all_rows = []
    for bank in ("dabench", "databench", "polyglot_py"):
        all_rows.extend(gauge_bank(bank, a.banks_root, a.scorers_root))

    failures = [r for r in all_rows if not r["ok"]]
    summary = {}
    for bank in ("dabench", "databench", "polyglot_py"):
        brows = [r for r in all_rows if r["bank"] == bank]
        pos = [r for r in brows if r["case"] == "reference"]
        neg = [r for r in brows if r["case"] != "reference"]
        summary[bank] = {
            "n_tasks": len({r["id"] for r in brows}),
            "positive_control": f"{sum(r['ok'] for r in pos)}/{len(pos)}",
            "negative_control": f"{sum(r['ok'] for r in neg)}/{len(neg)}",
            "n_failures": sum(1 for r in brows if not r["ok"]),
        }
    out = {"summary": summary, "n_rows": len(all_rows), "n_failures": len(failures),
           "failures": failures, "rows": all_rows}
    pathlib.Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"failures: {len(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
