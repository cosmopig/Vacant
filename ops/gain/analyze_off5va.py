#!/usr/bin/env python3
"""round388：off5v 的「(b,c)=(0,5) 卡 14 個檢查點」有沒有一個確定性的解釋。

`analyze_off5v.py`（round342）比較 ON 與 OFF5V（同一批 OFF5 列，離線把接受規則
換成 visible_ok）。round388 逐一檢查那些 discordant 列才發現：ON 的 `accepted`
公式是 `visible_ok and (audit_ok is not False)`（`gain_run.py:557`）——`audit_ok`
是 `sha256("audit:"+task_id) < audit_rate`（預設 0.2）決定要不要對這一題**額外
免費**（不耗一次模型呼叫）跑一次隱藏測資。OFF5／OFF5V 從來沒有這一道閘
——不是實作疏漏，是 self-consistency 的定義裡本來就沒有「偷看隱藏測資」這一步。

這支腳本離線把**同一條確定性稽核規則**套到 OFF5 自己選出的那份程式碼上
（zero 新增模型呼叫——OFF5 的 `meets_demand` 早就量過，只是拿來當「稽核結果」
用而已），產生 OFF5VA（V=visible gate, A=audit gate），再與 ON 重新配對比較。

若 OFF5VA 追上 ON（gap 收斂、p 值不再卡在同一個點）⇒ off5v 那道 8pp 差距的
主要來源是「ON 結構性擁有、OFF5 結構性沒有」的免費稽核存取權，不是同儕評審
／修訂機制本身的判斷力。這件事本身不推翻「ON 比 OFF5 好」（稽核也是 Vacant
機制的一部分，見 `vacant/auditor.py`），但它把「哪一段機制在加值」的歸因
從「多智能體評審」修正成「確定性稽核」——兩者是 Vacant 裡不同的子機制。
"""
import argparse
import hashlib
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


def audited(task_id: str, audit_rate: float) -> bool:
    # 逐字元照抄 gain_run.py:550-551 的規則，同一顆 hash，不是新的隨機來源。
    h = int(hashlib.sha256(f"audit:{task_id}".encode()).hexdigest()[:8], 16)
    return (h / 0xFFFFFFFF) < audit_rate


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--off5-arm", default="OFF5")
    ap.add_argument("--on-arm", default="ON")
    ap.add_argument("--audit-rate", type=float, default=0.2,
                     help="必須等於 ON 那次跑用的 --audit-rate，否則稽核抽樣不對齊")
    ap.add_argument("--json")
    args = ap.parse_args()

    run_dir = pathlib.Path(args.run)
    rows = load_rows(run_dir)
    OFF5 = arm_rows(rows, args.off5_arm)
    ON = arm_rows(rows, args.on_arm)

    missing = [t for t, r in OFF5.items() if "visible_ok" not in r]
    OFF5 = {t: r for t, r in OFF5.items() if "visible_ok" in r}
    if missing:
        print(f"⚠ {len(missing)}/{len(missing) + len(OFF5)} 條 {args.off5_arm} 列沒有 "
              f"visible_ok，排除")

    def off5va_accepted(t: str, r: dict) -> bool:
        if not r["visible_ok"]:
            return False
        if audited(t, args.audit_rate):
            return bool(r["meets_demand"])  # 已知的稽核結果，非新量測
        return True

    def leaked(accepted: bool, meets_demand: bool) -> bool:
        return accepted and not meets_demand

    common = sorted(set(OFF5) & set(ON))
    n = len(common)
    n_audited = sum(1 for t in common if audited(t, args.audit_rate))

    on_leak = {t: leaked(ON[t]["accepted"], ON[t]["meets_demand"]) for t in common}
    off5va_leak = {
        t: leaked(off5va_accepted(t, OFF5[t]), OFF5[t]["meets_demand"]) for t in common
    }
    on_n = sum(on_leak.values())
    off5va_n = sum(off5va_leak.values())
    b = sum(1 for t in common if on_leak[t] and not off5va_leak[t])
    c = sum(1 for t in common if off5va_leak[t] and not on_leak[t])
    p = exact_mcnemar_p(b, c)
    on_rate = on_n / n if n else None
    off5va_rate = off5va_n / n if n else None
    gap_pp = (off5va_rate - on_rate) * 100 if n else None

    out = {
        "run": str(run_dir),
        "audit_rate": args.audit_rate,
        "n_paired": n,
        "n_audited_common": n_audited,
        "audited_fraction": n_audited / n if n else None,
        "on_leaked": on_n, "off5va_leaked": off5va_n,
        "on_leak_rate": on_rate, "off5va_leak_rate": off5va_rate,
        "on_leak_rate_ci95": wilson(on_n, n) if n else None,
        "off5va_leak_rate_ci95": wilson(off5va_n, n) if n else None,
        "discordant_on_only": b, "discordant_off5va_only": c,
        "n_discordant": b + c,
        "mcnemar_exact_p_two_sided": p,
        "gap_pp_off5va_minus_on": gap_pp,
    }

    print(f"=== OFF5+同稽核(A) vs ON（配對 n={n}，其中 {n_audited} 題被同一顆 "
          f"hash 抽中稽核） ===")
    if n:
        print(f"ON      漏出 {on_n}/{n} = {100*on_rate:.2f}%")
        print(f"OFF5VA  漏出 {off5va_n}/{n} = {100*off5va_rate:.2f}%")
        print(f"discordant: 只有 ON 漏出 b={b}，只有 OFF5VA 漏出 c={c}")
        print(f"McNemar 精確雙尾 p = {p:.4f}")
        print(f"gap (OFF5VA - ON) = {gap_pp:.2f}pp")

    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
