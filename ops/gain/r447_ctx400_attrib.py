#!/usr/bin/env python3
"""把 r447 那通 `Context size has been exceeded` 400 歸因——零 API，只讀 calls.jsonl。

判準寫在 `DECISION_20260904_R447_CTX400_ATTRIBUTION.md` §四，**先 commit 才有這支尺**
（commit f0cd86d）。本檔只實作那些規則，不新增規則、不改門檻。

用法：
  python3 ops/gain/r447_ctx400_attrib.py --selftest
  python3 ops/gain/r447_ctx400_attrib.py --run runs/g_r447_conform_lcb2 [--json out.json]
"""
from __future__ import annotations
import argparse, json, pathlib, statistics, sys

MUTANT = ""
POWERS = [8192, 16384, 32768, 65536, 131072]   # DECISION §四 R2 的 L 候選，逐字
R5_RATIO = 10.0                                 # DECISION §四 R5，逐字
CTX_ERROR_MARK = "Context size has been exceeded"


def load(path: pathlib.Path) -> list[dict]:
    return [json.loads(l) for l in path.open() if l.strip()]


def _mut() -> str:
    import os
    return os.environ.get("MUTANT", MUTANT)


def adjudicate(calls: list[dict]) -> dict:
    """DECISION §四 的六條規則，全部只吃 calls。"""
    out: dict = {}
    gens = [c for c in calls if c.get("role") == "gen"]
    ok_gen = [c for c in gens if c.get("ok") and (c.get("usage") or {}).get("total_tokens")]
    target = [c for c in calls if CTX_ERROR_MARK in (c.get("error") or "")]
    out["ctx400_calls"] = len(target)
    if len(target) != 1:
        out["verdict"] = "NO_SINGLE_CTX400_CALL"
        return out
    f = target[0]
    fm = f.get("meta") or {}
    out["target"] = {"arm": fm.get("arm"), "task_id": fm.get("task_id"),
                     "attempt": f.get("attempt"), "latency_ms": f.get("latency_ms"),
                     "prompt_chars": len(f.get("prompt") or ""),
                     "system_chars": len(f.get("system") or "")}

    # ── (1) T_max_ok
    tmax = max((c["usage"]["total_tokens"] for c in ok_gen), default=None)
    if _mut() == "M1_tmax_uses_prompt_only":
        tmax = max((c["usage"]["prompt_tokens"] for c in ok_gen), default=None)
    out["T_max_ok"] = tmax
    out["T_max_ok_call"] = next(({"arm": (c.get("meta") or {}).get("arm"),
                                  "task_id": (c.get("meta") or {}).get("task_id"),
                                  "completion_tokens": c["usage"]["completion_tokens"],
                                  "total_tokens": c["usage"]["total_tokens"]}
                                 for c in ok_gen if c["usage"]["total_tokens"] == tmax), None)

    # ── (2a) P_fail：chars→prompt_tokens 的線性校準（只用成功通）
    xs = [len(c.get("system") or "") + len(c.get("prompt") or "") for c in ok_gen]
    ys = [c["usage"]["prompt_tokens"] for c in ok_gen]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    slope = (sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den) if den else 0.0
    icept = my - slope * mx
    resid = [abs(y - (slope * x + icept)) for x, y in zip(xs, ys)]
    out["prompt_fit"] = {"n": n, "slope_tok_per_char": round(slope, 5),
                         "intercept": round(icept, 2),
                         "resid_median": round(statistics.median(resid), 2),
                         "resid_max": round(max(resid), 2)}
    x_f = out["target"]["system_chars"] + out["target"]["prompt_chars"]
    p_fail = slope * x_f + icept
    out["P_fail_est"] = round(p_fail, 1)

    # ── (2b) C_fail：兩條路
    lat_f = f["latency_ms"]
    sib = [c for c in ok_gen if abs(c["latency_ms"] - lat_f) <= 0.02 * lat_f]
    sib_ct = [c["usage"]["completion_tokens"] for c in sib]
    rates = [c["usage"]["completion_tokens"] / (c["latency_ms"] / 1000.0) for c in ok_gen
             if c["latency_ms"] > 0]
    rate_med = statistics.median(rates)
    c_rate = rate_med * lat_f / 1000.0
    cands = sorted(sib_ct + [c_rate])
    out["C_fail_paths"] = {"sibling_near_latency": sib_ct,
                           "median_tok_per_s": round(rate_med, 2),
                           "rate_based": round(c_rate, 1)}
    t_lo, t_hi = min(cands) + p_fail, max(cands) + p_fail
    out["T_fail_lo"], out["T_fail_hi"] = round(t_lo, 1), round(t_hi, 1)

    # ── (3) 重試
    same = [c for c in gens if (c.get("meta") or {}).get("arm") == fm.get("arm")
            and (c.get("meta") or {}).get("task_id") == fm.get("task_id")
            and c.get("attempt", 1) > f.get("attempt", 1) and c.get("ok")]
    out["retry"] = [{"attempt": c["attempt"], "total_tokens": c["usage"]["total_tokens"],
                     "completion_tokens": c["usage"]["completion_tokens"],
                     "latency_ms": c["latency_ms"]} for c in same]

    # ── (4) 自我重疊
    def iv(c):
        return (c["ts_ms"] - c["latency_ms"], c["ts_ms"])
    a0, a1 = iv(f)
    ovl = [{"arm": (c.get("meta") or {}).get("arm"), "task_id": (c.get("meta") or {}).get("task_id"),
            "role": c["role"]}
           for c in calls if c is not f and iv(c)[0] < a1 and a0 < iv(c)[1]]
    out["overlap_self"] = bool(ovl)
    out["overlap_self_calls"] = ovl
    out["overlap_note"] = ("false 不反證 H-B：別的客戶端打同一個中轉，我們的 calls.jsonl 看不見")

    # ── (5) 延遲
    lats = sorted(c["latency_ms"] for c in ok_gen)
    lat_med = statistics.median(lats)
    out["lat_fail_ms"], out["lat_median_ok_ms"] = lat_f, lat_med
    out["lat_ratio"] = round(lat_f / lat_med, 2) if lat_med else None
    out["R5"] = ("PREFLIGHT_REFUTED" if lat_med and lat_f > R5_RATIO * lat_med
                 else "PREFLIGHT_NOT_REFUTED")

    # ── 判決：R6 優先於 R1/R2（DECISION §四）
    r6 = any(r["total_tokens"] >= t_lo for r in out["retry"])
    if _mut() == "M2_r6_ignores_size":
        r6 = bool(out["retry"])
    if r6:
        v = "STATIC_CEILING_REFUTED_BY_RETRY"
    elif tmax is not None and tmax > t_hi:
        v = "STATIC_CEILING_REFUTED_BY_MAX"
    elif tmax is not None and tmax < t_lo and any(tmax < L <= t_hi for L in POWERS):
        L = next(L for L in POWERS if tmax < L <= t_hi)
        v = f"STATIC_CEILING_CONSISTENT(L={L})"
    else:
        v = "INCONCLUSIVE_MAGNITUDE"
    out["R6_fired"] = r6
    out["verdict"] = v
    out["surviving_hypotheses"] = (["H-B", "H-D"] if v.startswith("STATIC_CEILING_REFUTED")
                                   and out["R5"] == "PREFLIGHT_REFUTED"
                                   else ["H-A", "H-B", "H-C", "H-D"] if v == "INCONCLUSIVE_MAGNITUDE"
                                   else ["H-B", "H-C", "H-D"])
    return out


