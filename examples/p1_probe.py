"""P1-0 思考模式探針（17 §P1-0；R1 機時重估的前置）。

量什麼（只寫觀測，不做任何效果宣稱）：
  1. ≥20 筆**思考模式**（R1：無 /no_think、無 max_tokens 上限）呼叫的
     延遲分布（median/p95/max）與 tok/s；
  2. 同題 no_think on/off 各 10 筆的正確率對照（帶分母）；
  3. 產出 RECORD_SPEC 合格包（manifest/model_io/ledger/SHA256SUMS），
     供機時裁決引用：由 p95 重調 watchdog/單呼叫 timeout、由 median 重估
     X1/X3 總機時。不得以恢復 /no_think 當機時壓縮手段（R1）。

用法：
    VACANT_ENDPOINT=http://<vm-host>:1234 python examples/p1_probe.py \
        --model qwen/qwen3.6-35b-a3b --n-think 20 --n-compare 10
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path

from vacant.batch import Watchdog
from vacant.brains import LMStudioBrain
from vacant.checks import compile_check
from vacant.record import check as record_check
from vacant.record import pack as record_pack
from vacant.x1 import make_pilot_tasks


def _pct(xs: list[float], p: float) -> float:
    if not xs:
        return float("nan")
    xs = sorted(xs)
    i = min(len(xs) - 1, max(0, round(p / 100 * (len(xs) - 1))))
    return xs[i]


def _call(brain, prompt: str, check, task_id: str, arm: str, io_f) -> dict:
    t0 = time.time()
    answer = brain.generate(prompt)
    wall_ms = int((time.time() - t0) * 1000)
    usage = getattr(brain, "last_usage", None)
    passed = bool(compile_check(check)(answer))
    rec = {"task_id": task_id, "arm": arm, "wall_ms": wall_ms,
           "usage": usage, "passed": passed,
           "prompt_sha": __import__("hashlib").sha256(prompt.encode()).hexdigest()[:16],
           "ts_ms": int(t0 * 1000)}
    io_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    io_f.flush()
    return rec


def main() -> None:
    ap = argparse.ArgumentParser(description="P1-0 思考模式探針（17 §P1-0）")
    ap.add_argument("--base", default=os.environ.get("VACANT_ENDPOINT", "http://localhost:1234"))
    ap.add_argument("--model", default="qwen/qwen3.6-35b-a3b")
    ap.add_argument("--api", default="openai",
                    help="'openai'(/v1/chat/completions) 或 'responses'(/api/v1/chat)")
    ap.add_argument("--n-think", type=int, default=20)
    ap.add_argument("--n-compare", type=int, default=10)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    run_dir = Path(args.out or f"runs/p1_probe/{int(time.time())}")
    run_dir.mkdir(parents=True, exist_ok=True)

    wd = Watchdog(args.base, on_down=lambda m: print(f"[watchdog] {m}"))
    if not wd.wait_alive(retries=3, interval=5):
        raise SystemExit(f"端點 {args.base} 不可用")
    # R1：不送 max_tokens（無上限）、不加 /no_think（思考開）
    brain = LMStudioBrain(args.base, args.model, api=args.api,
                          timeout=900, max_tokens=None)
    tasks = make_pilot_tasks(7)  # 3 族 × 7＝21 題
    think_tasks = tasks[: args.n_think]
    cmp_tasks = tasks[: args.n_compare]

    t_start = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print(f"P1-0 探針：{args.model} @ {args.base}（思考模式，R1）→ {run_dir}")
    io_path = run_dir / "model_io.jsonl"
    ledger_path = run_dir / "ledger_events.jsonl"
    recs = []
    with io_path.open("w", encoding="utf-8") as io_f, \
            ledger_path.open("w", encoding="utf-8") as led_f:
        for t in think_tasks:
            r = _call(brain, t.prompt, t.check, t.task_id, "think", io_f)
            recs.append(r)
            led_f.write(json.dumps({"type": "PROBE", "arm": "think", "task_id": t.task_id,
                                    "wall_ms": r["wall_ms"], "passed": r["passed"],
                                    "ts_ms": r["ts_ms"]}) + "\n")
            print(f"  think {t.task_id[:8]} {r['wall_ms']/1000:6.1f}s "
                  f"{'✓' if r['passed'] else '✗'} usage={r['usage']}")
        for t in cmp_tasks:
            r = _call(brain, t.prompt + "\n/no_think", t.check, t.task_id, "no_think", io_f)
            recs.append(r)
            led_f.write(json.dumps({"type": "PROBE", "arm": "no_think", "task_id": t.task_id,
                                    "wall_ms": r["wall_ms"], "passed": r["passed"],
                                    "ts_ms": r["ts_ms"]}) + "\n")
            print(f"  no_th {t.task_id[:8]} {r['wall_ms']/1000:6.1f}s "
                  f"{'✓' if r['passed'] else '✗'}")

    think = [r for r in recs if r["arm"] == "think"]
    nothink = [r for r in recs if r["arm"] == "no_think"]
    walls = [r["wall_ms"] / 1000 for r in think]
    toks = [r["usage"].get("completion_tokens") for r in think
            if r.get("usage") and r["usage"].get("completion_tokens")]
    summary = {
        "model": args.model, "endpoint": args.base, "thinking": True,
        "n_think": len(think), "think_pass": sum(1 for r in think if r["passed"]),
        "think_wall_s": {"median": _pct(walls, 50), "p95": _pct(walls, 95),
                         "max": max(walls) if walls else None},
        "think_completion_tokens": {"median": _pct(toks, 50), "p95": _pct(toks, 95)},
        "n_no_think": len(nothink),
        "no_think_pass": sum(1 for r in nothink if r["passed"]),
        "no_think_wall_s_median": _pct([r["wall_ms"] / 1000 for r in nothink], 50),
        "utc_start": t_start,
    }
    print("\n=== 探針結果（觀測，非效果宣稱）===")
    print(f"思考模式：median {summary['think_wall_s']['median']:.1f}s "
          f"p95 {summary['think_wall_s']['p95']:.1f}s max {summary['think_wall_s']['max']:.1f}s "
          f"（{len(think)} 筆）")
    print(f"正確率：think {summary['think_pass']}/{len(think)} "
          f"vs no_think {summary['no_think_pass']}/{len(nothink)}")
    x1_calls = 3 * 215  # 三臂 × T
    est_h = summary["think_wall_s"]["median"] * x1_calls / 3600
    print(f"X1 粗估（3×215 呼叫 @median）：~{est_h:.1f}h（p95 尾部另計）")

    record_pack(run_dir, {
        "model_id": args.model, "endpoint": args.base, "no_think": False,
        "seeds": ["probe"], "trust_arm": "probe",
        "scripts": [str(Path(__file__).resolve())], "utc_start": t_start,
    })
    ok, problems = record_check(run_dir)
    (run_dir / "summary.json").write_text(
        json.dumps({**summary, "record_check_ok": ok, "problems": problems},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"record check：{'PASS' if ok else 'FAIL — ' + '; '.join(problems)}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
