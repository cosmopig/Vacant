#!/usr/bin/env python3
"""離線重播（零模型調用）：「真實訊號驅動的重抽」能做到什麼，哪一欄是上界。

背景（P1 主線，round 98）：
  過去量到增益的是「真的訊號（可執行驗收）＋重來的權力（乾淨重抽）」。
  但 `ref/offline_restart_sim.py` 的 test-restart 欄用**評分器的對錯**決定要不要重抽，
  在可見測試≠評分器的題型上幾乎等於 oracle@k——是上界，不是 Vacant 自己能做到的。
  本腳本把同一份檔案（c37_final.json 形狀：每格一行 cell/task_dir/pass/findings_final）
  重播成**每欄帶 scorer_used 標記**的機器輸出：

  - flag_restart ：以 Vacant 自己的紀錄訊號（findings 為空＝放行）決定停止重抽。
                   scorer_used=false。這是「真實訊號驅動重抽」的可引用欄。
  - test_restart ：以檔案裡的 grader pass 決定停止重抽。
                   **只有**在可見測試就是評分器的題型（polyglot_py）上 scorer_used=false
                   （那是客戶自己的可執行驗收）；其餘題型 scorer_used=true＝上界，
                   不得引用為 Vacant 自己能做到的。
  - oracle_any   ：組內任意一次 archived run 過即算過。永遠 scorer_used=true（上界）。

口徑（與 NEXT_AGENT_TASKS.md 2026-10-24 CAUTION、~/dev/ops/ASSIGNMENT.md 誠實現況第 2 條
一致）：
  - +15.4pp（62.3→77.7）是 test-restart 欄＝用評分器決定重抽，不得引用當成效。
  - 可引用的真實訊號欄：ALL 62.3→66.4（flag-restart +4.1pp）；polyglot_py 37.3→47.0。
  - polyglot_py 可見測試＝評分器，其 test-restart（55.9）也是真的拿得到——但**只在該題型**。

算法與 `ref/offline_restart_sim.py` 相同（每組對所有 cyclic 起點取平均、cap K、
組＝(suite, batch, task) 且需 ≥2 次獨立 archived run、每組等權）。本腳本不改數字，
只把「哪一欄用了評分器」寫進機器輸出並用 --selftest 釘死。

用法：
  python3 ops/realrun/offline_real_signal_replay.py --selftest
  python3 ops/realrun/offline_real_signal_replay.py <replay.json> [K] [--json]
  python3 ops/realrun/offline_real_signal_replay.py <replay.json> [K] --write-mirror <path>
"""
from __future__ import annotations

import collections
import hashlib
import json
import sys
from pathlib import Path

SCHEMA = "vacant.realrun.offline_real_signal_replay/1"

# 可見測試就是評分器的題型：該處 test_restart 是客戶自己的可執行驗收（真實訊號），
# 不是上界。其餘題型的 pass 欄是 grader 判定，agent 看不到那個測試。
# 來源：~/dev/ops/ASSIGNMENT.md 誠實現況第 2 條、NEXT_AGENT_TASKS.md CAUTION（2026-10-24）。
VISIBLE_TESTS_ARE_GRADER = ("polyglot_py",)


def simulate(cells: list[dict], stop_ok, cap: int) -> tuple[float, float]:
    """Average over every starting offset: returns (expected pass, expected #runs)."""
    tp = tc = 0.0
    n = len(cells)
    for i in range(n):
        seq = [cells[(i + j) % n] for j in range(min(cap, n))]
        for j, c in enumerate(seq):
            if stop_ok(c) or j == len(seq) - 1:
                tp += c["pass"]
                tc += j + 1
                break
    return tp / n, tc / n


def group_rows(rows: list[dict]) -> dict[tuple[str, str, str], list[dict]]:
    groups: dict[tuple[str, str, str], list[dict]] = collections.defaultdict(list)
    for r in rows:
        if "error" in r:
            continue
        suite = r["task_dir"].rstrip("/").split("/")[-2]
        batch = r["cell"].split("-")[0]
        groups[(suite, batch, r["task_dir"])].append(r)
    return groups


