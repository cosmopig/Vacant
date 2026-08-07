"""基線 v1（2026-08-07）——用**現在的**架構跑一輪完整基線，凍結成對照組。

## 為什麼要有這支

之後每一次迭代都會想說「v2 比較好」。沒有一個用同一份程式碼、同一組 seed、
同一批參數跑出來的對照組，那句話無從宣稱——只能拿新數字去比 2026-08-03 的
舊數字，而那一輪之後機制改過（slash 的 λ、repent 臂、rows.jsonl），
比出來的差異會混著「改了什麼」與「量法變了」。

所以這一格的定位是**凍結**不是**發現**：不做假設檢定、不下「哪個策略比較強」
的結論。它的產出是一組 config digest 與 per-seed 原值，讓之後的比較有得對。

## 網格

  4 策略（whitewash / patient / sybil / pulse(3,10)）
× 5 盲區（0, 0.15, 0.3, 0.5, 0.7）
× 30 seeds × 600 輪

**盲區刻意不放 1.0**（分析紀律 2）：`blindspot=1.0` 時 30 個 seed 塌成同一條
軌跡（sd=0、有效 n=1），得手數退化成 `90 × 工作週期` 的算術恆等式。端點的
數字最漂亮，也最沒有資訊——上一輪「盲區 8.9 倍／54 倍」的結論就是被它撐著，
排掉它之後只剩 3.28／5.68 倍。

盲區的語意：`blindspot > 0` 是「若檢查者也是模型」的設計變體。現行設計的
稽核是 sandbox 確定性重跑，對**有客觀檢查的任務** blindspot=0 才是對的；
但**評審層本來就是模型**，所以盲區對評審層永遠適用。

## 重跑

    .venv/bin/python examples/baseline_v1.py --out <DIR>

全確定性：同一個 seed、同一份 config digest 必得同一個結果，與 `--workers` 無關。
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from simgrid import DEFAULT_WORKERS, run_cell, write_manifest
from vacant.entrycost import SimConfig

ROUNDS = 600
SEEDS = [f"p{i}" for i in range(30)]
# 不放 1.0：那是退化端點（見模組 docstring）。
# 預設是**精簡版**的三個盲區值（0＝現行設計、0.3、0.7），因為 sybil 那一格
# 貴到會吃掉整輪機時：它每輪丟一個身份，600 輪後 registry 有 601 張卡，
# 路由的成本是 O(輪數 × 卡數 × cell 數)。三個點已經夠當對照組（單調性看得到、
# 端點沒有塌），要跑滿五個點用 --blindspots 0 0.15 0.3 0.5 0.7。
BLINDSPOTS = (0.0, 0.3, 0.6)
BLINDSPOTS_FULL = (0.0, 0.15, 0.3, 0.5, 0.7)
STRATEGIES: dict[str, dict] = {
    "whitewash": dict(strategy="whitewash"),
    "patient": dict(strategy="patient", build_rounds=10),
    "sybil": dict(strategy="sybil"),
    "pulse(3,10)": dict(strategy="pulse", pulse_burst=3, pulse_recover=10),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    ap.add_argument("--seeds", type=int, default=None,
                    help="覆寫 seed 數（只給冒煙測試用；正式跑不要給）")
    ap.add_argument("--blindspots", nargs="*", type=float, default=None,
                    help=f"盲區值；不給＝精簡版 {BLINDSPOTS}。滿版是 {BLINDSPOTS_FULL}。"
                         "不要放 1.0（退化端點）")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    logdir = a.out / "logs"
    global SEEDS, BLINDSPOTS
    if a.blindspots:
        if any(b >= 1.0 for b in a.blindspots):
            raise SystemExit("blindspot=1.0 是退化端點（30 個 seed 塌成一條軌跡），拒跑")
        BLINDSPOTS = tuple(a.blindspots)
    if a.seeds:
        SEEDS = [f"p{i}" for i in range(a.seeds)]
        print(f"⚠ seed 數被覆寫成 {a.seeds}——這不是正式跑", flush=True)

    cells = []
    t0 = time.time()
    # 每格寫完就 flush（見 simgrid.run_cell）：跑到一半被砍掉時，
    # 已經跑完的格子必須留在磁碟上，而不是留在記憶體裡陪葬。
    with (a.out / "rows.jsonl").open("w", encoding="utf-8") as rows, \
            (a.out / "cells.jsonl").open("w", encoding="utf-8") as cf:
        for name, kw in STRATEGIES.items():
            for blind in BLINDSPOTS:
                label = f"{name} · blind={blind}"
                cfgs = [SimConfig(rounds=ROUNDS, seed=s, blindspot=blind, **kw)
                        for s in SEEDS]
                c = run_cell(label, cfgs, logdir=logdir, workers=a.workers,
                             params={"strategy": name, "blindspot": blind},
                             rows_out=rows, cells_out=cf)
                cells.append(c)
                print(f"{label:<26} 得手 {c['accepted_bad']['mean']:>7}"
                      f"  曝光 {c['routed_to_attacker']['mean']:>7}"
                      f"  效率 {c['bad_per_route']['mean']}"
                      f"  全擋 {c['shutout_rate']:>5}"
                      f"  有效n {c['accepted_bad']['n_effective']:>3}", flush=True)
                write_manifest(
                    a.out,
                    note="基線 v1（2026-08-07）· 進行中",
                    rounds=ROUNDS, seeds=SEEDS, cells=cells,
                    extra={"blindspots": list(BLINDSPOTS), "complete": False,
                           "cells_done": len(cells),
                           "cells_total": len(STRATEGIES) * len(BLINDSPOTS)})

    write_manifest(
        a.out,
        note="基線 v1（2026-08-07）。4 策略 × 5 盲區 × 30 seeds × 600 輪。"
             "盲區刻意不含 1.0（退化端點，30 seed 塌成一條軌跡）。"
             "這是凍結用的對照組，不下比較結論。",
        rounds=ROUNDS, seeds=SEEDS, cells=cells,
        extra={"blindspots": list(BLINDSPOTS), "complete": True,
               "strategies": {k: v for k, v in STRATEGIES.items()},
               "elapsed_s": round(time.time() - t0, 1)})
    print(f"\n寫出 {a.out}（{round(time.time() - t0, 1)}s）")


if __name__ == "__main__":
    main()
