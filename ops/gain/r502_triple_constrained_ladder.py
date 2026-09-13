#!/usr/bin/env python3
"""R502：組成軸（chat 佔比）是不是一條自由的軸？三重約束（等 chat-n ∧ 等跨度 ∧ 等組成）下的梯子。

判準先行：DECISION_20260905_R502_TRIPLE_CONSTRAINED_LADDER_PREREG.md（commit a97b1e8）。

第一段（有內容的那一段）：組成約束在「等 chat-n ∧ 等跨度」之下是不是 FORCED_BY_OTHERS。
第二段（以第一段判 COMP_FREE 為條件）：造三重約束設計並重跑 r489/r490 的梯子。

沿用（不重寫＝不製造第二套語意）：
  母體 R498.analysable ／ 層別 R498.derive_M ／ 分格 R496.classify ／
  切片跨度 R499.spans_for ／ 最大最小間距 R499P.max_min_gap ／ 探針 R495.probe_*

用法：
  python3 ops/gain/r502_triple_constrained_ladder.py --selftest
  python3 ops/gain/r502_triple_constrained_ladder.py --json ops/gain/data/r502_triple_constrained_ladder.json
"""
from __future__ import annotations
import argparse, json, math, os, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.gain import r495_empirical_census as R495                   # noqa: E402  (裝上 G-LIVE)
from ops.gain import r496_equal_n_windows as R496                    # noqa: E402
from ops.gain import r498_equal_chat_n as R498                       # noqa: E402
from ops.gain import r499_dual_constraint_feasibility as R499        # noqa: E402
from ops.gain import r499_posthoc_dispersion as R499P                # noqa: E402

TAU = 0.10                        # 判準 §一：τ_span == τ_comp，新增旋鈕零
K_PER_TIER = 6                    # 判準 §一（沿用 R499/R501）
DISP_MIN = 0.5                    # 判準 §一（沿用 R501，intent=guard）
M_EXPECTED = (364, 555)
N_WINDOWS_EXPECTED = 2 * K_PER_TIER
# R501 雙重約束下的 disp（判準 §三 P3 的對照值，來源 ops/gain/data/r501_dual_constrained_ladder.json）
R501_DISP = {364: 0.6731, 555: 0.9827}
R501_PINNED_EDGES = {364: [0, 49, 98, 147, 196, 248], 555: [0, 34, 68, 102, 136, 170]}

PROBES = [("r489_permutation_placebo", R495.probe_r489),
          ("r490_leveled_placebo", R495.probe_r490)]


def _mut() -> str:
    """突變旗標，**呼叫時**才讀（memory：寫在模組層永遠不生效）。"""
    return os.environ.get("R502_MUTANT", "")


# ── 組成量 ────────────────────────────────────────────────────────────────
def shares_for(rows, sub, M):
    """判準 §一：share_j = M / (該切片涵蓋的閘道**全部**列數)。長度同 R499.spans_for。"""
    pos = {id(r): j for j, r in enumerate(rows)}
    out = []
    for j in range(len(sub) - M + 1):
        n_total = pos[id(sub[j + M - 1])] - pos[id(sub[j])] + 1
        out.append(M / n_total)
    if _mut() == "M3_SHARE_CONST":
        return [0.5] * len(out)
    return out


def spread(vals):
    """(max-min)/min。空或非正的最小值 ⇒ None（不假裝算得出來）。"""
    if not vals:
        return None
    lo, hi = min(vals), max(vals)
    if lo <= 0:
        return None
    return (hi - lo) / lo


# ── 帶與挑點 ──────────────────────────────────────────────────────────────
def bands(spans, tau):
    """等跨度帶：以第 i 個切片當最短跨度，收 [s, s(1+tau)]。同 R499P.best_dispersion 的帶。"""
    for s in spans:
        hi = s * (1.0 + tau)
        yield [j for j, t in enumerate(spans) if s <= t <= hi]


