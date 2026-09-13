#!/usr/bin/env python3
"""R499：雙重約束（等被分析列數 ∧ 等時間跨度）視窗設計的**可行性**——先算塞不塞得下。

判準先行：DECISION_20260905_R499_DUAL_CONSTRAINT_FEASIBILITY_PREREG.md（commit dd1e43c）。

本尺**不量任何判決**。它只回答：這份閘道快照上，存不存在一組視窗同時
(a) 恰含 M 筆被分析列、(b) 跨度彼此相近到 τ 以內、(c) 左緣分散度 >= SPREAD_MIN。

用法：
  python3 ops/gain/r499_dual_constraint_feasibility.py --selftest
  python3 ops/gain/r499_dual_constraint_feasibility.py --json ops/gain/data/r499_dual_constraint.json
"""
from __future__ import annotations
import argparse, json, os, pathlib, statistics, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.gain import r495_empirical_census as R495                   # noqa: E402  (裝上 G-LIVE)
from ops.gain import r498_equal_chat_n as R498                       # noqa: E402
from ops.gain import r489_permutation_placebo as R489                # noqa: E402

# ---- 判準 §二 釘死的常數（本輪不准調） ----
K_PER_TIER = 6
SPREAD_MIN = 0.5
TOL_HEADLINE = 0.10
TOL_LADDER = (0.05, 0.10, 0.20, 0.30, 0.50, 0.75, 1.00, 2.00)
M_EXPECTED = (364, 555)          # 判準 §一.3：G-DERIVED 必須對上 R497 §三 記錄值


def _mut() -> str:
    """突變體旗標，**呼叫時**才讀（memory：寫在模組層永遠不生效）。"""
    return os.environ.get("R499_MUTANT", "")


def _spread_min() -> float:
    return 0.0 if _mut() == "M1_NO_SPREAD_REQ" else SPREAD_MIN


def _tol_headline() -> float:
    return 1e9 if _mut() == "M2_TOL_HUGE" else TOL_HEADLINE


def _band_min() -> int:
    return 2 if _mut() == "M4_BAND_K2" else K_PER_TIER


def spans_for(sub, M):
    """判準 §一.4：`sub` 上長度恰 M 的每個連續切片的時間跨度。"""
    return [sub[j + M - 1]["ts"] - sub[j]["ts"] for j in range(len(sub) - M + 1)]


def achievable(spans, tau, band_min=None):
    """判準 §一.8：精確解——枚舉「以第 i 個當最短跨度」的帶，取位置極差最大者。

    回傳 (pos_spread | None, 帶的細節)。room = len(spans) - 1。
    """
    k = _band_min() if band_min is None else band_min
    room = len(spans) - 1
    best, best_detail = None, None
    if room <= 0:
        return None, None
    for i, s in enumerate(spans):
        hi = s * (1.0 + tau)
        J = [j for j, t in enumerate(spans) if s <= t <= hi]
        if len(J) < k:
            continue
        ps = (J[-1] - J[0]) / room
        if best is None or ps > best:
            # 判準 §一.8：取兩端＋任意 k-2 個填充
            chosen = [J[0], J[-1]] + [j for j in J[1:-1]][: max(0, k - 2)]
            best, best_detail = ps, {"lo_span": s, "hi_span": hi, "band_size": len(J),
                                     "chosen": sorted(chosen)}
    return best, best_detail


def _rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for t in range(i, j + 1):
            r[order[t]] = avg
        i = j + 1
    return r


def spearman(xs):
    """spans 對其索引 j 的 Spearman rho（j 本身已是 0..n-1 的秩）。"""
    n = len(xs)
    if n < 3:
        return None
    a, b = _rank(xs), _rank(list(range(n)))
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    return None if da == 0 or db == 0 else round(num / (da * db), 4)


