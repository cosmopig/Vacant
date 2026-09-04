#!/usr/bin/env python3
"""R470 §六 P7：對每個 MISSED 的突變體找「可觀測差異的見證」。

為什麼要這一步：`MISSED` 有兩種完全不同的意思——
  (a) 偵測器沒看那條路徑  ⇒ 真的牙齒缺口
  (b) 突變體根本沒有可觀測差異（等價突變體）⇒ 不是缺口，是我造了個假突變體
只報 MISSED 的計數會把兩者混在一起，並高估缺口。零 API、純本機。

用法：python3 ops/gain/r470_missed_witness.py [--src <paired_ci.py 所在目錄>]
"""
from __future__ import annotations
import argparse, collections, pathlib, sys

ap = argparse.ArgumentParser()
ap.add_argument("--src", default=str(pathlib.Path(__file__).resolve().parents[1] / "gain/replay"))
a = ap.parse_args()
sys.path.insert(0, a.src)
import paired_ci as P                                              # noqa: E402

GRID_N = (60, 120, 189)          # r447=120、r461=189、MIN_PAIRED=60
hits4, hits5 = [], []
for n in GRID_N:
    for b in range(0, 31):
        for c in range(0, 31):
            if b + c == 0:
                continue
            r = P.diff_ci(b, c, n)
            lo, hi = r["lo"] * 100, r["hi"] * 100
            if r["lo"] == 0.0:                      # M4：lo>0 與 lo>=0 只在這裡分得開
                hits4.append((b, c, n))
            clean = P.verdict(lo, hi)               # M5：把 lo_pp>0 換成 hi_pp>0
            mut = ("ON_WINS" if hi > 0 else
                   "RULED_OUT" if hi <= P.PRACTICAL_PP else
                   "UNINFORMATIVE" if lo < -P.PRACTICAL_PP else "NON_INFERIOR_BUT_UNRESOLVED")
            if clean != mut:
                hits5.append((b, c, n, clean, mut))

print(f"M4 見證（lo 恰為 0）：{len(hits4)} / {3*30*30-3} 格 {hits4[:3]}")
print(f"M5 見證（判決被翻掉）：{len(hits5)} 格  例：{hits5[:3]}")
print(f"   被翻掉的乾淨判決分佈：{dict(collections.Counter(h[3] for h in hits5))}")
print(f"M6 見證：結構性——0 <= n_paired < MIN_PAIRED({P.MIN_PAIRED}) 的每一個 n 都分得開")


def nn(nd, n, start):                               # M9：搜尋起點 n vs 1
    if n == 0 or nd == 0:
        return -1
    rate = nd / n
    for m in range(start, P.MAX_N_SEARCH + 1):
        ndm = max(1, round(rate * m)); k = round(ndm / 2)
        r = P.diff_ci(k, ndm - k, m)
        if (r["hi"] - r["lo"]) / 2 * 100 <= P.PRACTICAL_PP:
            return m
    return -1


diff9, tested = [], 0
for n in (60, 82, 120, 189):
    for nd in range(1, n + 1, 7):
        tested += 1
        if nn(nd, n, n) != nn(nd, n, 1):
            diff9.append((nd, n, nn(nd, n, n), nn(nd, n, 1)))
print(f"M9 見證：掃 {tested} 格，{len(diff9)} 格不同  例：{diff9[:5]}")
print(f"   selftest E 用的那一格 (nd=24,n=82)：{nn(24,82,82)} vs {nn(24,82,1)} "
      f"⇒ {'同值，看不見' if nn(24,82,82)==nn(24,82,1) else '不同'}")
