#!/usr/bin/env python3
"""R497：閘道快照前段/後段的組成軸篩除普查。

判準先行：DECISION_20260905_R497_SEGMENT_COMPOSITION_PREREG.md（commit 626d300）。

⚠ 本尺是**篩除工具**，力氣在否定方向：判 NOT_TRACKING 的軸不可能解釋一個兩層都
   近乎單調的翻動；判 POSITION_TRACKING 只是「進入候選名單」，不是原因（判準三.1）。

用法：
  python3 ops/gain/r497_segment_composition.py --selftest
  python3 ops/gain/r497_segment_composition.py --json ops/gain/data/r497_segment_composition.json
"""
from __future__ import annotations
import argparse, collections, hashlib, json, os, pathlib, statistics, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.gain import r495_empirical_census as R495                   # noqa: E402  (裝上 G-LIVE)
from ops.gain import r496_equal_n_windows as R496                    # noqa: E402

RHO_MIN = 0.9        # 判準三.1 導出：k=6 時 |rho|>=0.9 ⇔ Σd²∈{0,2}；非掃出來的旋鈕
N_EXO_EXPECTED = 11
N_ENDO_EXPECTED = 3


def _mut() -> str:
    """突變體旗標，**呼叫時**才讀（memory：寫在模組層永遠不生效）。"""
    return os.environ.get("R497_MUTANT", "")


# ─────────────────────────────────────────────────────── 統計量（判準 §二 的表）
def _share(rows, pred):
    return (sum(1 for r in rows if pred(r)) / len(rows)) if rows else None


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return statistics.fmean(vals) if vals else None


def _median(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def build_stats(all_rows):
    """回傳 [(name, kind, field, fn)]。`field` 供 STAT_UNSCANNED 前置尺用。"""
    modal_ip = collections.Counter(
        r.get("client_ip") for r in all_rows).most_common(1)[0][0]

    exo = [
        ("share_chat", "path",
         lambda rs, ev: _share(rs, lambda r: "/chat/completions" in (r.get("path") or ""))),
        ("share_other_client", "client_ip",
         lambda rs, ev: _share(rs, lambda r: r.get("client_ip") != modal_ip)),
        ("n_distinct_client_ip", "client_ip",
         lambda rs, ev: float(len({r.get("client_ip") for r in rs}))),
        ("share_model_gemma", "model",
         lambda rs, ev: _share(rs, lambda r: r.get("model") == "gemma-4-12b-it-qat")),
        ("share_model_null", "model",
         lambda rs, ev: _share(rs, lambda r: r.get("model") is None)),
        ("share_machine_1004", "machine",
         lambda rs, ev: _share(rs, lambda r: r.get("machine") == "1004")),
        ("events_in_window", None, lambda rs, ev: float(len(ev))),
        ("share_error", "error",
         lambda rs, ev: _share(rs, lambda r: r.get("error") is not None)),
        ("share_status_non200", "status_code",
         lambda rs, ev: _share(rs, lambda r: r.get("status_code") != 200)),
        ("mean_prompt_tokens", "prompt_tokens",
         lambda rs, ev: _mean([r.get("prompt_tokens") for r in rs])),
        ("share_stream", "stream", lambda rs, ev: _share(rs, lambda r: r.get("stream") == 1)),
    ]
    endo = [
        ("median_latency_ms", "latency_ms",
         lambda rs, ev: _median([r.get("latency_ms") for r in rs])),
        ("mean_completion_tokens", "completion_tokens",
         lambda rs, ev: _mean([r.get("completion_tokens") for r in rs])),
        ("median_ms_per_tok", "completion_tokens",
         lambda rs, ev: _median([r["latency_ms"] / r["completion_tokens"] for r in rs
                                 if r.get("latency_ms") is not None
                                 and r.get("completion_tokens")])),
    ]
    cal = [
        ("C_POS", "ts", lambda rs, ev: _mean([r.get("ts") for r in rs])),
        ("C_NEG", "id", _cneg),
    ]
    out = [(n, "EXOGENOUS", f, fn) for n, f, fn in exo]
    out += [(n, "ENDOGENOUS", f, fn) for n, f, fn in endo]
    out += [(n, "CALIBRATION", f, fn) for n, f, fn in cal]
    # 注入用的假統計量：來源欄位全快照皆不存在，但它是 share 型 ⇒ 回傳 0.0 而非 None。
    # 注入與「關掉擋門」是兩個獨立旗標 ⇒ 突變對照組之間只翻一件事（見 §M4）。
    if os.environ.get("R497_INJECT_NULL_STAT") == "1":
        out.append(("INJECTED_ALL_NULL", "EXOGENOUS", "no_such_field",
                    lambda rs, ev: _share(rs, lambda r: r.get("no_such_field") is not None)))
    return out


def _cneg(rs, ev):
    """C_NEG：只依賴 id 的決定性雜湊，與 ts 無關。"""
    if _mut() == "M2_CNEG_TIME":                    # 突變：改用 ts ⇒ 必然跟著位置動
        return _mean([r.get("ts") for r in rs])
    return _share(rs, lambda r: int(hashlib.sha256(
        str(r.get("id")).encode()).hexdigest()[0], 16) % 2 == 0)


# ─────────────────────────────────────────────────────── Spearman（無 scipy）
def _rank(vals):
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs, ys):
    """回傳 rho；任一序列無變異 ⇒ None（不是 0，見判準三.2）。"""
    if len(xs) < 2 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    rx, ry = _rank(list(xs)), _rank(list(ys))
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return None if dx == 0 or dy == 0 else num / (dx * dy)


