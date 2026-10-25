#!/usr/bin/env python3
"""c37 重放：「失敗之後再重抽 N 次」能救回多少？（cap = 3）

資料：/home/user1/dev/ops/ref/c37_final.json（C37 的 replay 結果，1187 格；
pi 上 Vacant 0.7.1，review 模式）。每格 = 一次完整 agent 執行
（cell 名 b1-polyglot_py-... 裡含 batch 與 suite）。

重抽是「全新執行」，不是「讀到失敗訊號再重試」：所以這量的是**上界**
（重抽會重抽到對的機率），不是「Vacant 回饋」的效果——
見 ops/ref/offline_restart_sim 的舊註與 NEXT_AGENT_TASKS 2026-10-24。

  pass@1            第一次就過的單元比例（baseline）
  flag-restart (cap K)  第一次 findings_final 為空的單元，依序看第 2..K+1 次
                        （**不用評分器**：findings_final 是 Vacant 自己的 review 訊號）
  test-restart (cap K)  第一次 pass==false 的單元，依序看第 2..K+1 次
                        （訊號＝評分器的 pass；是否 reachable 見下）
  oracle@k            K 次內任一次 pass==true（無條件上界）

⚠ 每一格都是**獨立執行**（不同 batch），不是同一個工作區的連續重試；
  所以「runs」平均是「第幾次**獨立**執行才過」，不能當「重試幾次就過」。

## 誠實邊界：哪一欄可引用（2026-10-24 加入，見 tests/test_c37_restart_sim_honesty.py）

`pass` 欄來自評測的（隱藏）`score.json`。test-restart 欄能不能引用為
「可見測試驅動」的成效，取決於 **agent 自己拿不拿得到同一個訊號**：

- `polyglot_py`：題目的工作區裡有**可見的測試檔**（例如
  `bm_tasks/polyglot_py/pg_affine_cipher/workspace/affine_cipher_test.py`），
  而評分器 status 是 `pass`/`fail`——跑的就是那一份測試
  （ASSIGNMENT 2026-10-24：「polyglot_py 的可見測試 == 評分器」）
  → test-restart 欄 **reachable**，可引用。
- `dabstep`/`dabench`/`databench`：沒有可執行可見測試；
  `answer.txt` 與**隱藏**參考答案比對（status 是 `ok`/`missing`）
  → test-restart 欄是 **oracle 上界**，**不可引用為 Vacant 成效**。
- `ALL` 的 test-restart：兩類混池 → 同樣不可引用。

flag-restart 欄不用評分器（Vacant 自己的 findings_final），每個 suite 都成立。

規則（fail-closed）：只有 `VISIBLE_TESTS_ARE_GRADER` 裡**明確驗證過**
「可見測試＝評分器」的 suite 才可引用；新 suite 不在此集合＝當上界。

本檔是這把尺的**唯一正典**（git 版，有測試鎖住）。
`/home/user1/dev/ops/ref/offline_restart_sim.py` 只是 shim。
"""
from __future__ import annotations

import json
import pathlib
import sys

#: 驗證過「可見測試＝評分器」的 suite（證據見模組 docstring）。
#: 新 suite 未驗證前不進這裡——fail-closed 當上界。
VISIBLE_TESTS_ARE_GRADER = frozenset({"polyglot_py"})


def _flagged(findings) -> bool:
    """`findings_final` 非空＝Vacant 那一跑有旗標（重啟訊號，不用評分器）。"""
    try:
        return len(list(findings or [])) > 0
    except TypeError:
        return bool(findings)


def _first_pass_index(cells, cap):
    """前 `cap` 格內，第一格 pass 的 0-based 下標；找不到＝None。"""
    for i in range(min(cap, len(cells))):
        if bool(cells[i].get("pass")):
            return i
    return None


def _first_flag_free_index(cells, cap):
    """前 `cap` 格內，第一格 findings_final 為空的 0-based 下標；找不到＝None。"""
    for i in range(min(cap, len(cells))):
        if not _flagged(cells[i].get("findings_final")):
            return i
    return None


def _oracle_passes(cells, cap) -> bool:
    """前 `cap` 格里，任一格 pass。"""
    return any(bool(c.get("pass")) for c in cells[:cap])


def _test_signal(suite_set: set, visible_are_grader: frozenset) -> str:
    """一組 suite 的 test-restart 欄：reachable 還是上界？

    - 全部「可見測試＝評分器」 → `visible==grader`（可引用）
    - 全部不是                → `hidden-grader(UB)`（上界）
    - 混                      → `mixed(UB)`（上界；不可當成效引用）
    """
    if not suite_set:
        return "no-suites"
    if suite_set <= visible_are_grader:
        return "visible==grader"
    if not (suite_set & visible_are_grader):
        return "hidden-grader(UB)"
    return "mixed(UB)"


def _col(idx_list, cap):
    """一欄的統計：(過了的單元數, 單元數, pct, 平均第幾次)。與舊版同語意。"""
    oks = [i for i in idx_list if i is not None]
    n = len(idx_list)
    pct = 100.0 * len(oks) / n if n else 0.0
    avg = sum(min(cap, i + 1) for i in oks) / len(oks) if oks else 0.0
    return len(oks), n, pct, avg


def _row(sel, cap, sig):
    n = len(sel)
    cells = sum(len(v) for v in sel)
    _, _, p_pct, _ = _col([_first_pass_index(v, 1) for v in sel], cap)
    _, _, f_pct, f_avg = _col([_first_flag_free_index(v, cap) for v in sel], cap)
    _, _, t_pct, t_avg = _col([_first_pass_index(v, cap) for v in sel], cap)
    _, _, o_pct, _ = _col([0 if _oracle_passes(v, cap) else None for v in sel], cap)
    return {
        "cells": cells, "units": n,
        "pass1_pct": round(p_pct, 1), "flag_pct": round(f_pct, 1),
        "flag_runs": round(f_avg, 2),
        "test_pct": round(t_pct, 1), "test_runs": round(t_avg, 2),
        "oracle_pct": round(o_pct, 1),
        "test_signal": sig,
    }


