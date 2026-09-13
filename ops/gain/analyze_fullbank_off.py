"""P4 讀法（round78 §6 預先寫死，量測前訂死，不准跑完再挑）。

DECISION_20260825_ROUND78_FULLBANK_OFF.md §6 原文：
    全庫 OFF 失敗率 >= 35%       ⇒ route A（擴 n，條件不動）
    25% <= 失敗率 < 35%          ⇒ 用實測逐題結果重算 required-n，
                                    只有 required-n <= 371 的那些對才值得跑
    失敗率 < 25%                  ⇒ 現行 worker 池太強，B（換題庫／弱化 worker）
                                    成為必要而非選項，另立 DECISION

本工具只做讀出（read-only）：
  1. 從 rows.jsonl 直接算失敗率（不信任 summary.json——那份只在 arm 跑完後
     才被改寫，run 進行中讀到的是啟動時的空殼快照，見 round79 現場核對）。
  2. SPEC_GAIN §7 的 infra_void 閘門：void/(measured+void) > 10% ⇒ 整條臂
     作廢，不得下任何分類（不只是「先不分類」，是回報 BROKEN）。
  3. 重測雜訊底線：全庫 run 前 60 題（同 seed 同 offset ⇒ task_id 逐項相同）
     vs v3 OFF baseline 47/60，逐題比對 accepted&meets_demand 是否一致。
     round77 §6 的警告：若這裡差距 >= 5pp，所有 required-n 都是低估。
  4. run 未跑滿（measured < n_planned）時印 PRELIMINARY 橫幅，分類結果只供
     監控參考，不得引用為 P4 的正式讀出——正式讀出要等 run_complete。

用法：
    python3 ops/gain/analyze_fullbank_off.py runs/g_off371_20260825 \
        --off60-baseline runs/g_off60_qwenonly_20260824 [--json OUT]
    python3 ops/gain/analyze_fullbank_off.py --self-test
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

VOID_GATE = 0.10
ROUTE_A_THRESHOLD = 0.35
ROUTE_B_THRESHOLD = 0.25
NOISE_FLOOR_ALARM_PP = 5.0


def load_rows(d: Path) -> list[dict]:
    return [json.loads(l) for l in (d / "rows.jsonl").open() if l.strip()]


def load_notes(d: Path) -> list[dict]:
    p = d / "notes.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.open() if l.strip()]


def load_summary(d: Path) -> dict:
    return json.loads((d / "summary.json").read_text())


def void_gate(n_measured: int, n_void: int) -> dict:
    total = n_measured + n_void
    ratio = (n_void / total) if total else 0.0
    return {"n_measured": n_measured, "n_void": n_void, "void_ratio": ratio,
            "gate_exceeded": ratio > VOID_GATE, "gate_threshold": VOID_GATE}


def classify_route(failure_rate: float) -> dict:
    if failure_rate >= ROUTE_A_THRESHOLD:
        route = "A"
        reason = f"失敗率 {failure_rate:.4f} >= {ROUTE_A_THRESHOLD} ⇒ 效應空間夠，走 A（擴 n，條件不動）"
    elif failure_rate >= ROUTE_B_THRESHOLD:
        route = "recompute_required_n"
        reason = (f"{ROUTE_B_THRESHOLD} <= 失敗率 {failure_rate:.4f} < {ROUTE_A_THRESHOLD} "
                  "⇒ 用實測逐題結果重算 required-n，只有 required-n<=371 的對才值得跑")
    else:
        route = "B_necessary"
        reason = f"失敗率 {failure_rate:.4f} < {ROUTE_B_THRESHOLD} ⇒ 現行 worker 池太強，B 成為必要而非選項"
    return {"route": route, "failure_rate": failure_rate, "reason": reason}


def retest_noise_floor(fullbank_rows: list[dict], baseline_rows: list[dict],
                        baseline_seed: str, fullbank_seed: str) -> dict:
    if baseline_seed != fullbank_seed:
        return {"broken": True, "reason": f"seed 不同（baseline={baseline_seed} vs fullbank={fullbank_seed}）⇒ 題序不可比"}
    off_full = [r for r in fullbank_rows if r.get("arm") == "OFF"]
    off_base = [r for r in baseline_rows if r.get("arm") == "OFF"]
    if len(off_full) < 60 or len(off_base) < 60:
        return {"skipped": True, "reason": f"需要至少60題，目前 fullbank={len(off_full)} baseline={len(off_base)}"}
    first60 = off_full[:60]
    base60 = off_base[:60]
    for a, b in zip(first60, base60):
        if a["task_id"] != b["task_id"]:
            return {"broken": True, "reason": f"前60題題序不同（{a['task_id']} vs {b['task_id']}）⇒ offset/seed 假設錯"}
    agree = sum(1 for a, b in zip(first60, base60)
                if bool(a.get("accepted") and a.get("meets_demand")) ==
                   bool(b.get("accepted") and b.get("meets_demand")))
    full_correct = sum(1 for r in first60 if r.get("accepted") and r.get("meets_demand"))
    base_correct = sum(1 for r in base60 if r.get("accepted") and r.get("meets_demand"))
    gap_pp = abs(full_correct - base_correct) / 60 * 100
    return {
        "broken": False, "skipped": False,
        "n": 60, "agree": agree, "agreement_rate": agree / 60,
        "fullbank_first60_correct": full_correct, "baseline_correct": base_correct,
        "gap_pp": gap_pp, "alarm": gap_pp >= NOISE_FLOOR_ALARM_PP,
        "alarm_reason": (f"重測缺口 {gap_pp:.2f}pp >= {NOISE_FLOOR_ALARM_PP}pp ⇒ round77 所有 required-n 都是低估"
                          if gap_pp >= NOISE_FLOOR_ALARM_PP else None),
    }


def analyze(run_dir: Path, baseline_dir: Path | None) -> dict:
    rows = load_rows(run_dir)
    notes = load_notes(run_dir)
    off_rows = [r for r in rows if r.get("arm") == "OFF"]
    n_void = sum(1 for nt in notes if "infra_void" in nt)
    n_measured = len(off_rows)
    n_correct = sum(1 for r in off_rows if r.get("accepted") and r.get("meets_demand"))
    gate = void_gate(n_measured, n_void)

    s = load_summary(run_dir)
    n_planned = s.get("n")
    is_partial = n_measured < n_planned if n_planned else True

    out = {
        "run_dir": str(run_dir), "seed": s.get("seed"),
        "n_planned": n_planned, "n_measured": n_measured, "n_void": n_void,
        "is_partial": is_partial,
        "void_gate": gate,
    }
    if gate["gate_exceeded"]:
        out["classification"] = None
        out["broken"] = f"infra_void 比例 {gate['void_ratio']:.2%} > {VOID_GATE:.0%} 閘門 ⇒ 整條臂作廢（SPEC_GAIN §7），不分類"
        return out

    failure_rate = 1 - (n_correct / n_measured) if n_measured else None
    out["n_correct"] = n_correct
    out["failure_rate"] = failure_rate
    out["classification"] = classify_route(failure_rate) if failure_rate is not None else None

    if baseline_dir is not None:
        base_rows = load_rows(baseline_dir)
        base_summary = load_summary(baseline_dir)
        out["retest_noise_floor"] = retest_noise_floor(
            rows, base_rows, base_summary.get("seed"), s.get("seed"))
    return out


def _run_self_tests() -> int:
    cases = []

    def check(name, cond):
        cases.append((name, bool(cond)))

    check("route_A_at_exactly_35pct", classify_route(0.35)["route"] == "A")
    check("route_recompute_just_below_35pct", classify_route(0.3499)["route"] == "recompute_required_n")
    check("route_recompute_at_exactly_25pct", classify_route(0.25)["route"] == "recompute_required_n")
    check("route_B_necessary_just_below_25pct", classify_route(0.2499)["route"] == "B_necessary")
    check("route_A_above_35pct", classify_route(0.9)["route"] == "A")
    check("route_B_at_zero", classify_route(0.0)["route"] == "B_necessary")

    check("void_gate_exactly_10pct_not_exceeded", void_gate(90, 10)["gate_exceeded"] is False)
    check("void_gate_just_above_10pct_exceeded", void_gate(89, 11)["gate_exceeded"] is True)
    check("void_gate_zero_void", void_gate(100, 0)["gate_exceeded"] is False)

    mk = lambda tid, ok: {"arm": "OFF", "task_id": tid, "accepted": True, "meets_demand": ok}
    full = [mk(f"t{i}", True) for i in range(60)]
    base_agree = [mk(f"t{i}", True) for i in range(60)]
    r = retest_noise_floor(full, base_agree, "seed-x", "seed-x")
    check("retest_perfect_agreement", r["agreement_rate"] == 1.0 and r["gap_pp"] == 0.0 and not r["alarm"])

    base_disagree = [mk(f"t{i}", i >= 6) for i in range(60)]
    r2 = retest_noise_floor(full, base_disagree, "seed-x", "seed-x")
    check("retest_gap_triggers_alarm", r2["gap_pp"] == 10.0 and r2["alarm"] is True)

    r3 = retest_noise_floor(full, base_agree, "seed-x", "seed-y")
    check("retest_seed_mismatch_broken", r3["broken"] is True)

    base_reordered = [mk(f"tX{i}", True) for i in range(60)]
    r4 = retest_noise_floor(full, base_reordered, "seed-x", "seed-x")
    check("retest_task_order_mismatch_broken", r4["broken"] is True)

    r5 = retest_noise_floor(full[:10], base_agree[:10], "seed-x", "seed-x")
    check("retest_below_60_skipped", r5.get("skipped") is True)

    ok = True
    for name, passed in cases:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
        ok = ok and passed
    print(f"self-test: {sum(p for _, p in cases)}/{len(cases)} passed")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", nargs="?")
    ap.add_argument("--off60-baseline")
    ap.add_argument("--json")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return _run_self_tests()

    if not a.run_dir:
        ap.error("run_dir is required unless --self-test")

    run_dir = Path(a.run_dir)
    baseline_dir = Path(a.off60_baseline) if a.off60_baseline else None
    out = analyze(run_dir, baseline_dir)

    if out.get("is_partial"):
        print(f"⚠ PRELIMINARY — n_measured={out['n_measured']}/{out.get('n_planned')}，"
              "run 未跑滿，以下分類僅供監控參考，不是 P4 正式讀出")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if a.json:
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