def evaluate(tiers):
    """判準 §三：tiers = {M: spans}。回傳含頭條判決的 dict。純函式，夾具可獨立設定每個輸入。"""
    out = {"K_per_tier": K_PER_TIER, "spread_min": _spread_min(),
           "tol_headline": _tol_headline(), "tol_ladder": list(TOL_LADDER),
           "tiers": {}, "frontier": {}, "rho_span_vs_pos": {}}
    for M, spans in sorted(tiers.items()):
        if not spans or min(spans) <= 0:
            out["verdict"] = "BROKEN_NONPOS_SPAN"
            out["nonpos_tier"] = M
            out["nonpos_min_span"] = (min(spans) if spans else None)
            return out
        out["tiers"][str(M)] = {"n_candidates": len(spans), "room": len(spans) - 1,
                                "span_min": round(min(spans), 1), "span_max": round(max(spans), 1),
                                "span_median": round(statistics.median(spans), 1)}
        out["rho_span_vs_pos"][str(M)] = spearman(spans)
        out["frontier"][str(M)] = {}
        for tau in TOL_LADDER:
            ps, _d = achievable(spans, tau)
            out["frontier"][str(M)][f"{tau:g}"] = (None if ps is None else round(ps, 4))

    head = {}
    for M, spans in sorted(tiers.items()):
        ps, det = achievable(spans, _tol_headline())
        rec = {"achievable": (None if ps is None else round(ps, 4)), "detail": None}
        if det is not None:
            ch = det["chosen"]
            sel = [spans[j] for j in ch]
            rec["detail"] = {"band_size": det["band_size"], "chosen_left_edges": ch,
                             "spans": [round(s, 1) for s in sel],
                             # 判準 §一.5：兩個分母都報，並斷言 median 版 <= min 版
                             "spread_min_denom": round((max(sel) - min(sel)) / min(sel), 4),
                             "spread_median_denom": round(
                                 (max(sel) - min(sel)) / statistics.median(sel), 4)}
        head[str(M)] = rec
    out["headline_per_tier"] = head

    # 判準 §四 P6（IDENTITY guard）：median 分母版必定 <= min 分母版
    out["p6_inequality_holds"] = all(
        r["detail"] is None or r["detail"]["spread_median_denom"] <= r["detail"]["spread_min_denom"]
        for r in head.values())

    ok = [r["achievable"] is not None and r["achievable"] >= _spread_min() for r in head.values()]
    out["verdict"] = "DUAL_FEASIBLE" if (ok and all(ok)) else "DUAL_INFEASIBLE"
    return out


def _cal_pos():
    """等間隔到達 ⇒ 任何等 M 視窗跨度相同 ⇒ 必須 DUAL_FEASIBLE。"""
    sub = [{"ts": 100.0 + 2.0 * i} for i in range(200)]
    return evaluate({50: spans_for(sub, 50)})


def _cal_neg():
    """中途速率變 10 倍 ⇒ 跨度隨位置劇變 ⇒ 必須 DUAL_INFEASIBLE。"""
    ts, t = [], 0.0
    for i in range(200):
        t += 1.0 if i < 100 else 10.0
        ts.append(t)
    sub = [{"ts": v} for v in ts]
    return evaluate({50: spans_for(sub, 50)})


def census(snapshot_path: str = R495.SNAPSHOT) -> dict:
    live_at_entry = R495._live_reads
    t0 = time.time()
    snap = json.loads((ROOT / snapshot_path).read_text(encoding="utf-8"))
    rows = [r for r in snap["rows"] if r.get("ts") is not None]
    if _mut() != "M3_UNSORTED":                     # 突變：不依 ts 排序
        rows = sorted(rows, key=lambda r: r["ts"])

    sub = R498.analysable(rows)                     # 判準 §一.2：不自己重寫過濾器
    ms, per_tier = R498.derive_M(rows)              # 判準 §一.3：G-DERIVED

    out = {"snapshot": snapshot_path, "n_rows": len(rows),
           "n_chat": sum(1 for r in rows if R489.is_chat(r)), "n_analysable": len(sub),
           "M": list(ms), "M_expected": list(M_EXPECTED),
           "r496_tier_chat_counts": per_tier, "mutant": _mut(), "n_exceptions": 0}

    if tuple(ms) != M_EXPECTED:
        out["verdict"] = "BROKEN_M_DRIFT"
    else:
        try:
            res = evaluate({M: spans_for(sub, M) for M in ms})
            out.update(res)
        except Exception as e:                       # 偵測器不准 crash 收場
            out["n_exceptions"] = 1
            out["verdict"] = "BROKEN_EXC"
            out["exception"] = f"{type(e).__name__}: {e}"

    out["live_reads"] = R495._live_reads - live_at_entry
    if out["live_reads"] != 0:
        out["verdict"] = "BROKEN_LIVE_READ"
    out["calibration"] = {"C_POS": _cal_pos()["verdict"], "C_NEG": _cal_neg()["verdict"]}
    out["elapsed_s"] = round(time.time() - t0, 1)
    return out