def classify(field_all_null: bool, per_tier: dict, values: list):
    """判準 §三。per_tier: {N: rho or None}；values: 12 個視窗的值。"""
    if field_all_null and _mut() != "M4_SWALLOW_NULL":
        return "STAT_UNSCANNED", {}
    vals = [v for v in values if v is not None]
    if len(vals) != len(values):
        return "STAT_UNSCANNED", {"n_none": len(values) - len(vals)}
    if len(set(vals)) < 2:
        return "STAT_DEGENERATE", {}
    rhos = [per_tier.get(N) for N in sorted(per_tier)]
    detail = {"rho_by_tier": {str(N): (None if per_tier[N] is None else round(per_tier[N], 4))
                              for N in sorted(per_tier)}}
    if _mut() == "M3_RHO_ONE_TIER":                 # 突變：只看第一層
        r0 = rhos[0]
        return ("POSITION_TRACKING" if r0 is not None and abs(r0) >= RHO_MIN
                else "NOT_TRACKING"), detail
    if any(r is None for r in rhos):
        return "NOT_TRACKING", detail
    both = all(abs(r) >= RHO_MIN for r in rhos)
    same_sign = len({r > 0 for r in rhos}) == 1
    return ("POSITION_TRACKING" if both and same_sign else "NOT_TRACKING"), detail


