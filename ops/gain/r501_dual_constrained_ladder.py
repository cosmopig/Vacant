#!/usr/bin/env python3
"""R501：雙重約束（等被分析列數 ∧ 等跨度）視窗下，重跑 r489/r490 的梯子判決。

判準先行：DECISION_20260905_R501_DUAL_CONSTRAINED_LADDER_PREREG.md（commit dd3c861，rebase 前為 541c587）。

R498 固定了被分析的 chat 列數，但跨度沒夾（極差 0.5591／0.2297）＝只是換了殘留混淆。
R499 證明「等 n ∧ 等跨度」在這份快照上塞得下。本尺把那個設計造出來並真的跑判決。

沿用（不重寫＝不製造第二套語意）：
  母體過濾 R498.analysable ／ 層別 R498.derive_M ／ 分格 R496.classify ／
  切片跨度 R499.spans_for ／ 分散度 R499_POSTHOC.best_dispersion

用法：
  python3 ops/gain/r501_dual_constrained_ladder.py --selftest
  python3 ops/gain/r501_dual_constrained_ladder.py --json ops/gain/data/r501_dual_constrained_ladder.json
"""
from __future__ import annotations
import argparse, json, os, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.gain import r495_empirical_census as R495                   # noqa: E402  (裝上 G-LIVE)
from ops.gain import r496_equal_n_windows as R496                    # noqa: E402
from ops.gain import r498_equal_chat_n as R498                       # noqa: E402
from ops.gain import r499_dual_constraint_feasibility as R499        # noqa: E402
from ops.gain import r499_posthoc_dispersion as R499P                # noqa: E402
from ops.gain import r489_permutation_placebo as R489                # noqa: E402

TAU = 0.10                       # 判準 §一.4：R499 頭條那一階，不是本輪挑的
K_PER_TIER = 6                   # 判準 §一.5
DISP_MIN = 0.5                   # 判準 §一.6，intent=guard（R499 已公布 0.6731／0.9827）
M_EXPECTED = (364, 555)          # 判準 §一.3，G-DERIVED 現算必須對上
N_WINDOWS_EXPECTED = 2 * K_PER_TIER

# 判準 §一.5：釘死字面值（來源 ops/gain/data/r499_posthoc_dispersion.json，tau=0.1）
PINNED_EDGES = {364: [0, 49, 98, 147, 196, 248],
                555: [0, 34, 68, 102, 136, 170]}

PROBES = [("r489_permutation_placebo", R495.probe_r489),
          ("r490_leveled_placebo", R495.probe_r490)]


def _mut() -> str:
    """突變體旗標，**呼叫時**才讀（memory：寫在模組層永遠不生效）。"""
    return os.environ.get("R501_MUTANT", "")


def pinned_for(M):
    """判準 §一.5 的字面值。M3 突變體動的是**這個常數**，不是實際用的左緣。"""
    e = list(PINNED_EDGES[M])
    if _mut() == "M3_PIN_SHIFT":
        return [x + 1 for x in e]
    return e


def min_gap(edges):
    """相鄰最小間距。少於 2 個左緣時沒有間距可言 ⇒ 0。"""
    return min((b - a for a, b in zip(edges, edges[1:])), default=0)


def dispersion(edges, room):
    """判準 §一.6：min_adjacent_gap / even_gap，even_gap = room/(K-1)。

    取代 R499 §一.6 的 `pos_spread=(max-min)/room`——後者只管兩端，
    中間全部重合也拿滿分（R499 `M4_BAND_K2` MISSED 就是這個缺陷的另一面）。
    """
    even = room / (K_PER_TIER - 1)
    if even <= 0:
        return None
    return round(min_gap(edges) / even, 4)