def selftest() -> int:
    fails = []

    def chk(name, cond):
        if not cond:
            fails.append(name)

    # --- 校準（合成，與真資料無關） ---
    chk("C_POS", _cal_pos()["verdict"] == "DUAL_FEASIBLE")
    chk("C_NEG", _cal_neg()["verdict"] == "DUAL_INFEASIBLE")

    # --- spans_for ---
    sub = [{"ts": float(i)} for i in range(10)]
    chk("spans_len", len(spans_for(sub, 4)) == 7)
    chk("spans_val", all(s == 3.0 for s in spans_for(sub, 4)))

    # --- achievable：等跨度 ⇒ 全帶 ⇒ 位置分散度 1.0 ---
    ps, det = achievable([5.0] * 20, 0.0, band_min=6)
    chk("ach_flat", ps == 1.0 and det["band_size"] == 20)
    # 單調遞增跨度且 τ=0 ⇒ 每帶只有 1 個 ⇒ None
    ps2, _ = achievable([float(i + 1) for i in range(20)], 0.0, band_min=6)
    chk("ach_strict_none", ps2 is None)
    # 帶大小不足 ⇒ None（K 這道加嚴要真的擋得住）
    ps3, _ = achievable([1.0, 1.0, 1.0, 9.0, 9.0], 0.0, band_min=6)
    chk("ach_band_short", ps3 is None)
    # τ 放寬到吃下全部 ⇒ 1.0
    ps4, _ = achievable([float(i + 1) for i in range(20)], 19.0, band_min=6)
    chk("ach_wide", ps4 == 1.0)

    # --- 單調性（P3 的 IDENTITY，在合成資料上窮舉） ---
    sp = [1.0, 3.0, 2.0, 8.0, 5.0, 4.0, 6.0, 7.0, 2.5, 3.5, 4.5, 9.0]
    vals = [achievable(sp, t, band_min=3)[0] for t in (0.0, 0.1, 0.5, 1.0, 5.0, 100.0)]
    seq = [(-1.0 if v is None else v) for v in vals]
    chk("mono_frontier", all(a <= b for a, b in zip(seq, seq[1:])))

    # --- spearman ---
    chk("rho_up", spearman([1.0, 2.0, 3.0, 4.0, 5.0]) == 1.0)
    chk("rho_down", spearman([5.0, 4.0, 3.0, 2.0, 1.0]) == -1.0)
    chk("rho_short", spearman([1.0, 2.0]) is None)

    # --- 非正跨度擋門 ---
    bad = evaluate({4: [3.0, -1.0, 3.0]})
    chk("nonpos", bad["verdict"] == "BROKEN_NONPOS_SPAN" and bad["nonpos_tier"] == 4)
    zero = evaluate({4: [3.0, 0.0, 3.0]})
    chk("zero_span", zero["verdict"] == "BROKEN_NONPOS_SPAN")

    # --- 兩個分母的不等式（P6），合成上窮舉 ---
    ok = True
    for sel in ([1.0, 2.0, 3.0], [5.0, 5.0, 9.0], [2.0, 100.0, 100.0]):
        a = (max(sel) - min(sel)) / min(sel)
        b = (max(sel) - min(sel)) / statistics.median(sel)
        ok = ok and b <= a
    chk("p6_identity", ok)

    # --- 頭條判決兩個方向都到得了（不是恆定） ---
    chk("verdict_feasible_reachable", evaluate({5: [7.0] * 30})["verdict"] == "DUAL_FEASIBLE")
    chk("verdict_infeasible_reachable",
        evaluate({5: [float(i + 1) for i in range(30)]})["verdict"] == "DUAL_INFEASIBLE")

    # --- 常數沒被偷改 ---
    chk("const_k", K_PER_TIER == 6)
    chk("const_spread", SPREAD_MIN == 0.5)
    chk("const_tol", TOL_HEADLINE == 0.10)
    chk("const_ladder", TOL_LADDER == (0.05, 0.10, 0.20, 0.30, 0.50, 0.75, 1.00, 2.00))
    chk("const_M", M_EXPECTED == (364, 555))

    # --- 突變體旗標是呼叫時才讀（不是模組層） ---
    old = os.environ.get("R499_MUTANT", "")
    os.environ["R499_MUTANT"] = "M1_NO_SPREAD_REQ"
    chk("mut_runtime", _spread_min() == 0.0)
    os.environ["R499_MUTANT"] = old

    n = 24
    print(f"selftest {n - len(fails)}/{n}" + (f"  FAILS={fails}" if fails else ""))
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--snapshot", default=R495.SNAPSHOT)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    out = census(a.snapshot)
    if a.json:
        p = ROOT / a.json
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"verdict={out['verdict']}  M={out.get('M')}  n_analysable={out.get('n_analysable')}  "
          f"live_reads={out.get('live_reads')}  exc={out.get('n_exceptions')}  "
          f"elapsed_s={out.get('elapsed_s')}")
    print(f"calibration: {out.get('calibration')}")
    if out.get("headline_per_tier"):
        for M, r in out["headline_per_tier"].items():
            print(f"  tier M={M}: achievable(tau={out['tol_headline']:g})={r['achievable']}  "
                  f"(SPREAD_MIN={out['spread_min']})  detail={r['detail']}")
    if out.get("frontier"):
        print(f"  frontier: {json.dumps(out['frontier'], ensure_ascii=False)}")
        print(f"  rho_span_vs_pos: {out.get('rho_span_vs_pos')}  p6={out.get('p6_inequality_holds')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
