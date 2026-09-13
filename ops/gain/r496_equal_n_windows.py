#!/usr/bin/env python3
"""R496：等列數視窗——把 R495 的「視窗位置 vs 樣本量」拆開。

判準先行：DECISION_20260905_R496_EQUAL_N_WINDOW_PREREG.md（commit 53eb9c1）。

判決函式直接 import R495 的 probe_*，不重寫一份（重寫＝兩套語意）。
G-LIVE 也是 R495 那一份（import 它時就裝上了）。

用法：
  python3 ops/gain/r496_equal_n_windows.py --selftest
  python3 ops/gain/r496_equal_n_windows.py --json ops/gain/data/r496_equal_n.json
"""
from __future__ import annotations
import argparse, json, os, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.gain import r495_empirical_census as R495                   # noqa: E402

N_SMALL = 1672          # 判準 §一：R495 f=0.6 十二個視窗的最小列數（導出，非挑選）
N_LARGE = 2291          # 判準 §一：R495 f=0.8 六個視窗的最小列數
K_PER_TIER = 6
N_WINDOWS_EXPECTED = 2 * K_PER_TIER

PROBES = [
    ("r486_longreq_attrib", R495.probe_r486, "QUEUE_LIVE"),
    ("r489_permutation_placebo", R495.probe_r489, "PLACEBO_LADDER_BROKEN"),
    ("r490_leveled_placebo", R495.probe_r490, "PLACEBO_LADDER_BROKEN"),
]


def _mut() -> str:
    """突變體旗標，**呼叫時**才讀。"""
    return os.environ.get("R496_MUTANT", "")


