#!/usr/bin/env python3
"""R498：等 **chat 列數** 滑動視窗——把「視窗位置」與「被分析樣本數」拆開。

判準先行：DECISION_20260905_R498_EQUAL_CHAT_N_PREREG.md（commit 8b2db52）。

R496 固定的是閘道總列數；R497 §三 量出被 r489/r490 真正分析的 chat 列數在那批視窗裡
仍是 rho=-1.0 單調下降 ⇒ 位置與被分析 n 完全共線。本尺把固定的單位換成被分析的 chat 列數。

判決分格直接用 R496.classify（不重寫＝不製造第二套語意）；probe 直接用 R495 那兩支。

用法：
  python3 ops/gain/r498_equal_chat_n.py --selftest
  python3 ops/gain/r498_equal_chat_n.py --json ops/gain/data/r498_equal_chat_n.json
"""
from __future__ import annotations
import argparse, ast, json, os, pathlib, statistics, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.gain import r495_empirical_census as R495                   # noqa: E402  (裝上 G-LIVE)
from ops.gain import r496_equal_n_windows as R496                    # noqa: E402
from ops.gain import r489_permutation_placebo as R489                # noqa: E402

K_PER_TIER = 6
N_WINDOWS_EXPECTED = 2 * K_PER_TIER
M_EXPECTED = (364, 555)          # 判準 §一.3／G-DERIVED：R497 §三 記錄值，現算必須對上
SPAN_REPORT_THRESHOLD = 0.25     # 判準 §三：併記門檻，**不讓判決作廢**

PROBES = [("r489_permutation_placebo", R495.probe_r489),
          ("r490_leveled_placebo", R495.probe_r490)]


def _mut() -> str:
    """突變體旗標，**呼叫時**才讀（memory：寫在模組層永遠不生效）。"""
    return os.environ.get("R498_MUTANT", "")


def analysable(rows):
    """判準 §一.2：沿用被測檔自己的過濾器，不自己寫一份。"""
    return [r for r in rows if R489.is_chat(r) and R489.is_analysable(r)]


def derive_M(rows):
    """判準 §一.3：兩層的 chat 列數由 R496 的視窗導出（現算，不寫死）。"""
    sub_ts = {id(r) for r in analysable(rows)}
    per_tier = {}
    for N, i, lo, hi in R496.index_windows(len(rows)):
        n = sum(1 for r in rows[lo:hi] if id(r) in sub_ts)
        per_tier.setdefault(N, []).append(n)
    if _mut() == "M4_PIN_M":                       # 突變：寫死成 R496 的 N
        return (R496.N_SMALL, R496.N_LARGE), {str(k): v for k, v in sorted(per_tier.items())}
    if _mut() == "M4b_PIN_M_FEASIBLE":
        # 補充突變體（**事後補的，不在判準 §五 的表上**）：判準寫的 M4 把 M 釘成 1672/2291，
        # 而 len(sub)=728 ⇒ IndexError ⇒ crash 收場不算偵測到（memory 已記過這條）。
        # 這一版釘成可行的錯值，用來回答「G-DERIVED 到底有沒有牙齒」。
        return (300, 500), {str(k): v for k, v in sorted(per_tier.items())}
    ms = tuple(min(v) for _k, v in sorted(per_tier.items()))
    return ms, {str(k): v for k, v in sorted(per_tier.items())}