def simulate(rows, cap, visible_are_grader: frozenset = VISIBLE_TESTS_ARE_GRADER) -> dict:
    """結構化結果（可存檔、可比對）；`render()` 負責排版。

    回傳：
      rows:         每 suite + ALL：五欄數字 + test_signal 標註
      citable:      可引用的重抽數字（帶 n_cells/n_units/cap，uses_scorer=False）
      upper_bounds: 不可引用為成效的 test-restart 欄（上界，帶理由）
    """
    groups: dict = {}
    for r in rows:
        parts = str(r["cell"]).split("-")
        if len(parts) < 2:
            continue
        key = (parts[1], parts[0], r.get("task_dir"))
        groups.setdefault(key, []).append(r)

    # 重抽/重試語意要求 ≥2 個獨立執行；單次的只進 pass@1 的母體沒意義
    groups = {k: v for k, v in groups.items() if len(v) >= 2}

    suites = sorted({k[0] for k in groups})
    rows_out: dict = {}
    for s in suites:
        sel = [v for k, v in groups.items() if k[0] == s]
        rows_out[s] = _row(sel, cap, _test_signal({s}, visible_are_grader))
    rows_out["ALL"] = _row(list(groups.values()), cap,
                           _test_signal(set(suites), visible_are_grader))

    citable = []
    for s in suites + ["ALL"]:
        r = rows_out[s]
        citable.append({
            "suite": s, "signal": "vacant-flag",
            "pass1_pct": r["pass1_pct"], "flag_pct": r["flag_pct"],
            "n_cells": r["cells"], "n_units": r["units"], "cap": cap,
            "uses_scorer": False,
            "note": "Vacant 自己的 findings_final 訊號（不用評分器）",
        })
    for s in suites + ["ALL"]:
        r = rows_out[s]
        if r["test_signal"] == "visible==grader":
            citable.append({
                "suite": s, "signal": "visible-test",
                "pass1_pct": r["pass1_pct"], "test_pct": r["test_pct"],
                "n_cells": r["cells"], "n_units": r["units"], "cap": cap,
                "uses_scorer": False,
                "note": "可見測試＝評分器（agent 自己拿得到這個訊號）",
            })

    upper_bounds = [
        {"suite": s, "column": "test-restart", "pct": rows_out[s]["test_pct"],
         "reason": "該欄的重啟訊號含隱藏評分器的判斷（oracle 上界），不是 reachable"}
        for s in suites + ["ALL"] if rows_out[s]["test_signal"] != "visible==grader"
    ]

    return {"cap": cap, "rows": rows_out,
            "citable": citable, "upper_bounds": upper_bounds}


def render(res) -> str:
    cap = res["cap"]
    L = [
        f"cap={cap}  (units = (batch, task) groups with >=2 independent runs)",
        "",
        f"{'suite':<12} {'units':>6}  {'pass@1':>8}  {'flag-restart':>12}  "
        f"{'runs':>5}  {'test-restart':>12}  {'runs':>5}  "
        f"{'test-signal':<18}  {'oracle@k':>8}",
    ]
    order = [s for s in res["rows"] if s != "ALL"] + (["ALL"] if "ALL" in res["rows"] else [])
    for s in order:
        r = res["rows"][s]
        L.append(
            f"{s:<12} {r['units']:>6}  {r['pass1_pct']:>7.1f}%  {r['flag_pct']:>11.1f}%  "
            f"{r['flag_runs']:>5.2f}  {r['test_pct']:>11.1f}%  {r['test_runs']:>5.2f}  "
            f"{r['test_signal']:<18}  {r['oracle_pct']:>7.1f}%"
        )
    L += [
        "",
        "—— 可引用（reachable，未用隱藏評分器）——",
        "  vacant-flag 驅動重抽（flag-restart 欄；訊號＝Vacant 自己的 findings_final）:",
    ]
    for c in res["citable"]:
        if c["signal"] != "vacant-flag":
            continue
        L.append(f"    {c['suite']:<12} {c['pass1_pct']:>5.1f}% -> {c['flag_pct']:>5.1f}%   "
                 f"(n={c['n_cells']} cells / {c['n_units']} units, cap={c['cap']})")
    L.append("  visible-test 驅動重抽（test-restart 欄；僅「可見測試＝評分器」的 suite）:")
    vis = [c for c in res["citable"] if c["signal"] == "visible-test"]
    if vis:
        for c in vis:
            L.append(f"    {c['suite']:<12} {c['pass1_pct']:>5.1f}% -> {c['test_pct']:>5.1f}%   "
                     f"(n={c['n_cells']} cells / {c['n_units']} units, cap={c['cap']})")
    else:
        L.append("    （無：沒有 suite 驗證過「可見測試＝評分器」）")
    L += [
        "",
        "—— 不可引用為成效（test-restart 欄含隱藏評分器訊號，只是 oracle 上界）——",
    ]
    if res["upper_bounds"]:
        for u in res["upper_bounds"]:
            L.append(f"  test-restart @ {u['suite']:<12}: {u['pct']:.1f}%   "
                     f"({res['rows'][u['suite']]['test_signal']})")
    else:
        L.append("  （無）")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    path = pathlib.Path(argv[0])
    cap = int(argv[1]) if len(argv) > 1 else 3
    rows = json.loads(path.read_text())
    if isinstance(rows, dict):
        rows = rows.get("cells") or rows.get("rows") or []
    print(render(simulate(rows, cap=cap)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
