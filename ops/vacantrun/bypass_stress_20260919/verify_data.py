#!/usr/bin/env python3
"""這支在架構裡承重什麼：讓本目錄的數字**可以被外人在自己的機器上重算**。

`data/<cell>/egress_gauge.json` 是當時算好的結果。它旁邊的
`ctr_before.json`／`ctr_after.json` 是**原始的計數器讀數**。
這支拿原始讀數重跑一次 `egress_counter.delta()`，逐格比對——
不一致就代表 `egress_gauge.json` 不是從那兩個讀數算出來的。

⚠ 誠實邊界：這驗的是**算術與資料的一致性**，不是「當時機器上真的只有這些封包」。
  後者沒有辦法事後驗證（計數器不簽章），它靠的是 `rules_before/after.txt` 的
  還原比對與一跑一專屬 uid 那兩條紀律。

    python3 ops/vacantrun/bypass_stress_20260919/verify_data.py     # rc=0 ⇒ 全部對得上
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import egress_counter as ec                                      # noqa: E402

FIELDS = ("available", "off_mediation_packets", "offbox_packets",
          "onbox_other_packets", "mediated_packets")


def main() -> int:
    root = pathlib.Path(__file__).resolve().parent / "data"
    bad, n = [], 0
    for d in sorted(root.iterdir()):
        if not d.is_dir() or not (d / "ctr_before.json").exists():
            continue
        n += 1
        got = ec.delta(json.loads((d / "ctr_before.json").read_text()),
                       json.loads((d / "ctr_after.json").read_text()))
        want = json.loads((d / "egress_gauge.json").read_text())
        bad += [(d.name, k, want[k], got[k]) for k in FIELDS if got[k] != want[k]]
    print(f"逐格從 ctr_before/after 重算 egress_gauge：{n} 格，不一致 {len(bad)} 格")
    for x in bad:
        print("  ", x)
    if n == 0:
        print("一格都沒讀到——那是壞掉，不是通過。")   # 鐵律 3：沒量到 ≠ 量到 0
        return 2
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
