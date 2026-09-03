#!/usr/bin/env python3
"""配對分析：把兩個 arm 的 rows.jsonl 按 task_id 對起來，出 McNemar 精確檢定。

為什麼要獨立成一支工具（round138）：
  round126-137 連續 12 輪只做 monitoring checkpoint，沒有人把**已經落盤的**
  資料拿來配對分析。`g_off371_20260825`(OFF 367) 與 `g_on371_20260825`(ON 167)
  的 pool/instrument/calibration/request_policy 四項 sha 完全相同 ⇒ 早就可以配對。

判準（**寫在量測之前**，見 GAIN_STATE round138）：
  - 證據單位是 **discordant pair**，不是 paired point（b=只有 A 對、c=只有 B 對）。
  - 分母只含「兩臂都量到的格子」。`err='sandbox_check_failed'` 是**候選碼答錯**，
    算失敗、留在分母；真正的 InfraVoid 根本不會進 rows.jsonl（runner 直接 continue）。
  - 用 McNemar **精確二項**檢定，不用卡方近似——discordant 常常 <25。

round357 補（見 DECISION_20260830_R357_R278_VOID_BOUND_CAVEAT.md「沒做的事」第2點）：
  - 本工具的配對分母**本來就**只含兩臂都量到的格子，跟
    `analyze_fullbank_off.py`／`analyze_off5_gate_counterfactual.py` 那種單臂比例
    分析的判準邏輯不同，所以這裡**不套用**同一條 10% 硬閘門去擋輸出。
  - 但如果 void 率高，`common` 集合排除的題目變多，若 void 與正確性相關
    （round77 規則 B 自己的警告），discordant pair 的估計會有選擇偏誤。
    這裡只**印警告＋把每臂的 void 率放進輸出 JSON**，不擋、不改判定。
"""
import argparse
import json
import math
import pathlib

VOID_GATE = 0.10  # 只用來決定要不要印警告，SPEC_GAIN §7 同一條規則的數值


def load_rows(d: pathlib.Path) -> list[dict]:
    p = d / "rows.jsonl"
    return [json.loads(l) for l in p.open(encoding="utf-8") if l.strip()]


def exact_mcnemar_p(b: int, c: int) -> float:
    """雙尾精確二項檢定，H0: P(b)=P(c)=0.5。b+c=0 時無證據，回傳 1.0。"""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    ctr = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, ctr - half), min(1.0, ctr + half))


def arm_rows(rows: list[dict], arm: str) -> dict[str, dict]:
    return {r["task_id"]: r for r in rows if r.get("arm") == arm}


def load_notes(d: pathlib.Path) -> list[dict]:
    p = d / "notes.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.open(encoding="utf-8") if l.strip()]