def scorer_flag_for(suite: str, column: str) -> bool:
    """該欄在該題型上是否用了評分器（grader）作為驅動訊號。"""
    if column == "flag_restart":
        return False
    if column == "oracle_any":
        return True
    if column == "test_restart":
        return suite not in VISIBLE_TESTS_ARE_GRADER
    raise ValueError(column)


def replay(rows: list[dict], cap: int = 3) -> dict:
    groups = group_rows(rows)
    agg: dict[str, list[float]] = collections.defaultdict(lambda: [0.0] * 7)
    for (suite, _batch, _t), cells in groups.items():
        if len(cells) < 2:
            continue
        cells.sort(key=lambda c: c["cell"])
        p1 = sum(c["pass"] for c in cells) / len(cells)
        fp, fc = simulate(cells, lambda c: not c.get("findings_final"), cap)
        tp, tc = simulate(cells, lambda c: c["pass"], cap)
        orc = 1.0 if any(c["pass"] for c in cells) else 0.0
        for key in (suite, "ALL"):
            a = agg[key]
            a[0] += 1
            a[1] += p1
            a[2] += fp
            a[3] += fc
            a[4] += tp
            a[5] += tc
            a[6] += orc

    def row(key: str, suite: str | None) -> dict:
        n, p1, fp, fc, tp, tc, orc = agg[key]
        return {
            "units": int(n),
            "pass_at_1_pct": round(100 * p1 / n, 2),
            "flag_restart": {
                "pct": round(100 * fp / n, 2), "mean_runs": round(fc / n, 4),
                "scorer_used": scorer_flag_for(suite, "flag_restart") if suite else False,
                "signal": "vacant_findings_empty",
            },
            "test_restart": {
                "pct": round(100 * tp / n, 2), "mean_runs": round(tc / n, 4),
                "scorer_used": scorer_flag_for(suite, "test_restart") if suite else True,
                "signal": "recorded_grader_pass",
            },
            "oracle_any": {
                "pct": round(100 * orc / n, 2),
                "scorer_used": True, "signal": "any_archived_run_passes",
            },
        }

    suites = {k: row(k, k) for k in sorted(agg) if k != "ALL"}
    return {
        "schema": SCHEMA,
        "cap": cap,
        "definition": {
            "unit": "(suite, batch, task) group with >=2 archived independent runs; groups weighted equally",
            "columns": {
                "pass_at_1": "one archived run, as recorded",
                "flag_restart": "rerun while Vacant's recorded findings are non-empty; real signal, no scorer",
                "test_restart": "rerun while the archived run failed the grader; real signal ONLY where visible tests are the grader, otherwise an upper bound",
                "oracle_any": "at least one archived run in the group passes; always an upper bound",
            },
            "visible_tests_are_grader_suites": list(VISIBLE_TESTS_ARE_GRADER),
            "quoting_rule": "flag_restart is the citable real-signal column. test_restart is citable only for suites in visible_tests_are_grader_suites. oracle_any and other test_restart values are upper bounds; quoting them as an achieved effect is a misstatement.",
        },
        "suites": suites,
        "all": row("ALL", None),
    }


