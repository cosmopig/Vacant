"""離線重放：ON 與 OFF5 的「等預算」在 token 會計下還等不等。

**不打任何模型端點。** 只讀已落盤的 calls.jsonl / rows.jsonl。

SPEC_GAIN §45-61 把等預算定義成每題呼叫數（ON=5、OFF5=5）。這支量的是
同樣 5 次呼叫底下，兩臂實際吞掉多少 prompt/completion token 與牆鐘時間。
判準見 runs/_analysis_r654/CRITERION.md（先寫後量）。

--selftest 會植入兩個缺陷，證明綠燈有牙齒：
  A: 把 OFF5 的 usage 洗成 ON 的 → R 必須變成 1.000（偵測「兩臂沒真的分開」）
  B: 拿掉一成 ok 呼叫的 usage → 必須報 BROKEN 而不是安靜少算
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib
import statistics
import sys

MISSING_USAGE_MAX = 0.05   # 判準推翻條件 1


def load_calls(path: pathlib.Path) -> list[dict]:
    out = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def completed_tasks(rows_path: pathlib.Path) -> dict[str, set[str]]:
    """每臂已寫進 rows.jsonl 的 task_id（＝那一格真的跑完了）。"""
    done: dict[str, set[str]] = collections.defaultdict(set)
    with rows_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            arm, tid = d.get("arm"), d.get("task_id")
            if arm and tid:
                done[arm].add(tid)
    return done


def aggregate(calls, done, arms=("ON", "OFF5")):
    """回傳 (per_arm_per_task, 第三類清單, usage 缺漏統計)。"""
    paired = set.intersection(*(done.get(a, set()) for a in arms)) if all(
        done.get(a) for a in arms) else set()

    per: dict[str, dict[str, dict]] = {a: collections.defaultdict(
        lambda: {"prompt": 0, "completion": 0, "total": 0,
                 "latency_ms": 0, "calls": 0,
                 "failed_calls": 0, "failed_latency_ms": 0}) for a in arms}
    odd = []                       # 第三類：arm 不在 arms 也不是 preflight
    ok_calls = missing_usage = 0

    for c in calls:
        meta = c.get("meta") or {}
        arm, tid = meta.get("arm"), meta.get("task_id")
        if c.get("role") == "preflight":
            continue
        if arm not in arms:
            if arm is None:
                odd.append({"role": c.get("role"), "ts_ms": c.get("ts_ms")})
            continue
        if tid not in paired:
            continue
        slot = per[arm][tid]
        if not c.get("ok"):
            slot["failed_calls"] += 1
            slot["failed_latency_ms"] += c.get("latency_ms") or 0
            continue
        ok_calls += 1
        u = c.get("usage") or {}
        pt, ct = u.get("prompt_tokens"), u.get("completion_tokens")
        if not pt:
            missing_usage += 1
        slot["prompt"] += pt or 0
        slot["completion"] += ct or 0
        slot["total"] += (u.get("total_tokens")
                          or ((pt or 0) + (ct or 0)))
        slot["latency_ms"] += c.get("latency_ms") or 0
        slot["calls"] += 1

    return per, paired, odd, ok_calls, missing_usage


def stat_block(per_task: dict, key: str) -> dict:
    vals = [v[key] for v in per_task.values()]
    if not vals:
        return {"n": 0}
    return {"n": len(vals), "median": statistics.median(vals),
            "mean": round(statistics.mean(vals), 1),
            "min": min(vals), "max": max(vals), "sum": sum(vals)}


def verdict(ratio: float) -> str:
    if ratio >= 1.10:
        return "ON_COSTS_MORE"
    if ratio <= 0.90:
        return "ON_COSTS_LESS"
    return "AGREE"


def run(run_dir: pathlib.Path, arms=("ON", "OFF5")) -> dict:
    calls = load_calls(run_dir / "calls.jsonl")
    done = completed_tasks(run_dir / "rows.jsonl")
    per, paired, odd, ok_calls, missing = aggregate(calls, done, arms)

    frac_missing = (missing / ok_calls) if ok_calls else 1.0
    res = {
        "run": str(run_dir),
        "paired_tasks": len(paired),
        "ok_calls_counted": ok_calls,
        "missing_usage": missing,
        "missing_usage_frac": round(frac_missing, 4),
        "third_category_arm_none": odd,
        "broken": frac_missing > MISSING_USAGE_MAX,
    }
    for a in arms:
        res[a] = {k: stat_block(per[a], k) for k in
                  ("prompt", "completion", "total", "latency_ms",
                   "calls", "failed_calls", "failed_latency_ms")}
    if res["broken"]:
        res["verdict"] = "BROKEN"
        return res

    hi, lo = arms[0], arms[1]
    for key in ("total", "completion", "prompt"):
        m_hi = res[hi][key]["median"] if res[hi][key]["n"] else 0
        m_lo = res[lo][key]["median"] if res[lo][key]["n"] else 0
        res[f"R_{key}_median"] = round(m_hi / m_lo, 4) if m_lo else None
        a_hi = res[hi][key]["mean"] if res[hi][key]["n"] else 0
        a_lo = res[lo][key]["mean"] if res[lo][key]["n"] else 0
        res[f"R_{key}_mean"] = round(a_hi / a_lo, 4) if a_lo else None
    res["verdict"] = (verdict(res["R_total_median"])
                      if res["R_total_median"] else "BROKEN")
    return res


def selftest(run_dir: pathlib.Path) -> int:
    """植入兩個缺陷，證明這把尺會叫。"""
    calls = load_calls(run_dir / "calls.jsonl")
    done = completed_tasks(run_dir / "rows.jsonl")
    fails = []

    base = run(run_dir)
    if base["verdict"] == "BROKEN":
        fails.append("乾淨資料就 BROKEN，尺或資料有問題")

    # A: OFF5 的 usage 全部換成該題 ON 的平均 ⇒ R 必須 ≈ 1.000
    per, paired, _, _, _ = aggregate(calls, done)
    import copy
    ca = copy.deepcopy(calls)
    on_tok = {t: per["ON"][t]["total"] for t in paired}
    for c in ca:
        m = c.get("meta") or {}
        if m.get("arm") == "OFF5" and c.get("ok") and m.get("task_id") in paired:
            n = sum(1 for x in calls
                    if (x.get("meta") or {}).get("arm") == "OFF5"
                    and (x.get("meta") or {}).get("task_id") == m["task_id"]
                    and x.get("ok"))
            share = on_tok[m["task_id"]] / max(n, 1)
            c["usage"] = {"prompt_tokens": share / 2,
                          "completion_tokens": share / 2,
                          "total_tokens": share}
    pa, pr, _, okc, miss = aggregate(ca, done)
    r_a = (statistics.median([v["total"] for v in pa["ON"].values()])
           / statistics.median([v["total"] for v in pa["OFF5"].values()]))
    if abs(r_a - 1.0) > 1e-6:
        fails.append(f"A: 兩臂洗成同量後 R={r_a:.6f}，應為 1.000000")

    # B: 拿掉一成 ok 呼叫的 usage ⇒ 必須 BROKEN
    cb = copy.deepcopy(calls)
    okidx = [i for i, c in enumerate(cb)
             if c.get("ok") and (c.get("meta") or {}).get("arm") in ("ON", "OFF5")]
    for i in okidx[::10]:
        cb[i]["usage"] = {}
    _, _, _, okc_b, miss_b = aggregate(cb, done)
    if not (okc_b and miss_b / okc_b > MISSING_USAGE_MAX):
        fails.append(f"B: 洗掉 {miss_b}/{okc_b} 筆 usage 仍未達 BROKEN 門檻")

    for f in fails:
        print(f"SELFTEST FAIL: {f}")
    if not fails:
        print("SELFTEST PASS: A 兩臂同量⇒R=1.000000；"
              f"B 缺 usage {miss_b}/{okc_b} 觸發 BROKEN 門檻")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--json", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    d = pathlib.Path(a.run_dir)
    if a.selftest:
        return selftest(d)
    res = run(d)
    for name in ("rows.jsonl", "calls.jsonl"):
        p = d / name
        res[f"sha256_{name}"] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        res[f"lines_{name}"] = sum(1 for _ in p.open())
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
