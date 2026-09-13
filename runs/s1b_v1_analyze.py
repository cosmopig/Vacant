"""S1B 分析：λ × 六情境的通過表 ＋ 探針 C（λ=1.0 對既有 1000-seed 跑的回歸）。

為什麼要有這一支而不是直接看 `blayer_by_lambda.json` 的 `all_pass`：
本輪的主結果**很可能是「五個 λ 全過」**，而「全過」與「λ 根本沒接到 B 層」
在那個檔案裡長得一模一樣。所以除了通過與否，逐格印出兩個承重情境
（④reviewer_stake／⑤decay_slash）的實際數字與**離判準線還剩多遠**——
否則「全過」讀不出邊際有多寬（第 91 輪主判準 4）。

用法：PYTHONPATH=.:examples python3 runs/s1b_v1_analyze.py runs/s1b_v1
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REF = Path("runs/blayer_1000_v3/cells.jsonl")  # vacant/ 自 cb64bf5 零改動 ⇒ 可當已知答案
SLASH_SCEN = ("reviewer_stake", "decay_slash")


def load_cells(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def key(c: dict) -> tuple:
    return (c["scenario"], c["arm"], c["ratio"])


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/s1b_v1") / "S1B"
    rows = json.loads((root / "blayer_by_lambda.json").read_text(encoding="utf-8"))
    lams = [r["slash_n_factor"] for r in rows]
    print(f"λ 跑到的：{lams}（登記要 5 個）\n")

    # ── 主判準 1／2：落盤點數 ────────────────────────────────────────────
    print("── 產物點數（只數產物，不看返回值）──")
    for r in rows:
        lam = r["slash_n_factor"]
        d = root / f"lam{lam}"
        nc = len(load_cells(d / "cells.jsonl")) if (d / "cells.jsonl").exists() else -1
        ns = sum(1 for _ in (d / "samples.jsonl").open()) if (d / "samples.jsonl").exists() else -1
        nullv = sum(1 for v in r["scenarios"].values()
                    if v["verdict"] is None or not v["detail"])
        print(f"  λ={lam:<5} cells {nc:>3}/96 · samples {ns:>3}/96 · "
              f"verdict/detail 為 null 的情境 {nullv} · {r['elapsed_s']}s")

    # ── 主判準 3 · 探針 C：λ=1.0 必須逐位元重現既有跑 ────────────────────
    print("\n── 探針 C（回歸；不同 ⇒ 有隱藏狀態，全部作廢）──")
    r1 = next((r for r in rows if r["slash_n_factor"] == 1.0), None)
    if r1 is None or not REF.exists():
        print("  ✘ 無法比對（缺 λ=1.0 或缺參照）")
    else:
        ref = {key(c): c for c in load_cells(REF)}
        got = {key(c): c for c in load_cells(root / "lam1.0" / "cells.jsonl")}
        bad = [k for k in ref if k not in got or ref[k]["value"] != got[k]["value"]]
        print(f"  參照 {REF} · 比 {len(ref)} 格 · 逐位元不同 {len(bad)} 格 "
              f"⇒ PROBE_C_OK = {not bad}")
        for k in bad[:5]:
            print(f"    ✘ {k}: ref={ref[k]['value']} got={got.get(k, {}).get('value')}")

    # ── 主判準 4：通過表 ＋ 兩個承重情境的實際數字 ──────────────────────
    scen = list(rows[0]["scenarios"])
    print("\n── λ × 六情境通過表 ──")
    print("  λ      " + " ".join(f"{s[:12]:>13}" for s in scen) + "   all_pass")
    for r in rows:
        marks = " ".join(f"{('✅' if r['scenarios'][s]['verdict'] else '❌'):>13}" for s in scen)
        print(f"  {r['slash_n_factor']:<6} {marks}   {r['all_pass']}")

    print("\n── 承重情境的逐格數字（on 臂，ratio 0.0→0.7）──")
    for s in SLASH_SCEN:
        print(f"\n  {s}")
        for r in rows:
            # 注意：`scenarios[s]["on"]` 已經是 on 臂，Cell.to_json() 不帶 arm 欄
            on = sorted(r["scenarios"][s]["on"], key=lambda c: c["ratio"])
            print(f"    λ={r['slash_n_factor']:<5} " +
                  " ".join(f"{c['value']:.4f}" for c in on))
        print(f"    判準：{rows[0]['scenarios'][s]['detail']}")
        for r in rows:
            print(f"      λ={r['slash_n_factor']:<5} {r['scenarios'][s]['detail']}")


if __name__ == "__main__":
    main()