def greedy_pick(J, k, g):
    """從已排序的 J 起點 J[0] 開始貪婪取 k 個、相鄰間距 >= g；取不滿回 None。"""
    picked, last = [J[0]], J[0]
    for x in J[1:]:
        if len(picked) >= k:
            break
        if x - last >= g:
            picked.append(x)
            last = x
    return picked if len(picked) == k else None


def dispersion(edges, room):
    """判準 §一：min_adjacent_gap / even_gap（R501 已證明有牙齒的那一個）。"""
    even = room / (K_PER_TIER - 1)
    if even <= 0:
        return None
    gap = min((b - a for a, b in zip(edges, edges[1:])), default=0)
    return gap / even


# ── 第一段：組成軸自由不自由 ───────────────────────────────────────────────
def comp_axis_census(spans, shares, room, tau=TAU, k=K_PER_TIER, disp_min=DISP_MIN):
    """判準 §二 第一段。回傳 dict：verdict / witness / band_max_spread / n_feasible_bands。"""
    even = room / (k - 1)
    G = math.ceil(disp_min * even)
    n_feasible, band_max, witness, over_upper = 0, None, None, 0
    for J in bands(spans, tau):
        if len(J) < k:
            continue
        g = R499P.max_min_gap(J, k)
        if g is None or g / even < disp_min:
            continue
        n_feasible += 1
        u = spread([shares[j] for j in J])          # 全帶上界
        if u is not None and (band_max is None or u > band_max):
            band_max = u
        if u is None or u <= tau:
            continue                                # 上界就擋住了 ⇒ 這個帶不可能出 witness
        over_upper += 1
        if witness is not None:
            continue
        for a in range(len(J)):                     # 有界決定性搜尋：每個起點貪婪一次
            e = greedy_pick(J[a:], k, G)
            if e is None:
                continue
            sp = spread([shares[j] for j in e])
            if sp is not None and sp > tau:
                witness = {"edges": e, "disp": round(dispersion(e, room), 4),
                           "shares": [round(shares[j], 4) for j in e],
                           "comp_spread": round(sp, 4),
                           "span_lo": round(min(spans[j] for j in e), 1),
                           "span_hi": round(max(spans[j] for j in e), 1)}
                break
    if n_feasible == 0:
        v = "COMP_UNSCANNED"                        # 「安靜量不到」第三型：掃到 0 個目標
    elif witness is not None:
        v = "COMP_FREE"
    elif over_upper == 0:
        v = "COMP_FORCED_BY_OTHERS"
    else:
        v = "COMP_UNRESOLVED_SEARCH"
    return {"verdict": v, "n_feasible_bands": n_feasible, "n_bands_over_upper_bound": over_upper,
            "band_max_spread": (None if band_max is None else round(band_max, 4)),
            "tau": tau, "min_gap_required": G, "witness": witness}


# ── 第二段：三重約束選左緣（對「<= tau」方向完備） ──────────────────────────
def triple_edges(spans, shares, room, tau=TAU, k=K_PER_TIER):
    """巢狀帶：等跨度帶內再收組成子帶，取 disp 最大者。回傳 (edges, detail) 或 (None, None)。"""
    even = room / (k - 1)
    tau_comp = 10.0 if _mut() == "M1_COMP_TAU_HUGE" else tau
    best, out, det = None, None, None
    for J in bands(spans, tau):
        if len(J) < k:
            continue
        subbands = [J] if _mut() == "M2_COMP_IGNORE" else [
            [j for j in J if c <= shares[j] <= c * (1.0 + tau_comp)] for c in [shares[j] for j in J]]
        for Jp in subbands:
            if len(Jp) < k:
                continue
            g = R499P.max_min_gap(Jp, k)
            if g is None:
                continue
            if _mut() != "M5_DISP_IGNORE" and g / even < DISP_MIN:
                continue
            if best is not None and g <= best:
                continue
            e = greedy_pick(Jp, k, g)
            if e is None:
                continue
            best, out = g, e
            det = {"band_size": len(J), "subband_size": len(Jp), "max_min_gap": g}
    if out is not None and _mut() == "M6_ONE_POSITION":
        out = out[:1]
    return out, det


