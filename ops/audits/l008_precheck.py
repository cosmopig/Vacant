#!/usr/bin/env python3
"""L008 放大率預註冊前置量具（離線、0 model calls、只讀；票 P20261112_0723-2）。
L008＝G 系列下一張預註冊問題（人類定案 2026-11-11 §2.a 自續條款；草案 ops/loop/L008.md 已入庫）：
「可執行驗收門＋等預算重抽」（CONFORM vs OFF）的提升 Δ 是否隨模型變小而放大？（兩點：12b vs 27b）。
本檔只落地機械量具：不發射、不讀 hidden/scorer、不改凍結 4 檔。
1. eval_l008_amplification 三態（CI 為 Δ_small−Δ_large 的區間）：AMPLIFIED＝ci_lo>0 且 pval<alpha 且 delta_small>delta_large；
   REVERSED＝ci_hi<0 且 pval<alpha 且 delta_small<delta_large（如實記、不得包裝）；FLAT＝其餘（方向未確立）。
2. check_nonpooling：先驗兩點只准 motivation 引用；嚴禁兩筆獨立重複併成一個大 n（L008.md §0）。
3. check_snapshot：repo 快照 ops/loop/L008.md 須在案並記錄先驗兩點、三態表與不池化句。
用法：python3 ops/audits/l008_precheck.py [--selftest]
"""
import argparse
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
SNAP = REPO / "ops/loop/L008.md"
R460R_REPLICATIONS = (14.17, 18.33, 17.50, 19.17, 18.97)  # R460R CONFORM vs OFF 五重複
PRIOR = (("R460R", "gemma-4-12b-it-qat", 120, 18.33), ("R532", "qwen3.8-27b Q4_K_M", 836, 7.89))  # 引值：R460R 五重複之二；R532 五 bank pooled
SNAP_TOKENS = ("R460R", "18.33", "R532", "7.89", "AMPLIFIED", "FLAT", "REVERSED", "不池化")


def eval_l008_amplification(delta_small, delta_large, ci_lo, ci_hi, pval, alpha=0.05) -> tuple[str, str]:
    """L008 三態判定（預註冊狀態表；不得事後造狀態；回傳 (狀態, 理由)）。"""
    if ci_lo > 0 and pval < alpha and delta_small > delta_large:
        return ("AMPLIFIED", "Δ_small−Δ_large>0 且顯著：模型越小放大越大（H1 支持）")
    if ci_hi < 0 and pval < alpha and delta_small < delta_large:
        return ("REVERSED", "Δ_small−Δ_large<0 且顯著：大模型放大更多；如實記、不得包裝")
    return ("FLAT", "CI 跨零或未顯著：方向未確立；不得引申『門禁對小模型無用』")


def check_nonpooling(analysis: dict) -> list[str]:
    """non-pooling 守衛（fail-closed；回傳違規清單，空＝通過）。"""
    if not isinstance(analysis, dict):
        return ["non-pooling 違規：輸入非 dict（未測量，I-4）"]
    v: list[str] = []
    pts = analysis.get("points")
    if not isinstance(pts, list) or not pts:
        return ["non-pooling 違規：先驗兩點記載缺失（points 空，I-4）"]
    for i, p in enumerate(pts):
        if (p.get("use") if isinstance(p, dict) else p) != "motivation":
            v.append(f"non-pooling 違規：points[{i}] use={p!r}（先驗點只准作動機引用）")
    for k in ("pooled_n", "pooled_delta", "pooled_pval"):
        if analysis.get(k) is not None:
            v.append(f"non-pooling 違規：{k}={analysis[k]!r}（嚴禁併成一個大 n）")
    return v


def check_snapshot(path: pathlib.Path = SNAP) -> list[str]:
    """repo 快照須在案並記錄先驗兩點＋三態表＋不池化句（回傳違規清單，空＝通過）。"""
    if not path.is_file():
        return [f"快照缺失：{path}"]
    t = path.read_text(encoding="utf-8")
    v = [f"快照缺失：{tok}" for tok in SNAP_TOKENS if tok not in t]
    if PRIOR[0][3] not in R460R_REPLICATIONS:
        v.append("先驗值錯誤：R460R 引值不在五重複 delta 列內")
    return v


def _controls() -> list[tuple[str, bool]]:
    good = {"points": [{"run": r, "use": "motivation", "delta_pp": d} for r, _m, _n, d in PRIOR]}
    pooled = dict(good, pooled_n=120 + 836, pooled_delta=9.13)
    return [
        ("p1 先驗兩點數值核算（18.33∈五重複列；快照在案記錄 18.33/7.89）", PRIOR[0][3] in R460R_REPLICATIONS and not [s for s in check_snapshot() if "18.33" in s or "7.89" in s]),
        ("p2 快照三態表＋不池化句在案（ops/loop/L008.md）", not check_snapshot()),
        ("p3 合成 AMPLIFIED（20 vs 8，CI 2.5..21.5，p=0.01）判 AMPLIFIED", eval_l008_amplification(20.0, 8.0, 2.5, 21.5, 0.01)[0] == "AMPLIFIED"),
        ("n1 合成 REVERSED（6 vs 10，CI -24..-3.5，p=0.01）判 REVERSED", eval_l008_amplification(6.0, 10.0, -24.0, -3.5, 0.01)[0] == "REVERSED"),
        ("n2 合成 FLAT（12 vs 10，CI -4..8 跨零，p=0.42）判 FLAT", eval_l008_amplification(12.0, 10.0, -4.0, 8.0, 0.42)[0] == "FLAT"),
        ("n3 池化合併大 n（n=956）必報違規、合規記載必過", not check_nonpooling(good) and bool(check_nonpooling(pooled))),
    ]


def selftest() -> int:
    controls = _controls()
    for name, ok in controls:
        print(("OK   " if ok else "FAIL ") + name)
    if all(ok for _n, ok in controls):
        print("VERDICT: L008_PRECHECK_OK")
        return 0
    print("VERDICT: L008_PRECHECK_FAIL")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋3 負控制")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    v = check_snapshot()
    if v:
        for s in v: print("VIOLATION:", s)
        print("VERDICT: L008_PRECHECK_FAIL")
        return 1
    print("checked: ops/loop/L008.md 快照在案（R460R 18.33 / R532 7.89；三態表；不池化）")
    print("VERDICT: L008_PRECHECK_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
