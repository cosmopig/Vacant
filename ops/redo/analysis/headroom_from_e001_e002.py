#!/usr/bin/env python3
"""headroom_from_e001_e002 — MISSION §二 那三個數字的出處（探索性、0 次模型呼叫、只讀 repo 內已歸檔的報告）。

讀 `ops/vlab/runs_e001_pi_AC_baseline/REPORT_polyglot_py_subset.json`（每題 A／C 各一跑，含牆鐘）與
`ops/vlab/runs_e002_hypothesis_arms/PAIR_BREAKDOWN.json`（每題 A／C 各一跑）：pi＋gemma-4-12b、polyglot_py 34 題，
每題 4 跑。A 與 C（零設定 Stop 檢查）混用當成同一個 agent 的獨立跑——C 對 A 三批都沒有量到差別
（e001 p＝0.18、e002 p＝0.34、e016 p＝1.0），但它們不是逐位元組相同的條件，所以這只是**上限的估計**：
「抽 k 跑、有一跑過就算過」等於假設驗收訊號完美（polyglot_py 的可見測試就是評分器，所以這裡站得住）。
"""
import json, math, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[3]
e1 = json.loads((ROOT / "ops/vlab/runs_e001_pi_AC_baseline/REPORT_polyglot_py_subset.json").read_text())["per_pair"]
pb = json.loads((ROOT / "ops/vlab/runs_e002_hypothesis_arms/PAIR_BREAKDOWN.json").read_text())["pairs_AC"]
runs = {p["task"]: [p["A_pass"], p["C_pass"]] for p in e1}
for key, (a, c) in {"both": (1, 1), "C_only": (0, 1), "A_only": (1, 0), "neither": (0, 0)}.items():
    for t in pb[key]:
        runs[t] += [bool(a), bool(c)]
assert len(runs) == 34 and all(len(v) == 4 for v in runs.values())
dist = {k: sum(1 for v in runs.values() if sum(v) == k) for k in range(5)}
print("每題 4 跑裡過了幾跑 → 題數：", dist, "（0＝永遠不過、4＝永遠過、1–3＝時過時不過）")
for k in (1, 2, 3):
    exp = sum(1 - (math.comb(4 - sum(v), k) / math.comb(4, k) if 4 - sum(v) >= k else 0) for v in runs.values())
    print(f"從這 4 跑裡抽 {k} 跑、有一跑過就算過：{exp:.1f}/34 = {exp / 34:.1%}")
print("時過時不過的題：", sorted(t for t, v in runs.items() if 0 < sum(v) < 4))
walls = [(p[a + "_wall"], p[a + "_pass"]) for p in e1 for a in "AC"]
ok = sorted(w for w, good in walls if good); bad = sorted(w for w, good in walls if not good)
for T in (600, 900, 1800):
    print(f"e001 的 68 跑：{T} 秒內結束的——通過的 {sum(w <= T for w in ok)}/{len(ok)}、沒過的 {sum(w <= T for w in bad)}/{len(bad)}")
