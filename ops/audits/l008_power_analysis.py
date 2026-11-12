#!/usr/bin/env python3
"""L008 發射前檢定力分析量具（票 P20261112_1125-2；0 model calls、純本地離線數學）。
L008 §2「發射前算 power（research.mcnemar_power）並落案」：以 vacant_network.research
的 mcnemar_power/mcnemar_n_required（McNemar 精確雙尾、全枚舉）對 Phase 1 候選樣本量
n=60 與預期效應（p_disc 0.20/0.25/0.30 × ψ 0.65/0.70/0.75/0.80）算 power 與 80% power
最小 n，落案 ops/audits/l008_power_report.json。用法：`[--selftest]`（正控制＋3 負控制 → VERDICT）。
"""
from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from vacant_network.research import mcnemar_n_required, mcnemar_power

ALPHA = 0.05
PHASE1_N = 60
P_DISC_GRID = (0.20, 0.25, 0.30)
PSI_GRID = (0.65, 0.70, 0.75, 0.80)
TARGET_POWER = 0.80
REPORT = Path(__file__).resolve().parent / "l008_power_report.json"


def build_report() -> dict:
    """n=60 全格 power（重算自核心庫）＋80% power 最小 n 的 MDE 表。"""
    grid = [{"p_disc": pd, "psi": ps, "n": PHASE1_N,
             "power": round(mcnemar_power(PHASE1_N, pd, ps, alpha=ALPHA), 6)}
            for pd in P_DISC_GRID for ps in PSI_GRID]
    mde = [{"p_disc": pd, "psi": ps,
            "n_required": mcnemar_n_required(pd, ps, alpha=ALPHA, power=TARGET_POWER)}
           for pd in P_DISC_GRID for ps in PSI_GRID]
    return {"schema": "l008.power/1", "alpha": ALPHA, "phase1_n": PHASE1_N, "target_power": TARGET_POWER,
            "grid": grid, "mde_summary": mde, "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "vacant_network.research.mcnemar_power / mcnemar_n_required（精確雙尾 McNemar）"}


def verify_report(rep: dict) -> list[str]:
    """逐格重算 grid power 與 mde_summary n_required（雙邊界 mcnemar_power 驗證）並核對身份/單調性。"""
    bad: list[str] = []
    if rep.get("alpha") != ALPHA or rep.get("phase1_n") != PHASE1_N or rep.get("target_power") != TARGET_POWER:
        bad.append(f"alpha/phase1_n/target_power 被篡改: {rep.get('alpha')!r}/{rep.get('phase1_n')!r}/{rep.get('target_power')!r}")
    want_keys = [(pd, ps) for pd in P_DISC_GRID for ps in PSI_GRID]
    grid = rep.get("grid")
    if not isinstance(grid, list) or [(c.get("p_disc"), c.get("psi")) for c in grid if isinstance(c, dict)] != want_keys:
        bad.append("grid 缺格或 (p_disc, psi) 格身份/順序不符")
        grid = []
    for cell in grid:
        try:
            pd, ps, pw = cell["p_disc"], cell["psi"], cell["power"]
            if cell.get("n") != PHASE1_N or not isinstance(pw, (int, float)) or not 0.0 <= pw <= 1.0:
                bad.append(f"grid 格格式或範圍錯誤: {cell}")
            elif abs(pw - mcnemar_power(PHASE1_N, pd, ps, alpha=ALPHA)) > 1e-4:
                bad.append(f"power 不符重算: {pd}/{ps} 報告={pw} 重算={mcnemar_power(PHASE1_N, pd, ps, alpha=ALPHA):.6f}")
        except (KeyError, TypeError):
            bad.append(f"grid 格格式錯誤: {cell!r}")
    mde = rep.get("mde_summary")
    if not isinstance(mde, list) or [(c.get("p_disc"), c.get("psi")) for c in mde if isinstance(c, dict)] != want_keys:
        bad.append("mde_summary 缺格或 (p_disc, psi) 格身份/順序不符")
        mde = []
    for cell in mde:
        nr = cell.get("n_required")
        pd, ps = cell.get("p_disc"), cell.get("psi")
        if not (isinstance(nr, int) and nr >= 1):
            bad.append(f"mde_summary 有非正整數 n_required: {cell}")
        elif not (mcnemar_power(nr, pd, ps, alpha=ALPHA) >= TARGET_POWER > mcnemar_power(nr - 1, pd, ps, alpha=ALPHA)):
            bad.append(f"mde_summary n_required 不符最小 80% 檢定力樣本量: {cell}")
    for pd in P_DISC_GRID:  # 正控制 2：power 對 ψ 嚴格單調遞增
        row = [c["power"] for c in grid if isinstance(c, dict) and c.get("p_disc") == pd and isinstance(c.get("power"), (int, float))]
        if len(row) != len(PSI_GRID) or sorted(row) != row or len(set(row)) != len(row):
            bad.append(f"power 未隨 ψ 嚴格單調遞增 (p_disc={pd})")
    return bad


def run_selftest() -> int:
    if not REPORT.is_file():
        print(f"  FAIL missing report: {REPORT}\nVERDICT: L008_POWER_FAIL"); return 1
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    failures: list[str] = []
    for pd in P_DISC_GRID:  # 正控制 1/2：ψ=0.5 即 H0 size≤α；power 隨 ψ 嚴格單調遞增
        if mcnemar_power(PHASE1_N, pd, 0.5, alpha=ALPHA) > ALPHA + 1e-12:
            failures.append(f"正1: size(p_disc={pd}) > alpha={ALPHA}")
        pw = [mcnemar_power(PHASE1_N, pd, ps, alpha=ALPHA) for ps in PSI_GRID]
        if any(b <= a for a, b in zip(pw, pw[1:])):
            failures.append(f"正2: power 非 ψ 嚴格遞增 (p_disc={pd})")
    v = verify_report(rep)  # 正控制 3：實盤報告格式＋數值重算核對（唯讀，不覆寫實盤檔案）
    if v:
        failures.append(f"正3: 報告未過重算核對: {v}")
    t1 = copy.deepcopy(rep); t1["grid"][0]["power"] = round(t1["grid"][0]["power"] + 0.01, 6)
    if not verify_report(t1): failures.append("負1: 報告 power 被篡改未被抓出")
    try:  # 負控 2：ψ=0.5 達 80% power 必 raise ValueError
        mcnemar_n_required(0.25, 0.5, alpha=ALPHA, power=TARGET_POWER)
        failures.append("負2: ψ=0.5 未 raise ValueError")
    except ValueError:
        pass
    t3 = copy.deepcopy(rep); t3["phase1_n"] = PHASE1_N - 1
    if not verify_report(t3): failures.append("負3: phase1_n 被篡改未報違規")
    t4 = copy.deepcopy(rep); t4["mde_summary"][0]["n_required"] = 1
    if not verify_report(t4): failures.append("負4: mde_summary n_required 被篡改未報違規")
    if failures:
        print("\n".join(f"  FAIL {f}" for f in failures) + "\nVERDICT: L008_POWER_FAIL"); return 1
    print(f"report: {REPORT}\nVERDICT: L008_POWER_OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="L008 發射前檢定力分析量具（0 model calls）")
    ap.add_argument("--selftest", action="store_true", help="正控制＋3 負控制")
    args = ap.parse_args()
    if args.selftest:
        return run_selftest()
    REPORT.write_text(json.dumps(build_report(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"report: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
