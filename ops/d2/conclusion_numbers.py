#!/usr/bin/env python3
"""結論檔的數字一律從這裡產生（第三次獨立稽核 11-25：手抄的數字有 8 處和結果檔不符）。
讀 ~/dev/ops/d2_results/<root>/analysis.json 與 audit_summary.json，印出 Markdown 表格列。
漏抓用的是 analysis.json 的**配對**數字（兩臂週期開始時都對、真值變了的宣稱）——預註冊的主要口徑。
用法：conclusion_numbers.py [--results ~/dev/ops/d2_results] root[:label[:cost_metric_label]] ...
"""
from __future__ import annotations

import argparse
import json
import pathlib


def pct(x):
    return "n/a" if x is None else f"{x * 100:+.1f}pp"


def ci(v):
    return "n/a" if not v or v[0] is None else f"{v[0]:.2f}–{v[1]:.2f}"


def row(res: pathlib.Path, root: str, label: str) -> str:
    a = json.loads((res / root / "analysis.json").read_text())
    au = json.loads((res / root / "audit_summary.json").read_text())
    P = a.get("primary_arm", "c")
    cov = a["coverage"]
    mcb = a["primary"]["miss_diff_c_b"]
    mcd = a["confirmatory_c_d"]["miss_diff_c_d"]
    tbc = a["primary"]["token_ratio_b_c"]
    tdc = a["confirmatory_c_d"]["token_ratio_d_c"]
    miss = (f"{P} {mcb['missed_arm1']}/{mcb['n_pairs']}、b {mcb['missed_arm2']}/{mcb['n_pairs']}；"
            f"{P} {mcd['missed_arm1']}/{mcd['n_pairs']}、d {mcd['missed_arm2']}/{mcd['n_pairs']}")
    hm = au["harness_match"]
    cv = au.get("chain_verification_summary") or {}
    return (f"| {label} | {cov.get('correct_page')}/{cov.get('claims')} | {miss} | {pct(mcb['point'])}（上界 {pct(mcb.get('upper'))}） | "
            f"{tbc['point']:.2f}×（{ci(tbc.get('ci'))}） | {tdc['point']:.2f}×（{ci(tdc.get('ci'))}） | "
            f"{a['verdict']}／{a['verdict_c_d']} | 稽核 {hm['mismatches']}/{hm['rows']} 不一致；鏈 {cv.get('signatures_ok')}/{cv.get('chains')} | "
            f"`d2_results/{root}/analysis.json` |")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(pathlib.Path.home() / "dev/ops/d2_results"))
    ap.add_argument("roots", nargs="+")
    a = ap.parse_args()
    res = pathlib.Path(a.results)
    print("| 批次 | 覆蓋率（指到正確頁） | 漏抓（配對：主要臂對 b；主要臂對 d） | 主要臂−b 漏抓差（97.5% 上界） | 成本比 b/主要臂（97.5% 區間） | d/主要臂 | 判定（對 b／對 d） | 稽核 | 來源 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in a.roots:
        root, _, label = r.partition(":")
        print(row(res, root, label or root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
