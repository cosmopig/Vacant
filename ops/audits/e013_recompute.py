#!/usr/bin/env python3
"""e013 成本重算量具（BACKLOG line 101 收口；票 P20261112_0748-1）。
成本正確源＝每格 cell.json.metrics（model_calls/input_tokens/output_tokens）；
舊缺陷：讀 events.jsonl 事件型名 "model_call"/"token_usage"（不存在）⇒ calls/tokens 全讀 0 誤報。
口徑（對齊官方 report.py）：pass==None（infra）嚴排除分母；calls_per_success＝分母格 calls 總和（含失敗格）÷成功數；
tokens＝input+output；metrics 缺/壞→標記異常隔離，嚴禁假定 0.0 合格。
--selftest：正控制（模擬 cell.json 非零＋磁碟有 run 則活體重算）
＋負控制 1（舊 events 格式/缺 metrics→標記異常隔離，非 0.0 合格）
＋負控制 2（pass=None infra→嚴排除分母）。
全綠 → VERDICT: E013_RECOMPUTE_OK exit 0；任一紅 → E013_RECOMPUTE_FAIL exit 1。純本地離線，0 model calls。
"""
import json
import sys
import tempfile
from pathlib import Path

RUN_DIR = Path("/srv/vlab/runs/e013_dabench_pi_AC_full")
EXPECTED = {
    "A": {"n": 30, "calls_per_success": 26.93, "tokens_per_success": 583095},
    "C": {"n": 30, "calls_per_success": 14.41, "tokens_per_success": 244937},
}


def get_stats(cell_dir):
    """一格 → (stats, exclusion_reason)；None＝入分母。infra（pass is None）→排除；
    metrics 缺/壞→異常隔離。嚴禁 m.get(k,0) 以 0 填缺（舊缺陷：未測被讀成 0.0 合格）。"""
    cp, sp = cell_dir / "cell.json", cell_dir / "score.json"
    if not (cp.exists() and sp.exists()):
        return None, "missing_cell_or_score"
    cell = json.loads(cp.read_text())
    score = json.loads(sp.read_text())
    if score.get("pass") is None:
        return None, "infra_pass_none"
    m = cell.get("metrics")
    if not isinstance(m, dict) or any(not isinstance(m.get(k), (int, float))
                                      for k in ("model_calls", "input_tokens", "output_tokens")):
        return None, "missing_or_bad_metrics"
    return ({"success": bool(score["pass"]), "calls": m["model_calls"],
             "tokens": m["input_tokens"] + m["output_tokens"]}), None


def calc(cell_dirs):
    """→ (metrics, excluded[(dir, reason)])。被排除格不入分子與分母。"""
    stats, excluded = [], []
    for d in cell_dirs:
        s, why = get_stats(d)
        (excluded.append((d.name, why)) if s is None else stats.append(s))
    n = len(stats)
    ok = sum(1 for s in stats if s["success"])
    return ({"n": n, "successes": ok,
             "calls_per_success": round(sum(s["calls"] for s in stats) / ok, 2) if ok else None,
             "tokens_per_success": round(sum(s["tokens"] for s in stats) / ok) if ok else None}, excluded)


def arm_dirs(arm):
    return (sorted(d for d in RUN_DIR.iterdir() if d.name.endswith(f"-pi-{arm}-r1"))
            if RUN_DIR.is_dir() else [])


def selftest():
    fails = []
    def check(name, cond, detail=""):
        print(f"[{'PASS' if cond else 'FAIL'}] {name}" + ("" if cond else f" — {detail}"))
        if not cond:
            fails.append(name)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        def mk(name, calls, inp, out, pas):
            d = root / name
            d.mkdir()
            (d / "cell.json").write_text(json.dumps({"arm": "A", "metrics": {
                "model_calls": calls, "input_tokens": inp, "output_tokens": out}}))
            (d / "score.json").write_text(json.dumps({"pass": pas}))
            return d
        g1, g2 = mk("c1", 10, 100, 10, True), mk("c2", 20, 200, 20, True)
        m, ex = calc([g1, g2])
        check("positive: simulated metrics read non-zero",
              m["n"] == 2 and m["calls_per_success"] == 15.0 and m["tokens_per_success"] == 165 and not ex, f"{m} {ex}")
        bad = mk("bad", 5, 50, 5, True)
        (bad / "cell.json").write_text(json.dumps({"arm": "A", "events": [
            {"type": "model_call"}, {"type": "token_usage"}]}))  # 舊 events 格式：無 metrics
        m1, ex1 = calc([g1, bad])
        check("negative1: missing metrics isolated & flagged (not 0.0 pass)",
              m1["n"] == 1 and m1["calls_per_success"] == 10.0 and ex1 == [("bad", "missing_or_bad_metrics")],
              f"{m1} {ex1}")
        infra = mk("infra", 7, 70, 7, None)
        m2, ex2 = calc([g1, infra])
        check("negative2: infra pass=None excluded from denominator",
              m2["n"] == 1 and m2["successes"] == 1 and ex2 == [("infra", "infra_pass_none")], f"{m2} {ex2}")
    if RUN_DIR.is_dir():
        for arm, exp in EXPECTED.items():
            m, ex = calc(arm_dirs(arm))
            check(f"live {arm}: n={exp['n']} calls={exp['calls_per_success']} "
                  f"tokens={exp['tokens_per_success']} excluded=0",
                  m["n"] == exp["n"] and m["calls_per_success"] == exp["calls_per_success"]
                  and m["tokens_per_success"] == exp["tokens_per_success"] and not ex,
                  f"got n={m['n']} calls={m['calls_per_success']} tokens={m['tokens_per_success']} "
                  f"excluded={ex}")
    else:
        print(f"[SKIP] live: {RUN_DIR} not present on this machine")

    if fails:
        print(f"VERDICT: E013_RECOMPUTE_FAIL ({len(fails)}: {', '.join(fails)})")
        return 1
    print("VERDICT: E013_RECOMPUTE_OK")
    return 0


def main():
    if "--selftest" in sys.argv:
        return selftest()
    for arm in ("A", "C"):
        m, ex = calc(arm_dirs(arm))
        print(f"Arm {arm}: {json.dumps(m)}  excluded: {ex or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