def index_windows(n_rows: int):
    """判準 §一：每層 K 個左緣在索引上等距、恰好 N 列的連續區間。回傳 [(N, i, lo, hi)]。"""
    k = 1 if _mut() == "M1_ONE_POSITION" else K_PER_TIER
    out = []
    for N in (N_SMALL, N_LARGE):
        room = n_rows - N
        for i in range(k):
            lo = (room * i // (k - 1)) if k > 1 else 0
            out.append((N, i, lo, lo + N))
    return out


def classify(full_verdict, recs):
    """判準 §三。recs: [{'N':..,'verdict':..,'error':..}]"""
    ok = [r for r in recs if r.get("error") is None]
    errs = len(recs) - len(ok)
    detail = {"n_windows": len(recs), "n_ok": len(ok), "n_error": errs,
              "exc_rate": round(errs / len(recs), 4) if recs else 1.0}
    if not ok:
        return "UNSCANNED_EQN", detail
    tiers = {}
    for r in ok:
        tiers.setdefault(r["N"], set()).add(r["verdict"])
    detail["by_tier"] = {str(k): sorted(v) for k, v in sorted(tiers.items())}
    within = any(len(v) >= 2 for v in tiers.values())
    sets = list(tiers.values())
    across = len(sets) >= 2 and any(sets[0] != s for s in sets[1:])
    detail["within_tier_varies"] = within
    detail["across_tier_differs"] = across
    if all(v == {full_verdict} for v in tiers.values()):
        return "NEITHER", detail
    if within and across:
        return "BOTH", detail
    if within:
        return "POSITION_MATTERS", detail
    if across:
        return "N_MATTERS", detail
    # 層內恆定、層間相同，但那個判決 != 全視窗判決 ⇒ 判準沒有的第六種格
    return "NEW_CELL_UNIFORM_SHIFT", detail


def _cal_pos(rows, events):
    return "ALWAYS_SAME", 1.0


def _cal_neg(rows, events):
    return ("S" if len(rows) == N_SMALL else "L"), float(len(rows))


def census(snapshot_path: str = R495.SNAPSHOT) -> dict:
    live_at_entry = R495._live_reads
    t0w = time.time()
    snap = json.loads((ROOT / snapshot_path).read_text(encoding="utf-8"))
    rows = sorted([r for r in snap["rows"] if r.get("ts") is not None], key=lambda r: r["ts"])
    events = snap.get("events") or []
    wins = index_windows(len(rows))
    out = {"snapshot": snapshot_path, "n_rows_sorted": len(rows), "n_events": len(events),
           "N_SMALL": N_SMALL, "N_LARGE": N_LARGE, "n_windows": len(wins),
           "windows": [{"N": N, "i": i, "lo": lo, "hi": hi} for N, i, lo, hi in wins],
           "tools": {}, "blockers": []}

    def run_one(name, fn):
        v_full, s_full = fn(rows, events)
        recs = []
        for N, i, lo, hi in wins:
            rws = rows[lo:hi]
            t_lo, t_hi = rws[0]["ts"], rws[-1]["ts"]
            evs = [e for e in events if e.get("ts") is not None and t_lo <= e["ts"] <= t_hi]
            rec = {"N": N, "i": i, "lo": lo, "n_rows": len(rws),
                   "span_s": round(t_hi - t_lo, 1), "n_events": len(evs)}
            try:
                v, s = fn(rws, evs)
                rec["verdict"], rec["stat"], rec["error"] = v, s, None
            except Exception as e:
                rec["verdict"], rec["stat"] = None, None
                rec["error"] = f"{type(e).__name__}: {e}"
            if _mut() == "M2_FORCE_SAME" and rec["error"] is None:
                rec["verdict"] = v_full
            recs.append(rec)
        cell, detail = classify(v_full, recs)
        return {"full_verdict": v_full, "cell": cell, "detail": detail, "windows": recs}

    for name, fn, _exp in PROBES:
        out["tools"][name] = run_one(name, fn)

    out["repro_expected"] = {n: e for n, _f, e in PROBES}
    out["repro_actual"] = {n: out["tools"][n]["full_verdict"] for n, _f, _e in PROBES}
    out["repro_ok"] = out["repro_actual"] == out["repro_expected"]

    cpos, cneg = run_one("C_POS", _cal_pos), run_one("C_NEG", _cal_neg)
    out["calibration"] = {"C_POS": cpos["cell"], "C_NEG": cneg["cell"]}
    out["calibration_detail"] = {"C_POS": cpos["detail"], "C_NEG": cneg["detail"]}

    out["cells"] = {k: v["cell"] for k, v in out["tools"].items()}
    out["max_exc_rate"] = max(v["detail"]["exc_rate"] for v in out["tools"].values())
    out["live_reads"] = R495._live_reads - live_at_entry
    out["elapsed_s"] = round(time.time() - t0w, 1)

    if out["n_windows"] != N_WINDOWS_EXPECTED:
        out["blockers"].append("BROKEN_WINDOWS")
    if not out["repro_ok"]:
        out["blockers"].append("BROKEN_NO_REPRO")
    if out["calibration"]["C_POS"] != "NEITHER" or out["calibration"]["C_NEG"] != "N_MATTERS":
        out["blockers"].append("BROKEN_CALIBRATION")
    if out["live_reads"] != 0:
        out["blockers"].append("BROKEN_LIVE_READ")
    out["verdict"] = out["blockers"][0] if out["blockers"] else "EQN_OK"
    return out


def selftest() -> int:
    fails = []

    def chk(name, cond):
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)

    w = index_windows(2899)
    chk("S1_n", len(w) == N_WINDOWS_EXPECTED)
    chk("S1_exact_n", all((hi - lo) == N for N, i, lo, hi in w))
    chk("S1_inside", all(lo >= 0 and hi <= 2899 for _, _, lo, hi in w))
    chk("S1_two_tiers", {N for N, _, _, _ in w} == {N_SMALL, N_LARGE})

    def rec(N, v, err=None):
        return {"N": N, "verdict": v, "error": err}

    S, L = N_SMALL, N_LARGE
    # 五格各造一次，每格只翻一個輸入
    chk("S2_neither", classify("A", [rec(S, "A")] * 6 + [rec(L, "A")] * 6)[0] == "NEITHER")
    chk("S2_position", classify("A", [rec(S, "A")] * 5 + [rec(S, "B")]
                                + [rec(L, "A")] * 5 + [rec(L, "B")])[0] == "POSITION_MATTERS")
    chk("S2_n_matters", classify("A", [rec(S, "A")] * 6 + [rec(L, "B")] * 6)[0] == "N_MATTERS")
    chk("S2_both", classify("A", [rec(S, "A")] * 5 + [rec(S, "B")]
                            + [rec(L, "A")] * 6)[0] == "BOTH")
    chk("S2_unscanned", classify("A", [rec(S, None, "X")] * 12)[0] == "UNSCANNED_EQN")
    chk("S2_newcell", classify("A", [rec(S, "B")] * 6 + [rec(L, "B")] * 6)[0]
        == "NEW_CELL_UNIFORM_SHIFT")
    # BOTH 優先於 POSITION_MATTERS（判準 §三 明寫互斥順序）
    d = classify("A", [rec(S, "A")] * 5 + [rec(S, "B")] + [rec(L, "A")] * 6)[1]
    chk("S2_both_flags", d["within_tier_varies"] and d["across_tier_differs"])

    # S3：校準函式的語意
    chk("S3_cpos", _cal_pos([], [])[0] == "ALWAYS_SAME")
    chk("S3_cneg_s", _cal_neg([0] * N_SMALL, [])[0] == "S")
    chk("S3_cneg_l", _cal_neg([0] * N_LARGE, [])[0] == "L")

    # S4：G-LIVE 沿用 R495 那一份，牙齒在這裡再驗一次
    try:
        R495._guarded_open(f"runs/{R495.LIVE}/rows.jsonl")
        raised = False
    except RuntimeError:
        raised = True
    except Exception:
        raised = False
    chk("S4_glive", raised)

    # S5：突變體旗標必須呼叫時才讀
    old = os.environ.get("R496_MUTANT", "")
    os.environ["R496_MUTANT"] = "M1_ONE_POSITION"
    n1 = len(index_windows(2899))
    os.environ["R496_MUTANT"] = old
    chk("S5_mut_runtime", n1 == 2 and len(index_windows(2899)) == N_WINDOWS_EXPECTED)

    # S6：N 是從 R495 導出的常數，不是挑的 —— 釘死值必須還在原始碼裡
    import ast as _ast
    tree = _ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
    got = {}
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Assign):
            for t in node.targets:
                if isinstance(t, _ast.Name) and t.id in ("N_SMALL", "N_LARGE"):
                    got[t.id] = _ast.literal_eval(node.value)
    chk("S6_pinned_N", got == {"N_SMALL": 1672, "N_LARGE": 2291})

    print("selftest:", "all passed" if not fails else f"FAILED {fails}")
    return 0 if not fails else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    out = census()
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(out, indent=2, ensure_ascii=False),
                                        encoding="utf-8")
    print(f"verdict={out['verdict']}  windows={out['n_windows']}  repro_ok={out['repro_ok']}  "
          f"max_exc_rate={out['max_exc_rate']}  live_reads={out['live_reads']}  "
          f"elapsed_s={out['elapsed_s']}")
    for k, v in out["cells"].items():
        print(f"  {k:28s} {v:24s} full={out['tools'][k]['full_verdict']:24s} "
              f"tiers={out['tools'][k]['detail'].get('by_tier')}")
    print("  calibration:", out["calibration"])
    return 0 if out["verdict"] == "EQN_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
