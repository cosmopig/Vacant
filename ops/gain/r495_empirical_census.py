#!/usr/bin/env python3
"""R495：R486–R490 判決的 **EMPIRICAL 半邊**可證偽性普查。

判準先行：DECISION_20260905_R495_R486_R490_EMPIRICAL_CENSUS_PREREG.md（commit 4f9f4c1）。

R494 答的是 IDENTITY 半邊（結構上可不可能為假）。本尺答被它明文排除的那半邊：
**那份閘道快照翻不翻得動這些判決**。擾動族只有一個，事前釘死：時間上的連續子視窗。

⚠ `EMPIRICAL_FIXED` 只准讀成「這一族擾動翻不動它」，不准讀成「沒有任何資料翻得動它」。

用法：
  python3 ops/gain/r495_empirical_census.py --selftest
  python3 ops/gain/r495_empirical_census.py --json ops/gain/data/r495_empirical_census.json
"""
from __future__ import annotations
import argparse, json, os, pathlib, sys, time, traceback

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

LIVE = "g_r461_lcb3_three_arm"
_live_reads = 0
_real_open = open


def _guarded_open(file, *a, **k):            # G-LIVE：唯一的開檔入口
    global _live_reads
    if LIVE in str(file) and os.environ.get("R495_MUTANT", "") != "M3_NO_GLIVE":
        _live_reads += 1
        raise RuntimeError(f"G-LIVE: 拒絕碰主 run 的路徑：{file}")
    return _real_open(file, *a, **k)


import builtins                                                      # noqa: E402
builtins.open = _guarded_open

from ops.gain import r486_longreq_attrib as R486                     # noqa: E402
from ops.gain import r487_concurrency_tax as R487                    # noqa: E402
from ops.gain import r487_ts_semantics as R487TS                     # noqa: E402
from ops.gain import r488_pointwise_concurrency as R488              # noqa: E402
from ops.gain import r489_permutation_placebo as R489                # noqa: E402
from ops.gain import r490_leveled_placebo as R490                    # noqa: E402

SNAPSHOT = "ops/gain/data/r486_gateway_snapshot_v2.json"
FRACTIONS = (0.6, 0.8)
K_PER_FRACTION = 6
N_WINDOWS_EXPECTED = len(FRACTIONS) * K_PER_FRACTION          # G-N

# 判準 §一：觀測判決（＝落盤結果檔記的那個），事前釘死，G-REPRO 逐字比對
EXPECTED_FULL = {
    "r486_longreq_attrib":        "QUEUE_LIVE",
    "r486_events_full":           "QUEUE_LIVE",
    "r487_concurrency_tax":       "CONCURRENCY_TAXES",
    "r487_ts_semantics":          "TS_IS_START",
    "r488_pointwise_concurrency": "PLACEBO_UNSCANNED",
    "r489_permutation_placebo":   "PLACEBO_LADDER_BROKEN",
    "r490_leveled_placebo":       "PLACEBO_LADDER_BROKEN",
}


def _mut() -> str:
    """突變體旗標，**呼叫時**才讀（絕不在 import 時讀）。"""
    return os.environ.get("R495_MUTANT", "")


# ───────────────────────────────────────────── 被測工具：判決路徑 + 指名統計量
def probe_r486(rows, events):
    o = R486.analyze_under(rows, events, "start")
    return o.get("p1_verdict"), o.get("queue_share")


def probe_r486_events_full(rows, events, _all_events):
    o = R486.analyze_under(rows, _all_events, "start")
    return o.get("p1_verdict"), o.get("queue_share")


def probe_r487(rows, events):
    o = R487.analyze_one(rows, events, "start", "tok")
    return o.get("p1"), o.get("ratio")


def probe_r487ts(rows, events):
    o = R487TS.analyze(rows)
    return o.get("verdict"), (o.get("inv") or {}).get("ts_plus_lat")


def probe_r488(rows, events):
    o = R488.analyse(rows, "start")
    return o.get("verdict"), ((o.get("real") or {}).get("ratio"))


def probe_r489(rows, events):
    o = R489.analyse(rows, "start")
    return o.get("verdict"), ((o.get("real") or {}).get("ratio"))