# ─────────────────────────────────────────────────────── 普查
def census(snapshot_path: str = R495.SNAPSHOT) -> dict:
    live_at_entry = R495._live_reads
    t0 = time.time()
    snap = json.loads((ROOT / snapshot_path).read_text(encoding="utf-8"))
    rows = sorted([r for r in snap["rows"] if r.get("ts") is not None], key=lambda r: r["ts"])
    events = snap.get("events") or []
    wins = R496.index_windows(len(rows))
    if _mut() == "M1_ONE_WINDOW":
        wins = [w for w in wins if w[1] == 0]

    out = {"snapshot": snapshot_path, "n_rows_sorted": len(rows), "n_events": len(events),
           "n_windows": len(wins), "rho_min": RHO_MIN,
           "windows": [{"N": N, "i": i, "lo": lo, "hi": hi} for N, i, lo, hi in wins],
           "stats": {}, "blockers": [], "n_exceptions": 0}

    # 每個視窗的 rows/events 切法逐字沿用 R496.census
    sliced = []
    for N, i, lo, hi in wins:
        rws = rows[lo:hi]
        t_lo, t_hi = rws[0]["ts"], rws[-1]["ts"]
        evs = [e for e in events if e.get("ts") is not None and t_lo <= e["ts"] <= t_hi]
        sliced.append((N, i, lo, rws, evs))

    stats = build_stats(rows)
    out["n_exogenous"] = sum(1 for _n, k, _f, _fn in stats if k == "EXOGENOUS"
                             and _n != "INJECTED_ALL_NULL")
    out["n_endogenous"] = sum(1 for _n, k, _f, _fn in stats if k == "ENDOGENOUS")

    for name, kind, field, fn in stats:
        field_all_null = bool(field) and all(r.get(field) is None for r in rows)
        vals, per_tier_x, per_tier_y, exc = [], {}, {}, 0
        for N, i, lo, rws, evs in sliced:
            try:
                v = fn(rws, evs)
            except Exception as e:
                v, exc = None, exc + 1
                out.setdefault("exceptions", []).append(f"{name}: {type(e).__name__}: {e}")
            vals.append(v)
            if v is not None:
                per_tier_x.setdefault(N, []).append(float(lo))
                per_tier_y.setdefault(N, []).append(float(v))
        out["n_exceptions"] += exc
        per_tier = {N: spearman(per_tier_x[N], per_tier_y[N]) for N in per_tier_x}
        cls, detail = classify(field_all_null, per_tier, vals)
        out["stats"][name] = {
            "kind": kind, "field": field, "field_all_null": field_all_null,
            "class": cls, "n_exceptions": exc,
            "values": [None if v is None else round(float(v), 6) for v in vals],
            **detail}

    cls_of = {n: v["class"] for n, v in out["stats"].items()}
    exo_track = sorted(n for n, v in out["stats"].items()
                       if v["kind"] == "EXOGENOUS" and v["class"] == "POSITION_TRACKING"
                       and n != "INJECTED_ALL_NULL")
    endo_track = sorted(n for n, v in out["stats"].items()
                        if v["kind"] == "ENDOGENOUS" and v["class"] == "POSITION_TRACKING")
    exo_not = sorted(n for n, v in out["stats"].items()
                     if v["kind"] == "EXOGENOUS" and v["class"] == "NOT_TRACKING"
                     and n != "INJECTED_ALL_NULL")
    out["exo_tracking"], out["endo_tracking"], out["exo_not_tracking"] = \
        exo_track, endo_track, exo_not
    out["n_unscanned_or_degenerate"] = sum(
        1 for n, v in out["stats"].items()
        if v["class"] in ("STAT_UNSCANNED", "STAT_DEGENERATE") and n != "INJECTED_ALL_NULL")
    out["calibration"] = {"C_POS": cls_of.get("C_POS"), "C_NEG": cls_of.get("C_NEG")}
    out["live_reads"] = R495._live_reads - live_at_entry
    out["elapsed_s"] = round(time.time() - t0, 1)

    # ── 擋門（判準 §四）
    ref = [{"N": N, "i": i, "lo": lo, "hi": hi}
           for N, i, lo, hi in R496.index_windows(len(rows))]
    if out["windows"] != ref or len(wins) != R496.N_WINDOWS_EXPECTED:
        out["blockers"].append("BROKEN_WINDOWS")
    if out["n_exceptions"] != 0:
        out["blockers"].append("BROKEN_EXCEPTIONS")
    if out["calibration"]["C_POS"] != "POSITION_TRACKING" or \
       out["calibration"]["C_NEG"] == "POSITION_TRACKING":
        out["blockers"].append("BROKEN_CALIBRATION")
    if out["live_reads"] != 0:
        out["blockers"].append("BROKEN_LIVE_READ")
    if out["n_exogenous"] != N_EXO_EXPECTED or out["n_endogenous"] != N_ENDO_EXPECTED:
        out["blockers"].append("BROKEN_COUNT")
    out["verdict"] = out["blockers"][0] if out["blockers"] else \
        ("EXO_AXES_TRACK" if exo_track else "NO_EXO_AXIS_TRACKS")
    return out