def sha256_of(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def selftest() -> None:
    # 合成組：A(過不了, 有 findings) B(過不了, 無 findings) C(過, 無 findings)，cap=2。
    # 手算期望值（對所有 cyclic 起點取平均）：
    cells = [
        {"cell": "s-b-1", "pass": False, "findings_final": ["f"]},
        {"cell": "s-b-2", "pass": False, "findings_final": []},
        {"cell": "s-b-3", "pass": True, "findings_final": []},
    ]
    fp, fc = simulate(cells, lambda c: not c.get("findings_final"), 2)
    tp, tc = simulate(cells, lambda c: c["pass"], 2)
    assert abs(fp - 1 / 3) < 1e-12 and abs(fc - 4 / 3) < 1e-12, (fp, fc)
    assert abs(tp - 2 / 3) < 1e-12 and abs(tc - 5 / 3) < 1e-12, (tp, tc)
    # oracle_any：組內有 C 過 → 1.0
    assert any(c["pass"] for c in cells) is True
    # 全失敗組：三欄都該是 0（fail 不是「沒有訊號」，是 0 分）
    dead = [dict(cells[0]), dict(cells[1])]
    assert simulate(dead, lambda c: not c.get("findings_final"), 2)[0] == 0.0
    assert simulate(dead, lambda c: c["pass"], 2)[0] == 0.0
    # 標記守衛：flag_restart 永遠不用評分器；test_restart 只在 polyglot_py 不算上界
    assert scorer_flag_for("dabstep", "flag_restart") is False
    assert scorer_flag_for("dabstep", "test_restart") is True
    assert scorer_flag_for("polyglot_py", "test_restart") is False
    assert scorer_flag_for("polyglot_py", "oracle_any") is True
    # replay() 端到端：兩組同題型，ALL＝每組等權平均
    rows = [
        {"cell": "b-t-1", "task_dir": "/x/dabstep/1", "pass": True, "findings_final": []},
        {"cell": "b-t-2", "task_dir": "/x/dabstep/1", "pass": False, "findings_final": ["f"]},
        {"cell": "b-t-3", "task_dir": "/x/polyglot_py/9", "pass": False, "findings_final": ["f"]},
        {"cell": "b-t-4", "task_dir": "/x/polyglot_py/9", "pass": True, "findings_final": []},
    ]
    out = replay(rows, cap=2)
    assert out["suites"]["dabstep"]["flag_restart"]["scorer_used"] is False
    assert out["suites"]["dabstep"]["test_restart"]["scorer_used"] is True
    assert out["suites"]["polyglot_py"]["test_restart"]["scorer_used"] is False
    assert out["all"]["units"] == 2
    assert out["all"]["flag_restart"]["scorer_used"] is False
    assert out["all"]["test_restart"]["scorer_used"] is True  # 池裡含用評分器的題型
    assert out["all"]["pass_at_1_pct"] == 50.0
    # 錯誤行被剔除
    rows.append({"cell": "b-t-5", "task_dir": "/x/dabstep/2", "error": "boom"})
    assert replay(rows, cap=2)["all"]["units"] == 2
    print("selftest OK")


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--selftest":
        selftest()
        return 0
    if len(argv) < 1:
        print(__doc__, file=sys.stderr)
        return 2
    path = Path(argv[0])
    cap = int(argv[1]) if len(argv) > 1 else 3
    rows = json.loads(path.read_text(encoding="utf-8"))
    out = replay(rows, cap)
    out["input"] = {"path": str(path), "sha256": sha256_of(path),
                    "rows": len(rows),
                    "rows_used": sum(1 for r in rows if "error" not in r)}
    if "--write-mirror" in argv:
        mp = Path(argv[argv.index("--write-mirror") + 1])
        mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {mp}")
    if "--json" in argv or "--write-mirror" not in argv:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        a = out["all"]
        print(f"cap={cap}  units(ALL)={a['units']}")
        for k in list(out["suites"]) + ["ALL"]:
            r = out["suites"].get(k) or a
            tr = r["test_restart"]
            mark = "real-signal" if not tr["scorer_used"] else "UPPER-BOUND"
            print(f"{k:<14} n={r['units']:<4} pass@1={r['pass_at_1_pct']:>5}% "
                  f"flag={r['flag_restart']['pct']:>5}% (real-signal) "
                  f"test={tr['pct']:>5}% ({mark}) oracle={r['oracle_any']['pct']:>5}% (UPPER-BOUND)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