def probe_r490(rows, events):
    o = R490.analyse(rows, "start", reps=R490.R_REPLICATES)
    return o.get("verdict"), ((o.get("real") or {}).get("abs_log"))


PROBES = [
    ("r486_longreq_attrib", probe_r486),
    ("r486_events_full", None),                 # 特例：events 不隨視窗切（見 §報告）
    ("r487_concurrency_tax", probe_r487),
    ("r487_ts_semantics", probe_r487ts),
    ("r488_pointwise_concurrency", probe_r488),
    ("r489_permutation_placebo", probe_r489),
    ("r490_leveled_placebo", probe_r490),
]


# ───────────────────────────────────────────────────────────── 擾動族：連續子視窗
def windows(t0: float, t1: float):
    """判準 §二：f ∈ FRACTIONS，各 K 個左緣等距的連續視窗。回傳 [(f, i, lo, hi)]。"""
    span = t1 - t0
    out = []
    ks = 1 if _mut() == "M1_NO_SUBWINDOWS" else K_PER_FRACTION
    fr = (1.0,) if _mut() == "M1_NO_SUBWINDOWS" else FRACTIONS
    for f in fr:
        room = span * (1.0 - f)
        for i in range(ks):
            lo = t0 + (room * i / (ks - 1)) if ks > 1 else t0
            out.append((f, i, lo, lo + span * f))
    return out


def slice_rows(rows, lo, hi):
    return [r for r in rows if r.get("ts") is not None and lo <= r["ts"] <= hi]


# ─────────────────────────────────────────────────────────────────── 分類（§三）
def classify(full_verdict, results):
    """results: [{'verdict':.., 'stat':.., 'error':..}]  ⇒ (cell, detail)"""
    ok = [r for r in results if r.get("error") is None]
    errs = len(results) - len(ok)
    exc_rate = (errs / len(results)) if results else 1.0
    verdicts = sorted({r["verdict"] for r in ok})
    moved = [v for v in verdicts if v != full_verdict]
    stats = [r["stat"] for r in ok if isinstance(r.get("stat"), (int, float))]
    rng = (max(stats) - min(stats)) if stats else None
    detail = {"n_windows": len(results), "n_ok": len(ok), "n_error": errs,
              "exc_rate": round(exc_rate, 4), "verdicts_seen": verdicts,
              "moved_to": moved, "stat_n": len(stats),
              "stat_min": min(stats) if stats else None,
              "stat_max": max(stats) if stats else None,
              "stat_range": rng}
    if not ok:
        return "EMPIRICAL_UNSCANNED", detail
    if moved:
        return "EMPIRICAL_MOVABLE", detail
    if rng is None:
        return "EMPIRICAL_UNSCANNED", detail
    if rng == 0:
        if _mut() == "M4_NO_DEGENERATE":
            return "EMPIRICAL_FIXED", detail
        return "EMPIRICAL_DEGENERATE", detail
    return "EMPIRICAL_FIXED", detail


# ────────────────────────────────────────────────────────── 雙向校準（判準 §五）
def _cal_pos(rows, events):
    return "ALWAYS_SAME", 1.0


def _cal_neg_factory(n_full):
    def f(rows, events):
        return ("FULL" if len(rows) == n_full else "SUB"), float(len(rows))
    return f


