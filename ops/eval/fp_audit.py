"""誤報率審計：用有 ground truth 的歷史重播庫量「合格交付被退回」的比率。

背景（ASSIGNMENT P1）：「先降誤報再談加規則」。本機唯一有 pass/fail ground truth 的
重播庫是 C37 dabstep 批次（2026-10-02，v3.7 代碼當時的檢查動作已錄在案）：
    ~/dev/ops/ref/c37_final.json
每格有：
    pass                 Harbor 評分器的對錯（ground truth）
    recorded_action_r1   第一次交件前檢查的動作（allow / continue＝退回）
    recorded_findings_r1 / _final   退回的發現（kind 在內）
    num_reviews          該格總共檢查幾次

**口徑**：`pass=True` 且當次動作＝`continue`（有退回）＝**誤報**（fp）。
pass=False 的退回是「對的方向」（至少把不合格的東西擋了），不算誤報，但單列統計。
注意：庫是 v3.7 時代的檢查結果；本腳本量的是**那一版**的誤報率，不是現行代碼的。
現行代碼要重放同一批原始會話才能量（原始會話不在本機，見 README 限制）。

用法：
    python3 ops/eval/fp_audit.py --bank ~/dev/ops/ref/c37_final.json [--md]

exit 0＝讀到庫並產出統計；2＝庫不存在或格式不合。
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path


def load(bank: Path) -> list[dict]:
    rows = json.loads(bank.read_text())
    if not isinstance(rows, list) or not rows:
        raise ValueError("bank must be a non-empty JSON list")
    need = {"cell", "pass", "recorded_action_r1"}
    if not need.issubset(rows[0]):
        raise ValueError(f"bank rows missing keys: {sorted(need - set(rows[0]))}")
    return rows


def audit(rows: list[dict]) -> dict:
    passed = [r for r in rows if r["pass"]]
    failed = [r for r in rows if not r["pass"]]

    def fpr1(rs: list[dict]) -> list[dict]:
        return [r for r in rs if (r.get("recorded_findings_r1")
                                  and r.get("recorded_action_r1") == "continue")]

    def fpfinal(rs: list[dict]) -> list[dict]:
        return [r for r in rs if r.get("recorded_findings_final")]

    def kinds(rs: list[dict], key: str) -> collections.Counter:
        c: collections.Counter = collections.Counter()
        for r in rs:
            for f in r.get(key) or []:
                c[f.get("kind", "?")] += 1
        return c

    fp1, fpf = fpr1(passed), fpfinal(passed)
    out = {
        "bank_cells": len(rows),
        "pass": len(passed), "fail": len(failed),
        "fp_r1_n": len(fp1), "fp_r1_rate": len(fp1) / len(passed) if passed else None,
        "fp_r1_kinds": dict(kinds(passed, "recorded_findings_r1")),
        "fp_final_n": len(fpf),
        "fp_final_rate": len(fpf) / len(passed) if passed else None,
        "fp_final_kinds": dict(kinds(passed, "recorded_findings_final")),
        "fp_final_cells": [
            {"cell": r["cell"],
             "kinds": [f.get("kind") for f in r["recorded_findings_final"]]}
            for r in fpf],
        "sent_back_on_pass_r1": sum(1 for r in passed
                                    if r.get("recorded_action_r1") == "continue"),
        "sent_back_on_fail_r1": sum(1 for r in failed
                                    if r.get("recorded_action_r1") == "continue"),
        "pass_total_sentback_any": sum(1 for r in passed
                                       if r.get("recorded_findings_r1")
                                       or r.get("recorded_findings_final")),
    }
    return out


def render_md(a: dict) -> str:
    lines = [
        "# C37 誤報審計（v3.7 時代檢查，ground truth＝Harbor 評分器）",
        "",
        f"- 庫：{a['bank_cells']} 格；pass {a['pass']} / fail {a['fail']}",
        f"- **R1 誤報**（pass 且第一次檢查就退回）：{a['fp_r1_n']} / {a['pass']}"
        f" ＝ {a['fp_r1_rate']:.2%}；按類：{a['fp_r1_kinds']}",
        f"- **最終誤報**（pass 但最終仍被退回）：{a['fp_final_n']} / {a['pass']}"
        f" ＝ {a['fp_final_rate']:.2%}；按類：{a['fp_final_kinds']}",
        f"- 對照：fail 格第一次就被退回 {a['sent_back_on_fail_r1']} / {a['fail']}"
        f"（擋住不合格，方向正確）；pass 格全程至少被退過一次 {a['pass_total_sentback_any']} / {a['pass']}",
        "",
        "## 最終誤報逐格",
        "",
        "| cell | 退回類 |",
        "|---|---|",
    ]
    for c in a["fp_final_cells"]:
        lines.append(f"| {c['cell']} | {', '.join(c['kinds'])} |")
    lines += [
        "",
        "## 口徑限制",
        "",
        "1. 庫是 2026-10-02 v3.7 時代的**記錄**；現行代碼未在此庫上重放（原始會話不在本機）。",
        "2. `pass` 是 Harbor 評分器判定；它本身可能漏判（H-2 同構：過評分器≠滿足需求）。",
        "3. R1 誤報在 num_reviews>1 的格可能被後續回合救回（最終誤報才是留在分母裡的傷害）。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bank", required=True)
    ap.add_argument("--md", action="store_true", help="輸出 markdown 而非 JSON")
    a = ap.parse_args()
    p = Path(a.bank).expanduser()
    try:
        rows = load(p)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"bank 讀不到或格式不合：{e}", file=sys.stderr)
        return 2
    out = audit(rows)
    print(render_md(out) if a.md else json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