def _cal_pos(rows, events):
    return "ALWAYS_SAME", 1.0


def _cal_neg(rows, events):
    return ("S" if len(R498.analysable(rows)) == _cal_neg.m_small else "L"), float(len(rows))


def posthoc_stage2_is_noop(snapshot_path: str = R495.SNAPSHOT) -> dict:
    """事後診斷（判準 §二 之外，**不是**頭條、不是證據）：第一段判 FORCED 時，
    三重約束的選點必然退化成 R501 的雙重約束選點。

    推導：全帶組成極差 <= tau ⇒ 以**最小** share 當錨點的組成子帶 == 整個帶
    ⇒ 巢狀搜尋的可行集包含雙重約束的可行集，且組成過濾砍不掉任何東西。
    本函式只是把這個推導在真資料上對一次，防我自己推錯（memory：推理推錯、跑一次才看出來）。
    """
    snap = json.loads((ROOT / snapshot_path).read_text(encoding="utf-8"))
    rows = sorted([r for r in snap["rows"] if r.get("ts") is not None], key=lambda r: r["ts"])
    sub = R498.analysable(rows)
    ms, _ = R498.derive_M(rows)
    out = {"posthoc_of": "R502", "note": "事後診斷，不改頭條，不算證據", "tiers": {}}
    for M in ms:
        spans = R499.spans_for(sub, M)
        shares = shares_for(rows, sub, M)
        room = len(spans) - 1
        e_triple, _d = triple_edges(spans, shares, room)
        e_dual = R501_PINNED_EDGES[M]
        out["tiers"][str(M)] = {
            "triple_edges": e_triple, "r501_dual_edges": e_dual,
            "identical": e_triple == e_dual,
            "disp_triple": None if e_triple is None else round(dispersion(e_triple, room), 4),
            "disp_r501": R501_DISP[M]}
    out["all_identical"] = all(t["identical"] for t in out["tiers"].values())
    return out


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
           "comp_axis": {}, "edges": {}, "disp": {}, "disp_r501": R501_DISP,
           "span_by_tier": {}, "span_spread": {}, "share_by_tier": {}, "comp_spread": {},
           "comp_binding": {}, "tools": {}, "blockers": [], "n_exceptions": 0}

    # ── 第一段
    per_tier_spans, per_tier_shares, per_tier_room = {}, {}, {}
    for M in ms:
        spans = R499.spans_for(sub, M)
        shares = shares_for(rows, sub, M)
        room = len(spans) - 1
        per_tier_spans[M], per_tier_shares[M], per_tier_room[M] = spans, shares, room
        out["comp_axis"][str(M)] = comp_axis_census(spans, shares, room)
    verds = {r["verdict"] for r in out["comp_axis"].values()}
    out["comp_axis_verdict"] = ("COMP_FREE" if "COMP_FREE" in verds else
                                "COMP_UNSCANNED" if "COMP_UNSCANNED" in verds else
                                "COMP_UNRESOLVED_SEARCH" if "COMP_UNRESOLVED_SEARCH" in verds else
                                "COMP_FORCED_BY_OTHERS")

    # ── 第二段（判準 §二：只在第一段判 COMP_FREE 時才跑）
    out["stage2_ran"] = (out["comp_axis_verdict"] == "COMP_FREE")
    if not out["stage2_ran"]:
        out["live_reads"] = R495._live_reads - live_at_entry
        out["elapsed_s"] = round(time.time() - t0, 1)
        out["verdict"] = "STAGE2_SKIPPED_" + out["comp_axis_verdict"]
        return out

    sliced = []
    for M in ms:
        spans, shares, room = per_tier_spans[M], per_tier_shares[M], per_tier_room[M]
        edges, det = triple_edges(spans, shares, room)
        if edges is None:
            out["blockers"].append("BROKEN_TRIPLE_INFEASIBLE")
            continue
        out["edges"][str(M)] = {"picked": edges, **(det or {})}
        d = dispersion(edges, room)
        out["disp"][str(M)] = None if d is None else round(d, 4)
        out["comp_binding"][str(M)] = (edges != R501_PINNED_EDGES[M])
        tier_spans, tier_shares = [], []
        for i, lo_s in enumerate(edges):
            hi_s = lo_s + M - 1
            lo_r, hi_r = pos[id(sub[lo_s])], pos[id(sub[hi_s])] + 1
            rws = rows[lo_r:hi_r]
            t_lo, t_hi = rws[0]["ts"], rws[-1]["ts"]
            evs = [e for e in events if e.get("ts") is not None and t_lo <= e["ts"] <= t_hi]
            tier_spans.append(t_hi - t_lo)
            tier_shares.append(shares[lo_s])
            sliced.append({"M": M, "i": i, "lo_sub": lo_s, "lo_row": lo_r, "hi_row": hi_r,
                           "n_rows_total": len(rws),
                           "n_sub": sum(1 for r in rws if id(r) in sub_ids),
                           "share": round(shares[lo_s], 4), "span_s": round(t_hi - t_lo, 1),
                           "events_in_window": len(evs), "_rows": rws, "_evs": evs})
        out["span_by_tier"][str(M)] = [round(s, 1) for s in tier_spans]
        out["span_spread"][str(M)] = round(spread(tier_spans), 4)
        out["share_by_tier"][str(M)] = [round(s, 4) for s in tier_shares]
        out["comp_spread"][str(M)] = round(spread(tier_shares), 4)

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
            recs.append({"N": rec["M"], **rec})
        cell, detail = R496.classify(v_full, recs)
        return {"full_verdict": v_full, "cell": cell, "detail": detail, "windows": recs}

    for name, fn in PROBES:
        out["tools"][name] = run_one(name, fn)

    def headline(cell):                                # 判準 §二：沿用 R501 §一.8
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
    # 判準 §三 P3／P3′
    out["p3_strict_shrink"] = any(
        out["disp"].get(str(M)) is not None and out["disp"][str(M)] < R501_DISP[M] for M in ms)
    out["p3prime_identity_holds"] = all(
        out["disp"].get(str(M)) is not None and out["disp"][str(M)] <= R501_DISP[M] + 1e-9 for M in ms)
    out["live_reads"] = R495._live_reads - live_at_entry
    out["elapsed_s"] = round(time.time() - t0, 1)

    # ── 擋門（判準 §五）
    if tuple(out["M"]) != M_EXPECTED:
        out["blockers"].append("BROKEN_DERIVED")
    if len(sliced) != N_WINDOWS_EXPECTED or any(
            len([w for w in sliced if w["M"] == M]) != K_PER_TIER for M in ms):
        out["blockers"].append("BROKEN_WINDOWS")
    if any(w["n_sub"] != w["M"] for w in sliced):
        out["blockers"].append("BROKEN_EQCHAT")
    if any(v is None or v > TAU for v in out["span_spread"].values()):
        out["blockers"].append("BROKEN_EQSPAN")
    if any(v is None or v > TAU for v in out["comp_spread"].values()):
        out["blockers"].append("BROKEN_EQCOMP")
    if any(d is None or d < DISP_MIN for d in out["disp"].values()):
        out["blockers"].append("BROKEN_DISPERSION")
    if out["n_exceptions"] != 0:
        out["blockers"].append("BROKEN_EXCEPTIONS")
    if out["calibration"]["C_POS"] != "NEITHER" or out["calibration"]["C_NEG"] != "N_MATTERS":
        out["blockers"].append("BROKEN_CALIBRATION")
    if out["live_reads"] != 0:
        out["blockers"].append("BROKEN_LIVE_READ")
    out["verdict"] = out["blockers"][0] if out["blockers"] else "TRIWIN_OK"
    return out


