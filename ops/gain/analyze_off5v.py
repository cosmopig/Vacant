#!/usr/bin/env python3
"""round342 3arm 决定性对照的离线分析：OFF5V = 同一批 OFF5 列，换一条接受规则
（accepted_V = visible_ok）离线重算，而不是新增一条会在抽样上分岔的臂。

规格与事前判准见 `DECISION_20260830_R342_3ARM_PREREG.md`（判准写在资料产生之前，
本档只是把那份预注册转成可执行的判定，不额外发明门槛）。

主判准：OFF5V vs ON 的漏出量配对 McNemar（两臂都量到、非 void 的题目上）。
  - p >= 0.05 且 OFF5V 漏出率点估计 <= ON + 3pp  => 「机制没有加值」
  - p < 0.05 且 ON 较低                            => 「差额是机制的贡献」，报差额
  - 否则（p < 0.05 但 OFF5V 较低，或方向不明）      => 照实报，不套用上面两句话术

副判准（同一列、零 void 损失）：OFF5 vs OFF5V 的漏出量与交付率。
  重点是 OFF5V 的可见测试闸误杀了多少「本来会正确交付」的列
  （accepted=True 且 meets_demand=True 但 visible_ok=False）——
  ON 的同一道闸在 371-era 与 R278 都是 0 误杀，这里要看是否仍然成立。
"""
import argparse
import json
import math
import pathlib


def load_rows(d: pathlib.Path) -> list[dict]:
    p = d / "rows.jsonl"
    return [json.loads(l) for l in p.open(encoding="utf-8") if l.strip()]