def edges_for(sub, M):
    """實際要用的左緣。M1/M2/M5 動這裡；G-PINNED 的重算不受影響（專一性）。"""
    p = pinned_for(M)
    m = _mut()
    if m == "M1_ONE_POSITION":
        return p[:1]
    if m == "M2_R498_EDGES":
        # 退回 R498 的等距左緣（只等 n，不管跨度）
        room = len(sub) - M
        return [room * i // (K_PER_TIER - 1) for i in range(K_PER_TIER)]
    if m == "M5_CLUSTERED":
        # R499 舊解法的群聚形狀：五個幾乎重合＋一個遠端
        return [p[0], p[0] + 1, p[0] + 2, p[0] + 3, p[0] + 4, p[-1]]
    return p


def _cal_pos(rows, events):
    return "ALWAYS_SAME", 1.0


def _cal_neg(rows, events):
    """回層別字母 ⇒ 層內恆定、層間不同 ⇒ 必須落 N_MATTERS。"""
    return ("S" if len(R498.analysable(rows)) == _cal_neg.m_small else "L"), float(len(rows))


def census(snapshot_path: str = R495.SNAPSHOT) -> dict:
    live_at_entry, t0 = R495._live_reads, time.time()
    snap = json.loads((ROOT / snapshot_path).read_text(encoding="utf-8"))
    rows = sorted([r for r in snap["rows"] if r.get("ts") is not None], key=lambda r: r["ts"])
    events = snap.get("events") or []
    sub = R498.analysable(rows)
    ms, _per_tier = R498.derive_M(rows)
    _cal_neg.m_small = ms[0]
    pos = {id(r): j for j, r in enumerate(rows)}
    sub_ids = {id(r) for r in sub}

    out = {"snapshot": snapshot_path, "n_rows_sorted": len(rows), "n_events": len(events),
           "n_analysable": len(sub), "M": list(ms), "M_expected": list(M_EXPECTED),
           "tau": TAU, "K": K_PER_TIER, "disp_min": DISP_MIN,
           "pinned_edges": {str(k): v for k, v in sorted(PINNED_EDGES.items())},
           "recomputed_edges": {}, "pin_match": {}, "disp": {}, "span_by_tier": {},
           "span_spread": {}, "tools": {}, "blockers": [], "n_exceptions": 0}

    sliced = []
    for M in ms:
        spans = R499.spans_for(sub, M)
        room = len(spans) - 1
        # G-PINNED：現場重算一次（判準 §一.5）——不受 edges_for 的突變影響
        _g, det = R499P.best_dispersion(spans, TAU, K_PER_TIER)
        recomputed = (det or {}).get("picked_left_edges")
        out["recomputed_edges"][str(M)] = recomputed
        out["pin_match"][str(M)] = (recomputed == pinned_for(M))

        edges = edges_for(sub, M)
        out["disp"][str(M)] = dispersion(edges, room)
        tier_spans = []
        for i, lo_s in enumerate(edges):
            hi_s = lo_s + M - 1
            lo_r, hi_r = pos[id(sub[lo_s])], pos[id(sub[hi_s])] + 1
            rws = rows[lo_r:hi_r]
            t_lo, t_hi = rws[0]["ts"], rws[-1]["ts"]
            evs = [e for e in events if e.get("ts") is not None and t_lo <= e["ts"] <= t_hi]
            tier_spans.append(t_hi - t_lo)
            sliced.append({"M": M, "i": i, "lo_sub": lo_s, "lo_row": lo_r, "hi_row": hi_r,
                           "n_rows_total": len(rws), "n_sub": sum(1 for r in rws if id(r) in sub_ids),
                           "span_s": round(t_hi - t_lo, 1), "events_in_window": len(evs),
                           "_rows": rws, "_evs": evs})
        out["span_by_tier"][str(M)] = [round(s, 1) for s in tier_spans]
        out["span_spread"][str(M)] = round((max(tier_spans) - min(tier_spans)) / min(tier_spans), 4)

    def run_one(name, fn):
        v_full, _s = fn(rows, events)
        recs = []
        for w in sliced:
            rec = {k: v for k, v in w.items() if not k.startswith("_")}
            try:
                v, s = fn(w["_rows"], w["_evs"])
                rec["verdict"], rec["stat"], rec["error"] = v, s, None
            except Exception as e:
                rec["verdict"], rec["stat"] = None, None
                rec["error"] = f"{type(e).__name__}: {e}"
                out["n_exceptions"] += 1
            if _mut() == "M4_FORCE_SAME" and rec["error"] is None:
                rec["verdict"] = v_full
            recs.append({"N": rec["M"], **rec})       # R496.classify 讀 "N"
        cell, detail = R496.classify(v_full, recs)
        return {"full_verdict": v_full, "cell": cell, "detail": detail, "windows": recs}

    for name, fn in PROBES:
        out["tools"][name] = run_one(name, fn)

    def headline(cell):                               # 判準 §一.8：沿用 R498 的映射
        if cell in ("POSITION_MATTERS", "BOTH"):
            return "POSITION_SURVIVES"
        if cell in ("NEITHER", "NEW_CELL_UNIFORM_SHIFT"):
            return "POSITION_GONE"
        if cell == "N_MATTERS":
            return "N_ONLY"
        return "UNSCANNED"

    out["cells"] = {k: v["cell"] for k, v in out["tools"].items()}
    out["headlines"] = {k: headline(v["cell"]) for k, v in out["tools"].items()}

    cpos, cneg = run_one("C_POS", _cal_pos), run_one("C_NEG", _cal_neg)
    out["calibration"] = {"C_POS": cpos["cell"], "C_NEG": cneg["cell"]}
    out["live_reads"] = R495._live_reads - live_at_entry
    out["elapsed_s"] = round(time.time() - t0, 1)

    # ── 擋門（判準 §四／§一）
    if tuple(out["M"]) != M_EXPECTED:
        out["blockers"].append("BROKEN_DERIVED")
    if not all(out["pin_match"].values()):
        out["blockers"].append("BROKEN_PINNED")
    if len(sliced) != N_WINDOWS_EXPECTED or any(
            len([w for w in sliced if w["M"] == M]) != K_PER_TIER for M in ms):
        out["blockers"].append("BROKEN_WINDOWS")
    if any(w["n_sub"] != w["M"] for w in sliced):
        out["blockers"].append("BROKEN_EQCHAT")
    if any(d is None or d < DISP_MIN for d in out["disp"].values()):
        out["blockers"].append("BROKEN_DISPERSION")
    if any(v > TAU for v in out["span_spread"].values()):
        out["blockers"].append("BROKEN_EQSPAN")
    if out["n_exceptions"] != 0:
        out["blockers"].append("BROKEN_EXCEPTIONS")
    if out["calibration"]["C_POS"] != "NEITHER" or out["calibration"]["C_NEG"] != "N_MATTERS":
        out["blockers"].append("BROKEN_CALIBRATION")
    if out["live_reads"] != 0:
        out["blockers"].append("BROKEN_LIVE_READ")
    out["verdict"] = out["blockers"][0] if out["blockers"] else "DUALWIN_OK"
    return out


def selftest() -> int:
    fails = []

    def chk(name, cond):
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)

    # ── min_gap / dispersion：合成資料，兩個方向
    chk("gap_even", min_gap([0, 10, 20, 30]) == 10)
    chk("gap_clustered", min_gap([0, 1, 2, 3, 4, 100]) == 1)
    chk("gap_single", min_gap([7]) == 0)
    # 等距左緣 ⇒ disp 應為 1.0（room=100, even=20, gap=20）
    chk("disp_even_is_one", dispersion([0, 20, 40, 60, 80, 100], 100) == 1.0)
    # 群聚左緣 ⇒ disp 遠低於門檻（這是 M5 該被看見的那個量）
    chk("disp_clustered_low", dispersion([0, 1, 2, 3, 4, 100], 100) == 0.05)
    chk("disp_clustered_below_min", dispersion([0, 1, 2, 3, 4, 100], 100) < DISP_MIN)
    # 🔴 專一性：R499 舊的 pos_spread 對這兩組給相同分數，新的不給
    old_even = (100 - 0) / 100
    old_clu = (100 - 0) / 100
    chk("old_metric_cannot_tell", old_even == old_clu)
    chk("new_metric_can_tell",
        dispersion([0, 20, 40, 60, 80, 100], 100) != dispersion([0, 1, 2, 3, 4, 100], 100))

    # ── pinned_for：乾淨回字面值；M3 平移
    chk("pin_clean", pinned_for(364) == [0, 49, 98, 147, 196, 248])
    os.environ["R501_MUTANT"] = "M3_PIN_SHIFT"
    chk("pin_m3_shifts", pinned_for(364) == [1, 50, 99, 148, 197, 249])
    os.environ.pop("R501_MUTANT")
    chk("pin_clean_again", pinned_for(364) == [0, 49, 98, 147, 196, 248])

    # ── edges_for：合成 sub，每個突變體都要有看得見它的夾具
    sub = [{"ts": 1.0 * i} for i in range(700)]
    chk("edges_clean", edges_for(sub, 364) == PINNED_EDGES[364])
    for m, want in (("M1_ONE_POSITION", 1), ("M2_R498_EDGES", 6), ("M5_CLUSTERED", 6)):
        os.environ["R501_MUTANT"] = m
        e = edges_for(sub, 364)
        chk(f"edges_{m}_len", len(e) == want)
        if m == "M5_CLUSTERED":
            chk("edges_M5_is_clustered", min_gap(e) == 1)
        if m == "M2_R498_EDGES":
            chk("edges_M2_is_equidistant", len(set(
                b - a for a, b in zip(e, e[1:]))) <= 2)
        os.environ.pop("R501_MUTANT")

    # ── R499.spans_for 的常數沒被本尺改掉
    chk("tau_is_r499_ladder_step", TAU in R499.TOL_LADDER)
    chk("k_matches_r499", K_PER_TIER == R499.K_PER_TIER)
    # ── 沿用而非重寫：本尺不得自己定義 analysable/classify
    # 用 ast，不用字串比對——字串比對會匹配到這幾行自己（memory 記過的坑）
    import ast as _ast
    tree = _ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
    defined = {n.name for n in tree.body if isinstance(n, _ast.FunctionDef)}
    chk("no_second_analysable", "analysable" not in defined)
    chk("no_second_classify", "classify" not in defined)
    # 正對照：ast 這條真的看得見模組層的 def（否則「什麼都沒定義」也會全綠）
    chk("ast_sees_own_defs", {"census", "dispersion", "edges_for"} <= defined)

    n = 21
    print(f"selftest {n - len(fails)}/{n}" + (f"  FAILS={fails}" if fails else ""))
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    out = census()
    if a.json:
        p = ROOT / a.json
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    slim = {k: out[k] for k in ("verdict", "blockers", "M", "n_analysable", "tau",
                                "pin_match", "disp", "span_spread", "cells", "headlines",
                                "calibration", "live_reads", "n_exceptions", "elapsed_s")}
    print(json.dumps(slim, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