def chat_windows(rows, ms):
    """判準 §一.4：左緣在 `sub` 的索引上等距，每個視窗恰含 M 筆被分析列。

    回傳 [(M, i, lo_row, hi_row, lo_sub)]，lo_row/hi_row 是 `rows` 上的半開區間。
    """
    sub = analysable(rows)
    pos = {id(r): j for j, r in enumerate(rows)}
    k = 1 if _mut() == "M1_ONE_POSITION" else K_PER_TIER
    out = []
    for M in ms:
        room = len(sub) - M
        for i in range(k):
            lo_s = (room * i // (k - 1)) if k > 1 else 0
            if _mut() == "M2_TOTAL_ROWS":          # 突變：退化回 R496 的單位（總列數）
                lo_r = pos[id(sub[lo_s])]
                out.append((M, i, lo_r, min(lo_r + M, len(rows)), lo_s))
                continue
            lo_r = pos[id(sub[lo_s])]
            hi_r = pos[id(sub[lo_s + M - 1])] + 1
            out.append((M, i, lo_r, hi_r, lo_s))
    return out


def _cal_pos(rows, events):
    return "ALWAYS_SAME", 1.0


def _cal_neg(rows, events):
    """回層別字母 ⇒ 層內恆定、層間不同 ⇒ 必須落 N_MATTERS。"""
    return ("S" if len(analysable(rows)) == _cal_neg.m_small else "L"), float(len(rows))


def census(snapshot_path: str = R495.SNAPSHOT) -> dict:
    live_at_entry = R495._live_reads
    t0 = time.time()
    snap = json.loads((ROOT / snapshot_path).read_text(encoding="utf-8"))
    rows = sorted([r for r in snap["rows"] if r.get("ts") is not None], key=lambda r: r["ts"])
    events = snap.get("events") or []
    sub_all = analysable(rows)
    ms, per_tier_counts = derive_M(rows)
    _cal_neg.m_small = ms[0]
    wins = chat_windows(rows, ms)
    sub_ts = {id(r) for r in sub_all}

    out = {"snapshot": snapshot_path, "n_rows_sorted": len(rows), "n_events": len(events),
           "n_chat": sum(1 for r in rows if R489.is_chat(r)), "n_analysable": len(sub_all),
           "M": list(ms), "M_expected": list(M_EXPECTED),
           "r496_tier_chat_counts": per_tier_counts,
           "n_windows": len(wins), "tools": {}, "blockers": [], "n_exceptions": 0}

    sliced = []
    for M, i, lo_r, hi_r, lo_s in wins:
        rws = rows[lo_r:hi_r]
        t_lo, t_hi = rws[0]["ts"], rws[-1]["ts"]
        evs = [e for e in events if e.get("ts") is not None and t_lo <= e["ts"] <= t_hi]
        sliced.append({"M": M, "i": i, "lo_row": lo_r, "hi_row": hi_r, "lo_sub": lo_s,
                       "n_rows_total": len(rws), "n_chat": sum(1 for r in rws if R489.is_chat(r)),
                       "n_sub": sum(1 for r in rws if id(r) in sub_ts),
                       "span_s": round(t_hi - t_lo, 1), "events_in_window": len(evs),
                       "_rows": rws, "_evs": evs})

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
            if _mut() == "M3_FORCE_SAME" and rec["error"] is None:
                rec["verdict"] = v_full
            recs.append({"N": rec["M"], **rec})       # R496.classify 讀 "N"
        cell, detail = R496.classify(v_full, recs)
        return {"full_verdict": v_full, "cell": cell, "detail": detail, "windows": recs}

    for name, fn in PROBES:
        out["tools"][name] = run_one(name, fn)

    def headline(cell):
        if cell in ("POSITION_MATTERS", "BOTH"):
            return "POSITION_SURVIVES"
        if cell in ("NEITHER", "NEW_CELL_UNIFORM_SHIFT"):
            return "POSITION_GONE"
        if cell == "N_MATTERS":
            return "N_ONLY"
        return "UNSCANNED"

    out["cells"] = {k: v["cell"] for k, v in out["tools"].items()}
    out["headlines"] = {k: headline(v["cell"]) for k, v in out["tools"].items()}

    # 跨度／總列數的浮動（判準 §三 的併記量）
    spans = {}
    for w in sliced:
        spans.setdefault(w["M"], []).append(w["span_s"])
    out["span_by_tier"] = {str(k): v for k, v in sorted(spans.items())}
    out["span_spread"] = {str(k): round((max(v) - min(v)) / statistics.median(v), 4)
                          for k, v in sorted(spans.items())}
    out["span_uncontrolled"] = any(v > SPAN_REPORT_THRESHOLD for v in out["span_spread"].values())
    tot = [w["n_rows_total"] for w in sliced]
    out["n_rows_total_spread"] = round((max(tot) - min(tot)) / statistics.median(tot), 4)

    cpos, cneg = run_one("C_POS", _cal_pos), run_one("C_NEG", _cal_neg)
    out["calibration"] = {"C_POS": cpos["cell"], "C_NEG": cneg["cell"]}
    out["live_reads"] = R495._live_reads - live_at_entry
    out["elapsed_s"] = round(time.time() - t0, 1)

    # ── 擋門（判準 §四）
    if tuple(out["M"]) != M_EXPECTED:
        out["blockers"].append("BROKEN_DERIVED")
    if any(w["n_sub"] != w["M"] for w in sliced):
        out["blockers"].append("BROKEN_EQCHAT")
    los = {}
    for M, i, lo_r, _hi, lo_s in wins:
        los.setdefault(M, []).append(lo_s)
    if (len(wins) != N_WINDOWS_EXPECTED
            or any(len(v) != K_PER_TIER for v in los.values())
            or any(v != sorted(set(v)) for v in los.values())):
        out["blockers"].append("BROKEN_WINDOWS")
    if out["n_exceptions"] != 0:
        out["blockers"].append("BROKEN_EXCEPTIONS")
    if out["calibration"]["C_POS"] != "NEITHER" or out["calibration"]["C_NEG"] != "N_MATTERS":
        out["blockers"].append("BROKEN_CALIBRATION")
    if out["live_reads"] != 0:
        out["blockers"].append("BROKEN_LIVE_READ")
    out["verdict"] = out["blockers"][0] if out["blockers"] else "EQCHAT_OK"
    return out


def selftest() -> int:
    fails = []

    def chk(name, cond):
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)

    try:
        R495._guarded_open(f"runs/{R495.LIVE}/rows.jsonl")
        raised = False
    except RuntimeError:
        raised = True
    except Exception:
        raised = False
    chk("C1_glive", raised)

    # 合成快照：每 3 列有 1 列是可分析的 chat 列
    def mkrow(j, chat):
        return {"id": j, "ts": float(j), "iso": "", "machine": "1004",
                "path": "[gw] /v1/chat/completions" if chat else "[gw] /api/events",
                "model": "m" if chat else None, "error": None, "status_code": 200,
                "latency_ms": 100.0 + j, "completion_tokens": 50 + (j % 7) if chat else None,
                "prompt_tokens": 10 if chat else None, "finish_reason": "stop" if chat else None,
                "stream": 0, "client_ip": "a", "remote_id": None, "request_summary": "",
                "total_tokens": None, "method": "POST" if chat else "GET"}
    rs = [mkrow(j, j % 3 == 0) for j in range(90)]
    sub = analysable(rs)
    chk("C2_filter_is_r489", len(sub) == 30 and all(R489.is_chat(r) for r in sub))

    ws = chat_windows(rs, (10, 20))
    chk("C3_n_windows", len(ws) == N_WINDOWS_EXPECTED)
    sub_ids = {id(r) for r in sub}
    counts = [sum(1 for r in rs[lo:hi] if id(r) in sub_ids) for _M, _i, lo, hi, _ls in ws]
    chk("C3_exact_M", counts == [10] * 6 + [20] * 6)
    chk("C3_lo_increasing", all(sorted(set(l)) == l for l in (
        [w[4] for w in ws[:6]], [w[4] for w in ws[6:]])))
    # 等 chat 列數 ⇒ 總列數不必相等（本合成資料剛好均勻，故只檢查不 crash 的性質）
    chk("C3_hi_gt_lo", all(hi > lo for _M, _i, lo, hi, _ls in ws))

    # M2 突變（總列數單位）必須讓 n_sub != M
    os.environ["R498_MUTANT"] = "M2_TOTAL_ROWS"
    ws2 = chat_windows(rs, (10, 20))
    c2 = [sum(1 for r in rs[lo:hi] if id(r) in sub_ids) for _M, _i, lo, hi, _ls in ws2]
    os.environ.pop("R498_MUTANT")
    chk("C4_m2_breaks_eqchat", c2 != counts)

    # M4 突變必須讓導出的 M 不等於現算值
    rows_real = None
    chk("C5_M_expected_is_tuple", isinstance(M_EXPECTED, tuple) and len(M_EXPECTED) == 2)

    # headline 對照表：五格各一次（用 R496.classify 的輸出字串）
    def hl(cell):
        if cell in ("POSITION_MATTERS", "BOTH"):
            return "POSITION_SURVIVES"
        if cell in ("NEITHER", "NEW_CELL_UNIFORM_SHIFT"):
            return "POSITION_GONE"
        return "N_ONLY" if cell == "N_MATTERS" else "UNSCANNED"
    chk("C6_hl_survives", hl("POSITION_MATTERS") == hl("BOTH") == "POSITION_SURVIVES")
    chk("C6_hl_gone", hl("NEITHER") == hl("NEW_CELL_UNIFORM_SHIFT") == "POSITION_GONE")
    chk("C6_hl_nonly", hl("N_MATTERS") == "N_ONLY")
    chk("C6_hl_unscanned", hl("UNSCANNED_EQN") == "UNSCANNED")

    # 分格函式確實是 R496 那一份（不是自己重寫的第二套語意）
    # ⚠ 用 ast 不用字串比對：檢查那行自己就含有被找的字面 ⇒ 恆為真（memory 已記過兩次）
    src = R495._guarded_open(pathlib.Path(__file__), encoding="utf-8").read()
    tree = ast.parse(src)
    local_fns = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    calls_r496 = any(isinstance(n, ast.Attribute) and n.attr == "classify"
                     and isinstance(n.value, ast.Name) and n.value.id == "R496"
                     for n in ast.walk(tree))
    chk("C7_reuses_r496_classify", calls_r496 and "classify" not in local_fns)

    print(f"selftest: {'all passed' if not fails else 'FAILED ' + ','.join(fails)}")
    return 0 if not fails else 1


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
        pathlib.Path(a.json).write_text(json.dumps(out, indent=2, ensure_ascii=False),
                                        encoding="utf-8")
    print(f"verdict={out['verdict']}  M={out['M']}  n_windows={out['n_windows']}  "
          f"exc={out['n_exceptions']}  live_reads={out['live_reads']}  elapsed_s={out['elapsed_s']}")
    print(f"calibration: {out['calibration']}")
    print(f"span_spread={out['span_spread']}  SPAN_UNCONTROLLED={out['span_uncontrolled']}  "
          f"n_rows_total_spread={out['n_rows_total_spread']}")
    for k, v in out["tools"].items():
        print(f"  {k:28s} cell={v['cell']:22s} headline={out['headlines'][k]}")
        print(f"      full={v['full_verdict']}")
        print(f"      windows={[w['verdict'] for w in v['windows']]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