# ───────────────────────── selftest ─────────────────────────
def _call(**kw):
    d = {"role": "gen", "ok": True, "attempt": 1, "ts_ms": 0, "latency_ms": 1000,
         "system": "s" * 10, "prompt": "p" * 100, "meta": {"arm": "OFF5", "task_id": "t1"}}
    d.update(kw)
    return d


def _usage(pt, ct):
    return {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": pt + ct}


def _base(fail_lat=100000):
    """一份最小資料：n 通成功 + 1 通 400。"""
    cs = []
    for i in range(20):
        ct = 1000 + i * 10
        cs.append(_call(ts_ms=10_000 * (i + 1), latency_ms=20000,
                        usage=_usage(100, ct), meta={"arm": "OFF", "task_id": f"t{i}"}))
    cs.append(_call(ts_ms=10_000_000, latency_ms=fail_lat, ok=False, usage=None,
                    error='HTTPError: HTTP Error 400: Bad Request | body={"error":"Context size has been exceeded."}'))
    return cs


def selftest() -> int:
    fails = []

    def chk(label, cond, extra=""):
        print(f"  {'PASS' if cond else 'FAIL'}  {label}  {extra}")
        if not cond:
            fails.append(label)

    # F1：找得到唯一那通
    r = adjudicate(_base())
    chk("F1 ctx400_calls==1", r["ctx400_calls"] == 1)
    # F2：沒有 400 通 → 不准硬判
    r0 = adjudicate([c for c in _base() if c.get("ok")])
    chk("F2 無 400 通 → NO_SINGLE_CTX400_CALL", r0["verdict"] == "NO_SINGLE_CTX400_CALL")
    # F3：R1（有成功通 total 遠超過失敗估計）
    cs = _base(fail_lat=20000)
    # 這通刻意放在「近似延遲」窗之外（±2%），否則它自己會被當成 sibling 撐大 T_fail_hi
    cs.append(_call(ts_ms=99_000, latency_ms=30000, usage=_usage(100, 900_000),
                    meta={"arm": "OFF", "task_id": "big"}))
    r = adjudicate(cs)
    chk("F3 R1 refuted_by_max", r["verdict"] == "STATIC_CEILING_REFUTED_BY_MAX", r["verdict"])
    # F4：R2（所有成功通都很小、失敗估計跨過一個 2 的冪）
    cs = _base(fail_lat=20000 * 400)   # 估計 ~ 中位速率 × 很長 → 遠大於 tmax
    r = adjudicate(cs)
    chk("F4 R2 consistent(L)", r["verdict"].startswith("STATIC_CEILING_CONSISTENT"), r["verdict"])
    # F5：R6 優先——重試通夠大時蓋掉 R1/R2
    cs = _base(fail_lat=20000 * 400)
    cs.append(_call(ts_ms=10_100_000, latency_ms=20000, attempt=2, usage=_usage(100, 10_000_000),
                    meta={"arm": "OFF5", "task_id": "t1"}))
    r = adjudicate(cs)
    chk("F5 R6 蓋過 R2", r["verdict"] == "STATIC_CEILING_REFUTED_BY_RETRY", r["verdict"])
    # F5b：重試通存在但太小 → R6 不准點火
    cs = _base(fail_lat=20000 * 400)
    cs.append(_call(ts_ms=10_100_000, latency_ms=20000, attempt=2, usage=_usage(100, 5),
                    meta={"arm": "OFF5", "task_id": "t1"}))
    r = adjudicate(cs)
    chk("F5b 小重試通不點火 R6", r["R6_fired"] is False, str(r["R6_fired"]))
    # F6：R5 兩個方向
    chk("F6a 長延遲 → PREFLIGHT_REFUTED", adjudicate(_base(fail_lat=20000 * 11))["R5"] == "PREFLIGHT_REFUTED")
    chk("F6b 短延遲 → NOT_REFUTED", adjudicate(_base(fail_lat=1000))["R5"] == "PREFLIGHT_NOT_REFUTED")
    # F7：重疊偵測兩個方向（ts_ms 是結束時刻）
    cs = _base(fail_lat=100000)
    cs.append(_call(ts_ms=9_950_000, latency_ms=100000, meta={"arm": "X", "task_id": "ovl"},
                    usage=_usage(1, 1)))
    chk("F7a 有重疊 → true", adjudicate(cs)["overlap_self"] is True)
    chk("F7b 無重疊 → false", adjudicate(_base())["overlap_self"] is False)
    # F8：prompt 校準的殘差有印出來且是數字
    r = adjudicate(_base())
    chk("F8 prompt_fit 有殘差", isinstance(r["prompt_fit"]["resid_max"], float))

    print(f"\n{'PASS' if not fails else 'FAIL'} total={11} failed={len(fails)} {fails}")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.run:
        ap.error("--run 或 --selftest")
    d = pathlib.Path(a.run)
    calls = load(d / "calls.jsonl")
    out = adjudicate(calls)
    out["run"] = a.run
    out["calls_lines"] = len(calls)
    js = json.dumps(out, ensure_ascii=False, indent=2)
    if a.json:
        pathlib.Path(a.json).write_text(js)
    print(js)
    return 0


if __name__ == "__main__":
    sys.exit(main())