# ──────────────────────────────────────────────────────────────────────── 主流程
def census(snapshot_path: str = SNAPSHOT) -> dict:
    live_at_entry = _live_reads
    t_start = time.time()
    snap = json.loads((ROOT / snapshot_path).read_text(encoding="utf-8"))
    rows, events = snap["rows"], snap.get("events") or []
    ts = [r["ts"] for r in rows if r.get("ts") is not None]
    t0, t1 = min(ts), max(ts)
    wins = windows(t0, t1)

    out = {"snapshot": snapshot_path, "n_rows": len(rows), "n_events": len(events),
           "t0": t0, "t1": t1, "span_s": t1 - t0,
           "n_windows": len(wins), "fractions": list(FRACTIONS),
           "windows": [{"f": f, "i": i, "lo": lo, "hi": hi} for f, i, lo, hi in wins],
           "tools": {}, "blockers": []}

    def _call(name, fn, rws, evs):
        if name == "r486_events_full":
            return probe_r486_events_full(rws, evs, events)
        return fn(rws, evs)

    def run_one(name, fn):
        v_full, s_full = _call(name, fn, rows, events)
        res = []
        for f, i, lo, hi in wins:
            rws = slice_rows(rows, lo, hi)
            evs = [e for e in events if e.get("ts") is not None and lo <= e["ts"] <= hi]
            rec = {"f": f, "i": i, "n_rows": len(rws), "n_events": len(evs)}
            try:
                v, s = _call(name, fn, rws, evs)
                rec["verdict"], rec["stat"], rec["error"] = v, s, None
            except Exception as e:                      # G-ERR：例外要看得見，不准吞掉
                rec["verdict"], rec["stat"] = None, None
                rec["error"] = f"{type(e).__name__}: {e}"
            if _mut() == "M2_FORCE_SAME" and rec["error"] is None:
                rec["verdict"] = v_full
            res.append(rec)
        cell, detail = classify(v_full, res)
        return {"full_verdict": v_full, "full_stat": s_full, "cell": cell,
                "detail": detail, "windows": res}

    for name, fn in PROBES:
        out["tools"][name] = run_one(name, fn)

    # G-REPRO
    repro = {k: out["tools"][k]["full_verdict"] for k in EXPECTED_FULL}
    out["repro_expected"] = EXPECTED_FULL
    out["repro_actual"] = repro
    out["repro_ok"] = all(repro[k] == EXPECTED_FULL[k] for k in EXPECTED_FULL)

    # G-CAL（跑在同一套視窗機制上）
    n_full = len(rows)
    cpos = run_one("C_POS", _cal_pos)
    cneg = run_one("C_NEG", _cal_neg_factory(n_full))
    out["calibration"] = {"C_POS": cpos["cell"], "C_NEG": cneg["cell"]}
    out["calibration_detail"] = {"C_POS": cpos["detail"], "C_NEG": cneg["detail"]}

    cells = {k: v["cell"] for k, v in out["tools"].items()}
    out["cells"] = cells
    out["n_movable"] = sum(1 for c in cells.values() if c == "EMPIRICAL_MOVABLE")
    out["n_fixed"] = sum(1 for c in cells.values() if c == "EMPIRICAL_FIXED")
    out["n_degenerate"] = sum(1 for c in cells.values() if c == "EMPIRICAL_DEGENERATE")
    out["n_unscanned"] = sum(1 for c in cells.values() if c == "EMPIRICAL_UNSCANNED")
    out["max_exc_rate"] = max(v["detail"]["exc_rate"] for v in out["tools"].values())
    out["live_reads"] = _live_reads - live_at_entry
    out["elapsed_s"] = round(time.time() - t_start, 1)

    if out["n_windows"] != N_WINDOWS_EXPECTED:
        out["blockers"].append("BROKEN_WINDOWS")
    if not out["repro_ok"]:
        out["blockers"].append("BROKEN_NO_REPRO")
    if out["calibration"]["C_POS"] != "EMPIRICAL_DEGENERATE" \
            or out["calibration"]["C_NEG"] != "EMPIRICAL_MOVABLE":
        out["blockers"].append("BROKEN_CALIBRATION")
    if out["live_reads"] != 0:
        out["blockers"].append("BROKEN_LIVE_READ")
    out["verdict"] = out["blockers"][0] if out["blockers"] else "CENSUS_OK"
    return out


