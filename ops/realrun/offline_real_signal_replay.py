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
  python3 ops/realrun/offline_real_signal_replay.py <replay.json> --curve [Kmax=5] [--write-mirror <path>]

--curve（round 116 新增，只讀聚合，不改上面任何單 cap 輸出）：
  同一份輸入跑 cap=1..Kmax，只輸出**可引用欄 flag_restart**（所有題型 scorer_used=false），
  回答「每個重抽 slot 各買進多少成果」。每個 (cap, 題型) 附 groups_with_n_ge_cap＝
  該 cap 下「archived run 數 ≥ cap」的組數，且只數進入 units 的組（≥2 archived runs，
  與 replay() 同一把尺；cap=1 時故必等於 units）。cap 超過組的 archived run 數時，
  本工具的 cyclic 語義會重用已 archieve 的 run——那個 cap 的數字是 archived 集合的
  性質，不是新的一次 live 嘗試。
"""
from __future__ import annotations

import collections
import hashlib
import json
import sys
from pathlib import Path

SCHEMA = "vacant.realrun.offline_real_signal_replay/1"
SCHEMA_CURVE = "vacant.realrun.resample_budget_curve/1"

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


def curve(rows: list[dict], caps: list[int]) -> dict:
    """重抽預算曲線（只讀聚合）：cap=1..Kmax 的 flag_restart 欄（唯一所有題型皆可引用的欄）。

    語義（與 simulate() 一致）：cap=K＝在「Vacant 紀錄訊號 findings 為空」的停止條件下
    最多 K 次嘗試。組的 archived run 數 n < K 時，cyclic 起點平均會重用已 archieve 的 run，
    該 cap 的數字因此是 archived 集合的性質，不是 K 次全新 live 嘗試——groups_with_n_ge_cap
    就是「該 cap 下真正有足量 archived run」的組數。

    口徑（釘死）：groups_with_n_ge_cap 只數「進入 units 的組」（≥2 archived runs，與
    replay() 的 len(cells) >= 2 過濾同一把尺）。singleton 組不進任何平均，故 cap=1 時
    groups_with_n_ge_cap 必等於 units；K≥2 時必 ≤ 之。舊版漏掉這個過濾，cap=1 會數到
    singleton（dabstep 151>144、ALL 339>331），違反「子集」語義。
    """
    groups = group_rows(rows)
    entry_caps: dict[str, dict] = {}
    for K in caps:
        full = replay(rows, cap=K)

        def pick(r: dict) -> dict:
            fr = r["flag_restart"]
            assert fr["scorer_used"] is False  # flag_restart 永遠不用評分器
            return {
                "units": r["units"],
                "pct": fr["pct"],
                "mean_runs": fr["mean_runs"],
                "scorer_used": False,
                "signal": fr["signal"],
            }

        suites = {}
        for suite, r in full["suites"].items():
            e = pick(r)
            e["groups_with_n_ge_cap"] = sum(
                1 for (s, _b, _t), cells in groups.items()
                if s == suite and len(cells) >= 2 and len(cells) >= K)
            suites[suite] = e
        all_e = pick(full["all"])
        all_e["groups_with_n_ge_cap"] = sum(
            1 for cells in groups.values() if len(cells) >= 2 and len(cells) >= K)
        entry_caps[str(K)] = {"suites": suites, "all": all_e}
    return {
        "schema": SCHEMA_CURVE,
        "column": "flag_restart",
        "definition": {
            "unit": "same unit as the single-cap replay: (suite, batch, task) group with >=2 archived independent runs; groups weighted equally",
            "column_note": "flag_restart is the only column citable on every suite (scorer_used=false). test_restart is a real signal only on visible_tests_are_grader_suites (see the cap=3 mirror); oracle_any is always an upper bound.",
            "cap_note": "cap=K = at most K attempts before the stop condition (Vacant's recorded findings empty).",
        },
        "caps": entry_caps,
        "reading": {
            "caveats": [
                "offline replay over archived runs (zero model calls), not a live run (H-12: does not transfer to another model/bank without re-running)",
                "where a group has fewer archived runs than the cap, the cyclic average reuses archived runs: that cap's number is a property of the archived set, not fresh live attempts; see groups_with_n_ge_cap",
                "flatness from cap a to cap b means no group in this bank gains under the recorded stop rule from attempts a+1..b",
            ],
        },
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
    # curve()：手算期望（ALL＝每組等權）。
    # 組 A（dabstep, n=2）[T(findings 空), F(findings 有)]：
    #   K=1 → start0 停於 T、start1 取 F → 0.5；K=2 → start1 走完 F 後 wrap 回 T 停 → 1.0；K=3 同 1.0。
    #   mean_runs：K=2 → (1+2)/2 = 1.5。
    # 組 B（polyglot_py, n=3）[F, F, T(findings 空)]：
    #   K=1 → 1/3；K=2 → (F,F 走完取 F / F,T 停於 T / T 停) = 2/3；K=3 → 1.0。
    #   mean_runs：K=1 → 1.0；K=2 → (2+2+1)/3 = 5/3；K=3 → (3+2+1)/3 = 2.0。
    # ALL：K=1 → (0.5+1/3)/2；K=2 → (1+2/3)/2；K=3 → 1.0。
    crows = [
        {"cell": "c-a-1", "task_dir": "/x/dabstep/7", "pass": True, "findings_final": []},
        {"cell": "c-a-2", "task_dir": "/x/dabstep/7", "pass": False, "findings_final": ["f"]},
        {"cell": "c-b-1", "task_dir": "/x/polyglot_py/8", "pass": False, "findings_final": ["f"]},
        {"cell": "c-b-2", "task_dir": "/x/polyglot_py/8", "pass": False, "findings_final": ["f"]},
        {"cell": "c-b-3", "task_dir": "/x/polyglot_py/8", "pass": True, "findings_final": []},
        # singleton 組（只 1 筆 archived run）：不進 units（replay() 的 >=2 過濾），
        # 也不得進 groups_with_n_ge_cap——cap=1 時兩者必相等。
        {"cell": "c-s-1", "task_dir": "/x/databench/9", "pass": True, "findings_final": []},
    ]
    cv = curve(crows, [1, 2, 3])
    assert cv["column"] == "flag_restart"
    # replay() 的四捨五入口徑：pct 2 位、mean_runs 4 位——期望值用同口徑。
    assert cv["caps"]["1"]["all"]["pct"] == round(100 * (0.5 + 1 / 3) / 2, 2)  # 41.67
    assert cv["caps"]["2"]["all"]["pct"] == round(100 * (1 + 2 / 3) / 2, 2)  # 83.33
    assert cv["caps"]["3"]["all"]["pct"] == 100.0
    assert cv["caps"]["1"]["suites"]["dabstep"]["pct"] == 50.0
    assert cv["caps"]["2"]["suites"]["dabstep"]["pct"] == 100.0
    assert cv["caps"]["3"]["suites"]["dabstep"]["pct"] == 100.0
    assert cv["caps"]["2"]["suites"]["dabstep"]["mean_runs"] == 1.5
    assert cv["caps"]["1"]["suites"]["polyglot_py"]["pct"] == round(100 / 3, 2)  # 33.33
    assert cv["caps"]["2"]["suites"]["polyglot_py"]["pct"] == round(200 / 3, 2)  # 66.67
    assert cv["caps"]["3"]["suites"]["polyglot_py"]["pct"] == 100.0
    # mean_runs 組 B：K=1 → 1.0；K=2 → (2+2+1)/3 = 5/3；K=3 → (3+2+1)/3 = 2.0
    assert cv["caps"]["1"]["suites"]["polyglot_py"]["mean_runs"] == 1.0
    assert cv["caps"]["2"]["suites"]["polyglot_py"]["mean_runs"] == round(5 / 3, 4)  # 1.6667
    assert cv["caps"]["3"]["suites"]["polyglot_py"]["mean_runs"] == 2.0
    # groups_with_n_ge_cap：n=2 與 n=3 → K=1/2 皆 2，K=3 只有 n=3 那組
    assert cv["caps"]["2"]["all"]["groups_with_n_ge_cap"] == 2
    assert cv["caps"]["3"]["all"]["groups_with_n_ge_cap"] == 1
    # cap=1：n_ge_cap 必等於 units（singleton 不數）；舊版漏 >=2 過濾會數成 3
    assert cv["caps"]["1"]["all"]["units"] == 2
    assert cv["caps"]["1"]["all"]["groups_with_n_ge_cap"] == 2
    # 每欄 scorer_used 恆為 False（flag 欄守衛）
    for K in ("1", "2", "3"):
        assert cv["caps"][K]["all"]["scorer_used"] is False
    print("selftest OK")


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--selftest":
        selftest()
        return 0
    if len(argv) < 1:
        print(__doc__, file=sys.stderr)
        return 2
    path = Path(argv[0])
    if "--curve" in argv:
        idx = argv.index("--curve")
        kmax = 5
        if idx + 1 < len(argv) and argv[idx + 1].isdigit():
            kmax = int(argv[idx + 1])
        rows = json.loads(path.read_text(encoding="utf-8"))
        out = curve(rows, list(range(1, kmax + 1)))
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
            names = sorted(out["caps"]["1"]["suites"])
            for K in sorted(out["caps"], key=int):
                row = out["caps"][K]
                cells = "  ".join(f"{s}={row['suites'][s]['pct']}%" for s in names)
                print(f"K={K}  {cells}  ALL={row['all']['pct']}%")
        return 0
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