# ─────────────────────────────────────────────────────── selftest
def selftest() -> int:
    fails = []

    def chk(name, cond):
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)

    # G-LIVE 的牙齒：故意打主 run 路徑必須 RuntimeError
    try:
        R495._guarded_open(f"runs/{R495.LIVE}/rows.jsonl")
        raised = False
    except RuntimeError:
        raised = True
    except Exception:
        raised = False
    chk("C1_glive", raised)

    # Spearman 對課本值自檢（memory：自己現寫的統計小工具要先對課本值自檢）
    chk("C2_rho_perfect", abs(spearman([1, 2, 3, 4, 5, 6], [2, 4, 6, 8, 10, 12]) - 1.0) < 1e-12)
    chk("C2_rho_reverse", abs(spearman([1, 2, 3, 4, 5, 6], [6, 5, 4, 3, 2, 1]) + 1.0) < 1e-12)
    chk("C2_rho_none_const", spearman([1, 2, 3], [5, 5, 5]) is None)
    # 課本例：x=[1..5], y=[5,6,7,8,7] -> ties -> rho = 0.8207826816681233
    chk("C2_rho_ties", abs(spearman([1, 2, 3, 4, 5], [5, 6, 7, 8, 7]) - 0.8207826816681233) < 1e-9)
    # Σd²=2（一組相鄰對調）⇒ rho = 1 - 12/210 = 0.942857 >= 0.9（判準三.1 的導出）
    chk("C2_rho_sigd2_is_0p943",
        abs(spearman([1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 6, 5]) - (1 - 12 / 210)) < 1e-12)
    # Σd²=4（兩組相鄰對調）⇒ rho = 1 - 24/210 = 0.8857 < 0.9 ⇒ 門檻真的切在這裡
    # ⚠ 第一版寫成 [1,2,3,5,4,6]，那是 Σd²=2 不是 4（selftest 抓到，見結果檔 §附錄）
    chk("C2_rho_sigd2_4_below",
        abs(spearman([1, 2, 3, 4, 5, 6], [2, 1, 4, 3, 5, 6]) - (1 - 24 / 210)) < 1e-12
        and (1 - 24 / 210) < RHO_MIN)

    # classify 六格，每格只翻一個輸入
    S, L = R496.N_SMALL, R496.N_LARGE
    v12 = list(range(12))
    chk("C3_unscanned", classify(True, {S: 1.0, L: 1.0}, v12)[0] == "STAT_UNSCANNED")
    chk("C3_unscanned_none", classify(False, {S: 1.0, L: 1.0},
                                      [None] + v12[1:])[0] == "STAT_UNSCANNED")
    chk("C3_degenerate", classify(False, {S: None, L: None}, [1.0] * 12)[0] == "STAT_DEGENERATE")
    chk("C3_tracking", classify(False, {S: 1.0, L: 0.95}, v12)[0] == "POSITION_TRACKING")
    chk("C3_tracking_neg", classify(False, {S: -1.0, L: -0.95}, v12)[0] == "POSITION_TRACKING")
    chk("C3_opposite_sign", classify(False, {S: 1.0, L: -0.95}, v12)[0] == "NOT_TRACKING")
    chk("C3_one_tier_only", classify(False, {S: 1.0, L: 0.5}, v12)[0] == "NOT_TRACKING")
    chk("C3_rho_none", classify(False, {S: 1.0, L: None}, v12)[0] == "NOT_TRACKING")

    # 邊界：恰好 0.9 過、剛好在下面不過
    chk("C4_edge_in", classify(False, {S: 0.9, L: 0.9}, v12)[0] == "POSITION_TRACKING")
    chk("C4_edge_out", classify(False, {S: 0.8999, L: 0.9}, v12)[0] == "NOT_TRACKING")

    # 前置尺：判準 §二 的表與實作條數一致（G-COUNT 的來源）
    rows = [{"id": i, "ts": float(i), "client_ip": "a", "path": "p", "model": None,
             "machine": "1004", "error": None, "status_code": 200, "prompt_tokens": 1,
             "stream": 0, "latency_ms": 1.0, "completion_tokens": 1} for i in range(5)]
    st = build_stats(rows)
    chk("C5_count_exo", sum(1 for _n, k, _f, _fn in st if k == "EXOGENOUS") == N_EXO_EXPECTED)
    chk("C5_count_endo", sum(1 for _n, k, _f, _fn in st if k == "ENDOGENOUS") == N_ENDO_EXPECTED)
    chk("C5_names_unique", len({n for n, _k, _f, _fn in st}) == len(st))

    # C_NEG 真的與 ts 無關：把 ts 全部改掉，值不變
    r2 = [dict(r, ts=r["ts"] * 1000 + 7) for r in rows]
    chk("C6_cneg_ts_free", _cneg(rows, []) == _cneg(r2, []))
    # C_NEG 對 id 有反應（不是常數尺）
    r3 = [dict(r, id=r["id"] + 100000) for r in rows]
    chk("C6_cneg_id_sensitive", isinstance(_cneg(r3, []), float))

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
    print(f"verdict={out['verdict']}  n_windows={out['n_windows']}  "
          f"exo={out['n_exogenous']} endo={out['n_endogenous']}  "
          f"exc={out['n_exceptions']}  live_reads={out['live_reads']}  "
          f"elapsed_s={out['elapsed_s']}")
    print(f"calibration: {out['calibration']}")
    print(f"exo_tracking:     {out['exo_tracking']}")
    print(f"exo_not_tracking: {out['exo_not_tracking']}")
    print(f"endo_tracking:    {out['endo_tracking']}")
    for n, v in out["stats"].items():
        print(f"  {v['kind'][:4]:4s} {n:24s} {v['class']:18s} rho={v.get('rho_by_tier')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