# ─────────────────────────────────────────────────────────────────────── selftest
def selftest() -> int:
    fails = []

    def chk(name, cond):
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)

    # C1_glive：故意打主 run 路徑必須丟 RuntimeError（G-LIVE 的牙齒）
    try:
        _guarded_open(f"runs/{LIVE}/rows.jsonl")
        raised = False
    except RuntimeError:
        raised = True
    except Exception:
        raised = False
    chk("C1_glive", raised)

    # C2_windows：視窗數、左緣等距、涵蓋範圍
    w = windows(0.0, 100.0)
    chk("C2_windows_n", len(w) == N_WINDOWS_EXPECTED)
    chk("C2_windows_span", all(abs((hi - lo) - 100.0 * f) < 1e-9 for f, i, lo, hi in w))
    chk("C2_windows_inside", all(lo >= -1e-9 and hi <= 100.0 + 1e-9 for _, _, lo, hi in w))

    # C3_classify：四格各自造一次，每格**只翻一個輸入**
    base = [{"verdict": "A", "stat": 1.0, "error": None} for _ in range(12)]
    mov = [dict(r) for r in base]; mov[3]["verdict"] = "B"
    chk("C3_movable", classify("A", mov)[0] == "EMPIRICAL_MOVABLE")
    chk("C3_degenerate", classify("A", base)[0] == "EMPIRICAL_DEGENERATE")
    var = [dict(r) for r in base]; var[3]["stat"] = 2.0
    chk("C3_fixed", classify("A", var)[0] == "EMPIRICAL_FIXED")
    allerr = [{"verdict": None, "stat": None, "error": "X"} for _ in range(12)]
    chk("C3_unscanned_allerr", classify("A", allerr)[0] == "EMPIRICAL_UNSCANNED")
    nostat = [{"verdict": "A", "stat": None, "error": None} for _ in range(12)]
    chk("C3_unscanned_nostat", classify("A", nostat)[0] == "EMPIRICAL_UNSCANNED")

    # C4_exc_rate：例外要進報告，不准被當成「同一個判決」
    half = [dict(r) for r in base[:6]] + [{"verdict": None, "stat": None, "error": "X"}] * 6
    cell, det = classify("A", half)
    chk("C4_exc_rate", abs(det["exc_rate"] - 0.5) < 1e-9 and det["n_error"] == 6)

    # C5_cal：兩個校準函式本身的語意（不跑真資料）
    chk("C5_cpos_const", _cal_pos([], [])[0] == "ALWAYS_SAME")
    f = _cal_neg_factory(10)
    chk("C5_cneg_full", f([0] * 10, [])[0] == "FULL")
    chk("C5_cneg_sub", f([0] * 9, [])[0] == "SUB")

    # C6_slice：切片只留視窗內、且沒有 ts 的列一律排除
    rs = [{"ts": 0.0}, {"ts": 5.0}, {"ts": 11.0}, {"no_ts": 1}]
    chk("C6_slice", [r["ts"] for r in slice_rows(rs, 0.0, 10.0)] == [0.0, 5.0])

    # C7_mut_runtime：突變體旗標必須是呼叫時才讀（import 時讀 ⇒ 突變不生效）
    old = os.environ.get("R495_MUTANT", "")
    os.environ["R495_MUTANT"] = "M1_NO_SUBWINDOWS"
    n1 = len(windows(0.0, 1.0))
    os.environ["R495_MUTANT"] = old
    n2 = len(windows(0.0, 1.0))
    chk("C7_mut_runtime", n1 == 1 and n2 == N_WINDOWS_EXPECTED)

    # C8_expected_pinned：G-REPRO 的期望值是常數表，不是從跑出來的東西導出的
    import ast as _ast
    src = _guarded_open(pathlib.Path(__file__), encoding="utf-8").read()
    tree = _ast.parse(src)
    pinned = None
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Assign):
            for t in node.targets:
                if isinstance(t, _ast.Name) and t.id == "EXPECTED_FULL":
                    pinned = _ast.literal_eval(node.value)
    chk("C8_expected_pinned", isinstance(pinned, dict) and len(pinned) == 7)

    print("selftest:", "all passed" if not fails else f"FAILED {fails}")
    return 0 if not fails else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--snapshot", default=SNAPSHOT)
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    out = census(a.snapshot)
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(out, indent=2, ensure_ascii=False),
                                        encoding="utf-8")
    print(f"verdict={out['verdict']}  windows={out['n_windows']}  "
          f"movable={out['n_movable']}  fixed={out['n_fixed']}  "
          f"degenerate={out['n_degenerate']}  unscanned={out['n_unscanned']}  "
          f"max_exc_rate={out['max_exc_rate']}  live_reads={out['live_reads']}  "
          f"repro_ok={out['repro_ok']}  elapsed_s={out['elapsed_s']}")
    for k, v in out["cells"].items():
        d = out["tools"][k]["detail"]
        print(f"  {k:30s} {v:22s} full={out['tools'][k]['full_verdict']!s:24s} "
              f"seen={d['verdicts_seen']} stat_range={d['stat_range']} exc={d['exc_rate']}")
    print("  calibration:", out["calibration"])
    return 0 if out["verdict"] == "CENSUS_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