def exact_mcnemar_p(b: int, c: int) -> float:
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="含 OFF5,ON 两臂的 run 目录")
    ap.add_argument("--off5-arm", default="OFF5")
    ap.add_argument("--on-arm", default="ON")
    ap.add_argument("--json", help="把结果写成 JSON 到这个档")
    args = ap.parse_args()

    run_dir = pathlib.Path(args.run)
    rows = load_rows(run_dir)
    OFF5 = arm_rows(rows, args.off5_arm)
    ON = arm_rows(rows, args.on_arm)

    missing_vok_off5 = [t for t, r in OFF5.items() if "visible_ok" not in r]
    if missing_vok_off5:
        print(f"⚠ {len(missing_vok_off5)}/{len(OFF5)} 条 {args.off5_arm} 列没有 visible_ok"
              f"（旧碼跑的 run，无法算 OFF5V）；先排除，不当成 False 处理")
    OFF5 = {t: r for t, r in OFF5.items() if "visible_ok" in r}

    def leaked(r: dict, accepted_key) -> bool:
        acc = accepted_key(r)
        return bool(acc) and not r["meets_demand"]

    def off5_accepted(r):
        return r["accepted"]  # 恒为 True（arm_off5 语意）

    def off5v_accepted(r):
        return r["visible_ok"]

    def on_accepted(r):
        return r["accepted"]

    # ---- 主判准：OFF5V vs ON，配对在两臂都量到的题目上 ----
    common_main = sorted(set(OFF5) & set(ON))
    on_leak = {t: leaked(ON[t], on_accepted) for t in common_main}
    off5v_leak = {t: leaked(OFF5[t], off5v_accepted) for t in common_main}
    n_main = len(common_main)
    on_leak_n = sum(on_leak.values())
    off5v_leak_n = sum(off5v_leak.values())
    # b = 只有 ON 漏出，c = 只有 OFF5V 漏出
    b_main = sum(1 for t in common_main if on_leak[t] and not off5v_leak[t])
    c_main = sum(1 for t in common_main if off5v_leak[t] and not on_leak[t])
    p_main = exact_mcnemar_p(b_main, c_main)
    on_leak_rate = on_leak_n / n_main if n_main else None
    off5v_leak_rate = off5v_leak_n / n_main if n_main else None
    gap_pp = (
        (off5v_leak_rate - on_leak_rate) * 100
        if n_main and on_leak_rate is not None else None
    )

    verdict = "insufficient_n"
    if n_main >= 30:
        if p_main >= 0.05 and gap_pp is not None and gap_pp <= 3.0:
            verdict = "no_mechanism_value（OFF5V 追平 ON，p>=0.05 且差距<=3pp）"
        elif p_main < 0.05 and on_leak_rate is not None and on_leak_rate < off5v_leak_rate:
            verdict = f"mechanism_contributes（ON 显著更低，gap={gap_pp:.2f}pp）"
        else:
            verdict = f"other（p={p_main:.4f}, gap={gap_pp}）— 照实报，不套用预设话术"
    elif n_main > 0:
        verdict = f"insufficient_n（n={n_main}<30，只能报点估计，不能宣称无加值）"

    # ---- 副判准：OFF5 vs OFF5V，同一列，零 void 损失 ----
    common_secondary = sorted(set(OFF5))  # OFF5 与 OFF5V 定义在同一批列上
    off5_delivered_ok = {
        t: (off5_accepted(OFF5[t]) and OFF5[t]["meets_demand"]) for t in common_secondary
    }
    off5v_delivered_ok = {
        t: (off5v_accepted(OFF5[t]) and OFF5[t]["meets_demand"]) for t in common_secondary
    }
    n_sec = len(common_secondary)
    off5_deliver_n = sum(off5_delivered_ok.values())
    off5v_deliver_n = sum(off5v_delivered_ok.values())
    off5_leak_n_sec = sum(leaked(OFF5[t], off5_accepted) for t in common_secondary)
    off5v_leak_n_sec = sum(leaked(OFF5[t], off5v_accepted) for t in common_secondary)
    # 误杀：本来 accepted=True 且 meets_demand=True，被 V 门槛挡下（visible_ok=False）
    false_rejects = [
        t for t in common_secondary
        if OFF5[t]["accepted"] and OFF5[t]["meets_demand"] and not OFF5[t]["visible_ok"]
    ]

    out = {
        "run": str(run_dir),
        "main_criterion": {
            "off5_arm": args.off5_arm, "on_arm": args.on_arm,
            "n_paired": n_main,
            "on_leaked": on_leak_n, "off5v_leaked": off5v_leak_n,
            "on_leak_rate": on_leak_rate, "off5v_leak_rate": off5v_leak_rate,
            "on_leak_rate_ci95": wilson(on_leak_n, n_main) if n_main else None,
            "off5v_leak_rate_ci95": wilson(off5v_leak_n, n_main) if n_main else None,
            "discordant_on_only": b_main, "discordant_off5v_only": c_main,
            "n_discordant": b_main + c_main,
            "mcnemar_exact_p_two_sided": p_main,
            "gap_pp_off5v_minus_on": gap_pp,
            "verdict": verdict,
        },
        "secondary_criterion": {
            "n_rows": n_sec,
            "off5_delivered_correct": off5_deliver_n,
            "off5v_delivered_correct": off5v_deliver_n,
            "off5_delivery_rate": off5_deliver_n / n_sec if n_sec else None,
            "off5v_delivery_rate": off5v_deliver_n / n_sec if n_sec else None,
            "off5_leaked": off5_leak_n_sec, "off5v_leaked": off5v_leak_n_sec,
            "off5_leak_rate": off5_leak_n_sec / n_sec if n_sec else None,
            "off5v_leak_rate": off5v_leak_n_sec / n_sec if n_sec else None,
            "false_rejects_of_correct_answers": len(false_rejects),
            "false_reject_task_ids": false_rejects,
        },
        "excluded_off5_rows_missing_visible_ok": len(missing_vok_off5),
    }

    print(f"=== 主判准：{args.off5_arm}V vs {args.on_arm}（配对 n={n_main}） ===")
    if n_main:
        print(f"ON    漏出 {on_leak_n}/{n_main} = {100*on_leak_rate:.2f}%")
        print(f"OFF5V 漏出 {off5v_leak_n}/{n_main} = {100*off5v_leak_rate:.2f}%")
        print(f"discordant: 只有 ON 漏出 b={b_main}，只有 OFF5V 漏出 c={c_main}")
        print(f"McNemar 精确双尾 p = {p_main:.4f}")
        print(f"gap (OFF5V - ON) = {gap_pp:.2f}pp")
    print(f"判定：{verdict}")
    print()
    print(f"=== 副判准：{args.off5_arm} vs {args.off5_arm}V（同列 n={n_sec}） ===")
    if n_sec:
        print(f"OFF5  正确交付 {off5_deliver_n}/{n_sec} = {100*off5_deliver_n/n_sec:.2f}%"
              f"  漏出 {off5_leak_n_sec} ({100*off5_leak_n_sec/n_sec:.2f}%)")
        print(f"OFF5V 正确交付 {off5v_deliver_n}/{n_sec} = {100*off5v_deliver_n/n_sec:.2f}%"
              f"  漏出 {off5v_leak_n_sec} ({100*off5v_leak_n_sec/n_sec:.2f}%)")
        print(f"误杀（本来正确交付、被 V 闸挡下）= {len(false_rejects)}"
              + (f"：{false_rejects}" if false_rejects else ""))

    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
