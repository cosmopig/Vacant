#!/usr/bin/env python3
"""R499 **事後**診斷：等跨度帶裡，左緣能不能像 R496／R498 那樣「等距鋪開」？

⚠ **事後，不改頭條。** R499 頭條判 `DUAL_FEASIBLE`，但被選中的左緣是 [0,1,2,3,4,289]
——五個幾乎重合的視窗＋一個遠端。判準 §一.6 的 `pos_spread=(max-min)/room` 只管兩端，
不管中間有沒有鋪開。**語意理由（不是結果數字）**：R496／R498 的設計是**等距**左緣，
而 R499 §一.8 的解法安靜地把那個要求丟掉了 ⇒ 兩者不是同一個設計。
（同輪 `M4_BAND_K2` MISSED 是同一件事的另一面：K=6 這道加嚴在真資料上零承重。）

本檔**不吐新判決、不訂新門檻**，只報一個描述量：
等跨度帶內，K 個左緣的**最小間距**最大能做到多少，佔 R498 等距間距 `room/(K-1)` 的幾成。

用法：python3 ops/gain/r499_posthoc_dispersion.py [--json <path>]
"""
from __future__ import annotations
import argparse, json, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.gain import r495_empirical_census as R495                   # noqa: E402  (裝上 G-LIVE)
from ops.gain import r498_equal_chat_n as R498                       # noqa: E402
from ops.gain import r499_dual_constraint_feasibility as R499        # noqa: E402


def _greedy_ok(J, k, g):
    """能不能從已排序的 J 裡挑 k 個、相鄰間距都 >= g。貪婪取最早可行者＝最優。"""
    cnt, last = 1, J[0]
    for x in J[1:]:
        if x - last >= g:
            cnt += 1
            last = x
            if cnt >= k:
                return True
    return cnt >= k


def max_min_gap(J, k):
    """從已排序的 J 挑 k 個，最大化最小間距。二分搜尋（間距是整數索引）。"""
    if len(J) < k:
        return None
    lo, hi = 0, J[-1] - J[0]
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _greedy_ok(J, k, mid):
            lo = mid
        else:
            hi = mid - 1
    return lo


def best_dispersion(spans, tau, k):
    """對每個等跨度帶算 max-min-gap，取全域最大；回傳 (gap, 該帶細節)。"""
    best, det = None, None
    for i, s in enumerate(spans):
        hi = s * (1.0 + tau)
        J = [j for j, t in enumerate(spans) if s <= t <= hi]
        if len(J) < k:
            continue
        g = max_min_gap(J, k)
        if g is not None and (best is None or g > best):
            picked, last = [J[0]], J[0]
            for x in J[1:]:
                if x - last >= g and len(picked) < k:
                    picked.append(x)
                    last = x
            best, det = g, {"band_size": len(J), "lo_span": round(s, 1),
                            "picked_left_edges": picked}
    return best, det


def run(snapshot_path: str = R495.SNAPSHOT) -> dict:
    live_at_entry, t0 = R495._live_reads, time.time()
    snap = json.loads((ROOT / snapshot_path).read_text(encoding="utf-8"))
    rows = sorted([r for r in snap["rows"] if r.get("ts") is not None], key=lambda r: r["ts"])
    sub = R498.analysable(rows)
    ms, _ = R498.derive_M(rows)
    k = R499.K_PER_TIER
    out = {"posthoc_of": "R499", "note": "事後診斷，不改頭條", "M": list(ms),
           "n_analysable": len(sub), "K": k, "tiers": {}}
    for M in ms:
        spans = R499.spans_for(sub, M)
        room = len(spans) - 1
        even = room / (k - 1)                      # R496／R498 的等距間距
        rec = {"room": room, "even_gap_r498": round(even, 2), "per_tau": {}}
        for tau in R499.TOL_LADDER:
            g, det = best_dispersion(spans, tau, k)
            rec["per_tau"][f"{tau:g}"] = {
                "max_min_gap": g,
                "frac_of_even": (None if g is None else round(g / even, 4)),
                "picked": (det or {}).get("picked_left_edges")}
        out["tiers"][str(M)] = rec
    out["live_reads"] = R495._live_reads - live_at_entry
    out["elapsed_s"] = round(time.time() - t0, 1)
    return out


def selftest() -> int:
    fails = []

    def chk(n, c):
        if not c:
            fails.append(n)

    chk("gap_even", max_min_gap(list(range(0, 100)), 6) == 19)      # 99/5=19.8 -> 19
    chk("gap_short", max_min_gap([0, 1, 2], 6) is None)
    chk("gap_clustered", max_min_gap([0, 1, 2, 3, 4, 100], 6) == 1)
    chk("greedy_true", _greedy_ok([0, 10, 20, 30], 4, 10))
    chk("greedy_false", not _greedy_ok([0, 10, 20, 30], 4, 11))
    # 等距候選＋等跨度 ⇒ 分散度應該做到滿（frac_of_even == 1.0 附近）
    sub = [{"ts": 2.0 * i} for i in range(200)]
    g, _d = best_dispersion(R499.spans_for(sub, 50), 0.0, 6)
    chk("disp_flat", g == (150 // 5))
    # 帶太小 ⇒ None
    g2, _ = best_dispersion([1.0, 5.0, 9.0], 0.0, 6)
    chk("disp_none", g2 is None)
    n = 7
    print(f"posthoc selftest {n - len(fails)}/{n}" + (f"  FAILS={fails}" if fails else ""))
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    out = run()
    if a.json:
        p = ROOT / a.json
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"posthoc  M={out['M']}  K={out['K']}  live_reads={out['live_reads']}  "
          f"elapsed_s={out['elapsed_s']}")
    for M, rec in out["tiers"].items():
        print(f"  tier M={M}  room={rec['room']}  even_gap(R498)={rec['even_gap_r498']}")
        for tau, r in rec["per_tau"].items():
            print(f"    tau={tau:>5}  max_min_gap={r['max_min_gap']}  "
                  f"frac_of_even={r['frac_of_even']}  picked={r['picked']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