def selftest() -> int:
    fails = []

    def chk(name, cond):
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)

    # ── spread
    chk("spread_basic", abs(spread([4.0, 5.0]) - 0.25) < 1e-12)
    chk("spread_flat_zero", spread([3.0, 3.0, 3.0]) == 0.0)
    chk("spread_empty_none", spread([]) is None)

    # ── shares_for：合成快照，每 3 列有 1 列 chat；再讓後半段塞入額外非 chat 列
    def mkrow(ts, chat):
        return {"ts": float(ts), "path": "[gw] /v1/chat/completions" if chat else "[gw] /api/events",
                "model": "m" if chat else None, "error": None, "status_code": 200,
                "latency_ms": 100.0, "completion_tokens": 50 if chat else None,
                "prompt_tokens": 10 if chat else None, "finish_reason": "stop" if chat else None,
                "id": f"r{ts}", "total_tokens": None, "method": "POST" if chat else "GET"}
    rows = [mkrow(i, i % 3 == 0) for i in range(90)] + [mkrow(90 + i, i % 6 == 0) for i in range(90)]
    sub = R498.analysable(rows)
    sh = shares_for(rows, sub, 10)
    chk("shares_len", len(sh) == len(sub) - 10 + 1)
    chk("shares_in_unit", all(0.0 < s <= 1.0 for s in sh))
    # 🔴 有牙齒的夾具：組成**真的**在這份合成資料上變動（否則下面的 FREE/FORCED 全是空綠燈）
    chk("shares_actually_vary", spread(sh) > 0.10)
    # M3 突變體：share 變常數 ⇒ spread == 0
    os.environ["R502_MUTANT"] = "M3_SHARE_CONST"
    chk("shares_M3_constant", spread(shares_for(rows, sub, 10)) == 0.0)
    os.environ.pop("R502_MUTANT")
    chk("shares_clean_again", spread(shares_for(rows, sub, 10)) > 0.10)

    # ── greedy_pick / dispersion
    chk("greedy_ok", greedy_pick(list(range(0, 100)), 6, 19) == [0, 19, 38, 57, 76, 95])
    chk("greedy_short_none", greedy_pick([0, 1, 2], 6, 1) is None)
    chk("disp_even_is_one", abs(dispersion([0, 20, 40, 60, 80, 100], 100) - 1.0) < 1e-12)
    chk("disp_clustered_low", dispersion([0, 1, 2, 3, 4, 100], 100) < DISP_MIN)

    # ── comp_axis_census：兩個方向都要有夾具（只有一個方向 ⇒ 「什麼都判 X」也會全綠）
    n = 400
    flat_spans = [100.0] * n                         # 全部同跨度 ⇒ 一個大帶，分散度做得滿
    room = n - 1
    # 正對照（FREE）：組成在帶內大幅變動。**週期性**而非單調——單調的組成會讓「等組成」與
    # 「鋪得開」直接互斥（第一版夾具就是這樣，triple_edges 回 None），那種夾具看不見 M1/M2。
    varying = [0.30 * (1.0 + 0.15 * math.sin(2 * math.pi * j / 50.0)) for j in range(n)]
    c_free = comp_axis_census(flat_spans, varying, room)
    chk("census_free", c_free["verdict"] == "COMP_FREE")
    chk("census_free_has_witness", c_free["witness"] is not None
        and len(c_free["witness"]["edges"]) == K_PER_TIER
        and c_free["witness"]["comp_spread"] > TAU)
    chk("census_free_witness_disp_ok", c_free["witness"]["disp"] >= DISP_MIN)
    # 負對照（FORCED）：組成幾乎不動 ⇒ 全帶上界就擋住 ⇒ 不可能有 witness
    tight = [0.30 + 0.001 * (j / (n - 1)) for j in range(n)]
    c_forced = comp_axis_census(flat_spans, tight, room)
    chk("census_forced", c_forced["verdict"] == "COMP_FORCED_BY_OTHERS")
    chk("census_forced_no_witness", c_forced["witness"] is None)
    chk("census_forced_upper_zero", c_forced["n_bands_over_upper_bound"] == 0)
    # 第三格：掃不到可行帶 ⇒ UNSCANNED，不准跟 FORCED 混為一談
    c_uns = comp_axis_census([100.0, 200.0, 300.0], [0.3, 0.3, 0.3], 2)
    chk("census_unscanned", c_uns["verdict"] == "COMP_UNSCANNED")
    chk("census_unscanned_not_forced", c_uns["verdict"] != "COMP_FORCED_BY_OTHERS")

    # ── triple_edges：組成子帶真的有咬（乾淨 vs M2/M1）
    te_clean, _d = triple_edges(flat_spans, varying, room)
    chk("triple_clean_found", te_clean is not None and len(te_clean) == K_PER_TIER)
    chk("triple_clean_comp_ok", spread([varying[j] for j in te_clean]) <= TAU)
    for m in ("M2_COMP_IGNORE", "M1_COMP_TAU_HUGE"):
        os.environ["R502_MUTANT"] = m
        e, _ = triple_edges(flat_spans, varying, room)
        chk(f"triple_{m}_breaks_comp", e is not None and spread([varying[j] for j in e]) > TAU)
        os.environ.pop("R502_MUTANT")
    # M5 的夾具要讓**乾淨版取不到任何合格帶**（否則乾淨版挑到別的高分帶，M5 看不出來）
    m5_spans, m5_shares, m5_room = [100.0] * 20 + [1000.0] * 20, [0.3] * 40, 39
    chk("triple_M5_fixture_clean_none", triple_edges(m5_spans, m5_shares, m5_room)[0] is None)
    os.environ["R502_MUTANT"] = "M5_DISP_IGNORE"
    e5, _ = triple_edges(m5_spans, m5_shares, m5_room)
    chk("triple_M5_allows_low_disp", e5 is not None and dispersion(e5, m5_room) < DISP_MIN)
    os.environ.pop("R502_MUTANT")
    os.environ["R502_MUTANT"] = "M6_ONE_POSITION"
    e6, _ = triple_edges(flat_spans, varying, room)
    chk("triple_M6_one_edge", e6 is not None and len(e6) == 1)
    os.environ.pop("R502_MUTANT")
    te_again, _ = triple_edges(flat_spans, varying, room)
    chk("triple_clean_again", te_again == te_clean)

    # ── 沿用而非重寫：用 ast，不用字串比對（字串比對會匹配到這幾行自己）
    import ast as _ast
    tree = _ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
    defined = {n_.name for n_ in tree.body if isinstance(n_, _ast.FunctionDef)}
    chk("no_second_analysable", "analysable" not in defined)
    chk("no_second_classify", "classify" not in defined)
    chk("no_second_max_min_gap", "max_min_gap" not in defined)
    chk("ast_sees_own_defs", {"census", "comp_axis_census", "triple_edges"} <= defined)
    # 常數沒被本尺偷改
    chk("tau_is_r499_ladder_step", TAU in R499.TOL_LADDER)
    chk("k_matches_r499", K_PER_TIER == R499.K_PER_TIER)

    n_tot = 28
    print(f"selftest {n_tot - len(fails)}/{n_tot}" + (f"  FAILS={fails}" if fails else ""))
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--posthoc-stage2", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.posthoc_stage2:
        print(json.dumps(posthoc_stage2_is_noop(), ensure_ascii=False, indent=2))
        return 0
    out = census()
    if a.json:
        p = ROOT / a.json
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    keys = ("verdict", "blockers", "M", "n_analysable", "tau", "comp_axis_verdict", "stage2_ran",
            "edges", "disp", "disp_r501", "comp_binding", "span_spread", "comp_spread",
            "share_by_tier", "cells", "headlines", "calibration", "p3_strict_shrink",
            "p3prime_identity_holds", "live_reads", "n_exceptions", "elapsed_s")
    print(json.dumps({k: out[k] for k in keys if k in out}, ensure_ascii=False, indent=2))
    print(json.dumps({"comp_axis": out["comp_axis"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
