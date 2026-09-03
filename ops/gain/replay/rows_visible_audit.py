"""只讀 rows.jsonl：各臂出貨的答案裡，有多少是連可見測試都沒過的。

零沙箱、零模型呼叫。`visible_ok` 是 round342 之後每一臂都會落盤的欄位
（arm_off / arm_off5 都只是**記錄**，不改變 accepted 語意），所以這個數字
可以直接從已歸檔的 run 讀出來。
"""
from __future__ import annotations

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]


def main(runs):
    for run in runs:
        rows = [json.loads(x) for x in
                (REPO / "runs" / run / "rows.jsonl").open(encoding="utf-8")]
        print(f"== {run} (rows={len(rows)})")
        for arm in ("OFF", "ON", "OFF5"):
            rs = [r for r in rows if r["arm"] == arm]
            if not rs:
                continue
            fail = [r for r in rs if not r["meets_demand"]]
            fv = [r for r in fail if r.get("visible_ok") is False]
            pv = [r for r in rs if r["meets_demand"] and r.get("visible_ok") is False]
            print(f"  {arm:5s} n={len(rs):3d}  pass={len(rs)-len(fail):3d} "
                  f"({100*(len(rs)-len(fail))/len(rs):5.2f}%)  fail={len(fail):3d}  "
                  f"shipped-with-visible_ok=false among failures={len(fv):3d}  "
                  f"passed-hidden-while-visible-false={len(pv)}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["g_r441_gemma_only_mbpp_b", "g_r356_3arm_20260830"])