def arm_void_ratio(notes: list[dict], n_measured: int, arm: str) -> dict:
    """跟 analyze_off5_gate_counterfactual.py 的 arm_void_ratio 同一條算法。"""
    n_void = sum(1 for nt in notes if nt.get("arm") == arm and "infra_void" in nt)
    total = n_measured + n_void
    ratio = (n_void / total) if total else 0.0
    return {"n_measured": n_measured, "n_void": n_void, "ratio": ratio,
            "gate_exceeded": ratio > VOID_GATE}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a-run", required=True, help="A 臂的 run 目錄")
    ap.add_argument("--a-arm", required=True)
    ap.add_argument("--b-run", required=True, help="B 臂的 run 目錄")
    ap.add_argument("--b-arm", required=True)
    ap.add_argument("--json", help="把結果寫成 JSON 到這個檔")
    ap.add_argument("--exclude-task-ids", default="",
                     help="逗號分隔的 task_id，事前排除（例：R440T 的 lcb_3613,lcb_3763）。"
                          "分子分母同時移除，比照 infra_void 鐵律 2。留空＝不排除，"
                          "用來跟排除後那次跑的結果對照，兩次都要貼出來。")
    args = ap.parse_args()
    exclude = {t.strip() for t in args.exclude_task_ids.split(",") if t.strip()}

    a_dir, b_dir = pathlib.Path(args.a_run), pathlib.Path(args.b_run)
    A = arm_rows(load_rows(a_dir), args.a_arm)
    B = arm_rows(load_rows(b_dir), args.b_arm)

    # 條件比對：pool/instrument/calibration/request_policy 不同就明講，不要靜默比下去
    cond = {}
    for key in ("pool", "instrument", "calibration", "request_policy"):
        import hashlib
        def h(d):
            s = json.load((d / "summary.json").open(encoding="utf-8")).get(key)
            return hashlib.sha256(json.dumps(s, sort_keys=True).encode()).hexdigest()[:16]
        ha, hb = h(a_dir), h(b_dir)
        cond[key] = {"a": ha, "b": hb, "same": ha == hb}

    common_all = sorted(set(A) & set(B))
    common = [t for t in common_all if t not in exclude]
    excluded_present = sorted(exclude & set(common_all))
    excluded_missing = sorted(exclude - set(common_all))
    a_ok = sum(1 for t in common if A[t]["meets_demand"])
    b_ok = sum(1 for t in common if B[t]["meets_demand"])
    disc_b = sum(1 for t in common if A[t]["meets_demand"] and not B[t]["meets_demand"])
    disc_c = sum(1 for t in common if B[t]["meets_demand"] and not A[t]["meets_demand"])
    p = exact_mcnemar_p(disc_b, disc_c)
    a_calls = sum(A[t]["calls_used"] for t in common)
    b_calls = sum(B[t]["calls_used"] for t in common)

    a_void = arm_void_ratio(load_notes(a_dir), len(A), args.a_arm)
    b_void = arm_void_ratio(load_notes(b_dir), len(B), args.b_arm)
    void_gate_warning = a_void["gate_exceeded"] or b_void["gate_exceeded"]

    out = {
        "a": {"run": str(a_dir), "arm": args.a_arm, "n_rows": len(A)},
        "b": {"run": str(b_dir), "arm": args.b_arm, "n_rows": len(B)},
        "exclude_requested": sorted(exclude),
        "exclude_applied": excluded_present,
        "exclude_not_in_common": excluded_missing,
        "n_paired_before_exclude": len(common_all),
        "conditions": cond,
        "conditions_all_same": all(v["same"] for v in cond.values()),
        "n_paired": len(common),
        "a_meets_demand": a_ok,
        "b_meets_demand": b_ok,
        "a_rate": a_ok / len(common) if common else None,
        "b_rate": b_ok / len(common) if common else None,
        "a_rate_ci95": wilson(a_ok, len(common)),
        "b_rate_ci95": wilson(b_ok, len(common)),
        "discordant_a_only": disc_b,
        "discordant_b_only": disc_c,
        "n_discordant": disc_b + disc_c,
        "mcnemar_exact_p_two_sided": p,
        "a_calls_total": a_calls,
        "b_calls_total": b_calls,
        "a_calls_per_correct": a_calls / a_ok if a_ok else None,
        "b_calls_per_correct": b_calls / b_ok if b_ok else None,
        "equal_budget": a_calls == b_calls,
        "a_void": a_void,
        "b_void": b_void,
        "void_gate_warning": void_gate_warning,
    }

    lbl_a, lbl_b = args.a_arm, args.b_arm
    if exclude:
        print(f"事前排除 {sorted(exclude)}：套用於 common 的 {len(excluded_present)} 個"
              f"（{excluded_present}），不在 common 裡的 {len(excluded_missing)} 個"
              f"（{excluded_missing}）")
        print(f"排除前配對任務數 n = {len(common_all)} → 排除後 n = {len(common)}")
    print(f"配對任務數 n = {len(common)}  （A={len(A)} 列, B={len(B)} 列）")
    print(f"條件一致：{out['conditions_all_same']}")
    for k, v in cond.items():
        if not v["same"]:
            print(f"  ⚠ {k} 不同：{v['a']} vs {v['b']}")
    print()
    print(f"{lbl_a:5s} 需求=產出  {a_ok}/{len(common)} = {100*out['a_rate']:.2f}%"
          f"  CI95 [{100*out['a_rate_ci95'][0]:.1f}, {100*out['a_rate_ci95'][1]:.1f}]")
    print(f"{lbl_b:5s} 需求=產出  {b_ok}/{len(common)} = {100*out['b_rate']:.2f}%"
          f"  CI95 [{100*out['b_rate_ci95'][0]:.1f}, {100*out['b_rate_ci95'][1]:.1f}]")
    print()
    print(f"discordant pair：只有 {lbl_a} 對 b={disc_b}，只有 {lbl_b} 對 c={disc_c}"
          f"  （證據單位 = {disc_b + disc_c}）")
    print(f"McNemar 精確雙尾 p = {p:.4f}")
    print()
    print(f"總呼叫  {lbl_a}={a_calls}  {lbl_b}={b_calls}   等預算：{out['equal_budget']}")
    if a_ok and b_ok:
        print(f"每個正確交付的呼叫數  {lbl_a}={a_calls/a_ok:.2f}  {lbl_b}={b_calls/b_ok:.2f}")
    print()
    print(f"void 率（分母＝該臂該 run 的 measured+void，不是 n_paired）"
          f"  {lbl_a}={100*a_void['ratio']:.1f}% ({a_void['n_void']}/{a_void['n_measured']+a_void['n_void']})"
          f"  {lbl_b}={100*b_void['ratio']:.1f}% ({b_void['n_void']}/{b_void['n_measured']+b_void['n_void']})")
    if void_gate_warning:
        print("⚠ VOID-GATE-WARNING：至少一臂 void 率超過 SPEC_GAIN §7 的 10% 閘門。"
              "本工具的配對分母本來就只含兩臂都量到的格子（不套用硬擋），但若 void"
              "與正確性相關，上面的 discordant pair／McNemar 結果可能有選擇偏誤——"
              "見 DECISION_20260830_R357_R278_VOID_BOUND_CAVEAT.md。")

    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
