#!/usr/bin/env python3
"""r445 八條事前預測（P-E1…P-E8）的收官判定。

CRITERION_20260903_R677_R445_PREDCHECK.md。**為什麼要有這支工具：**

`conform_settle.py` 印的 band 布林是 **r444 口徑**（round670 註冊的 P-C1…P-C5）：
`P-C1_band_3_to_6pp` 用 [3,6]pp，r445 註冊的 P-E1 是 **[0,+6]pp**；
`P-C2_le_2.0` 用 ≤2.0，r445 的 P-E4 是 **[1.2,1.6]**（Δ=+1.5pp 會被印成沒中，
c/task=1.05 會被印成通過——**一個假紅燈、一個假綠燈**）；
`_SETTLEMENT_TEXT` 還寫死了 `n=179`。r445 是 192（併庫 371）。
⇒ 「基準會過期」的第三種形狀：**尺沒改、素材沒改，改的是註冊的預測。**

**自我約束（判準 §二）：新增可調參數 0。** 本檔裡不准出現任何門檻數字——
每一條的 band 都是從 `DECISION_…R445….md` 的 `| P-E<k> |` 那一列，
用 `quote` 逐字定位、再從 quote 本身 parse 出來的。改動門檻的唯一辦法是改
DECISION（那會留下 commit）；quote 對不上就 BROKEN，不會安靜用舊值。

同理，數值一律**轉述**而不重算：Δ／配對數走 `conform_settle.settle()`，
併庫走 `pooled_paired_ci` 的 JSON 產物。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import conform_settle as _cs  # noqa: E402

DECISION_DEFAULT = "DECISION_20260903_R445_CONFORM_BANK_EXTENSION.md"

# 突變點（植入缺陷測試用，由 test_r445_predcheck_r677.py 設環境變數注入）。
# 正式路徑一律 None——`R445_PREDCHECK_MUTANT` 沒設就是 None。
MUTANT = os.environ.get("R445_PREDCHECK_MUTANT") or None


class Broken(Exception):
    pass


class NotEvaluated(Exception):
    """還沒有辦法判（例如併庫輸入尚未產生）。**與 BROKEN 分開**：
    BROKEN 是「該有的資料不見了」，NOT_EVALUATED 是「這一條還沒輪到」。
    兩者都不准算成通過；`--final` 之下兩者都讓 rc≠0（判準 Q7）。"""


# ── band 的形狀：每一種都從 quote 字串本身 parse，程式碼裡沒有數字 ──────────
def _nums(pat: str, quote: str, k: int) -> list[float]:
    m = re.search(pat, quote)
    if not m or len(m.groups()) != k:
        raise Broken(f"quote {quote!r} 解不出 {k} 個數字（pattern={pat}）")
    return [float(g.replace("+", "").strip()) for g in m.groups()]


def band_interval(quote: str):
    lo, hi = _nums(r"\[\s*([+-]?[\d.]+)\s*,\s*([+-]?[\d.]+)\s*\]", quote, 2)
    return {"kind": "interval", "lo": lo, "hi": hi,
            "test": lambda v: lo <= v <= hi, "desc": f"[{lo}, {hi}]"}


def band_le(quote: str):
    (hi,) = _nums(r"≤\s*([\d.]+)", quote, 1)
    return {"kind": "le", "hi": hi, "test": lambda v: v <= hi, "desc": f"≤ {hi}"}


def band_lt(quote: str):
    (hi,) = _nums(r"<\s*([\d.]+)", quote, 1)
    return {"kind": "lt", "hi": hi, "test": lambda v: v < hi, "desc": f"< {hi}"}


def band_dash(quote: str):
    lo, hi = _nums(r"([\d.]+)\s*[–—-]\s*([\d.]+)", quote, 2)
    return {"kind": "interval", "lo": lo, "hi": hi,
            "test": lambda v: lo <= v <= hi, "desc": f"{lo}–{hi}"}


def band_full_ratio(quote: str):
    a, b = _nums(r"([\d]+)\s*/\s*([\d]+)", quote, 2)
    if a != b:
        raise Broken(f"quote {quote!r} 的 x/y 不是滿分形式")
    return {"kind": "full_ratio", "n": a,
            "test": lambda v: v == a, "desc": f"== {a:.0f}/{a:.0f}"}


def band_gt_abort(quote: str):
    (thr,) = _nums(r">\s*([\d.]+)", quote, 1)
    return {"kind": "gt_abort", "thr": thr,
            "test": lambda v: v > thr, "desc": f"> {thr}"}


# ── 取值：一律轉述，不重算 ──────────────────────────────────────────────
def _arm(ctx, name):
    blk = ctx["settle"]["arms"].get(name)
    if blk is None:
        raise Broken(f"settle 結果沒有 {name!r} 臂（有的是 {sorted(ctx['settle']['arms'])}）"
                     f"——這不是通過，是量不到")
    return blk


def _pooled(ctx, path):
    if ctx["pooled"] is None:
        raise NotEvaluated("尚未提供併庫結果（--pooled-json，"
                           "由 pooled_paired_ci.py --key deliv 產生）")
    cur = ctx["pooled"]
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise Broken(f"併庫 JSON 缺 {path!r}——這不是通過，是量不到")
        cur = cur[part]
    return cur


def v_delta_pp(ctx):
    return ctx["settle"]["paired_test_vs_baseline"]["by"]["deliv"]["delta_pp"]


def v_pooled_halfwidth(ctx):
    lo = _pooled(ctx, "pooled.ci95_lo_pp")
    hi = _pooled(ctx, "pooled.ci95_hi_pp")
    return (hi - lo) / 2.0


def v_pooled_nd(ctx):
    return float(_pooled(ctx, "pooled.n_discordant"))


def v_conform_calls(ctx):
    return _arm(ctx, ctx["test_arm"])["calls_per_task_recomputed"]


def v_conform_refusal_pct(ctx):
    return 100.0 * _arm(ctx, ctx["test_arm"])["refusal_rate"]


def v_void_max_pct(ctx):
    """三臂 void 率的最大值：`各 <5%` ⇔ `max <5%`（不是新門檻，是同一句話）。"""
    return 100.0 * max(b["ratio"] for b in ctx["settle"]["void"].values())


def v_instrument_min(ctx):
    """量具雙向 + 可見閘門覆蓋，四個計數取最小；分母 n 另外硬比。"""
    ins = ctx["summary"].get("instrument")
    if not isinstance(ins, dict):
        raise Broken("summary.json 沒有 instrument 區塊——這不是通過，是量不到")
    need = ("n", "ref_pass", "broken_rejected",
            "visible_n", "visible_ref_pass", "visible_stub_rejected")
    miss = [f for f in need if ins.get(f) is None]
    if miss:
        raise Broken(f"summary.instrument 缺欄位 {miss}——這不是通過，是量不到")
    if ins["n"] != ins["visible_n"]:
        raise Broken(f"instrument.n={ins['n']} ≠ visible_n={ins['visible_n']}")
    return float(min(ins["ref_pass"], ins["broken_rejected"],
                     ins["visible_ref_pass"], ins["visible_stub_rejected"]))


def v_off_fail_pct(ctx):
    return 100.0 * (1.0 - _arm(ctx, ctx["third_arm"])["rate_deliv"])


# ── 八條的註冊表：quote 必須逐字出現在 DECISION 的該列 ────────────────────
SPEC = [
    {"id": "P-E1", "what": "新 192 題 Δdeliv(CONFORM−OFF5) 點估計 (pp)",
     "quote": "[0, +6]pp", "band": band_interval, "value": v_delta_pp},
    {"id": "P-E2", "what": "併 371 題 95%CI 半寬 (pp)",
     "quote": "半寬 ≤ 3.0pp", "band": band_le, "value": v_pooled_halfwidth},
    {"id": "P-E3", "what": "併 371 題 discordant 對數 n_d",
     "quote": "[20, 40]", "band": band_interval, "value": v_pooled_nd},
    {"id": "P-E4", "what": "新 192 題 CONFORM calls_per_task",
     "quote": "[1.2, 1.6]", "band": band_interval, "value": v_conform_calls,
     "abort_quote": ">4.5 中止", "abort_band": band_gt_abort},
    {"id": "P-E5", "what": "新 192 題 CONFORM 拒交率 (%)",
     "quote": "[3, 10]%", "band": band_interval, "value": v_conform_refusal_pct},
    {"id": "P-E6", "what": "三臂 infra_void 最大值 (%)",
     "quote": "<5%", "band": band_lt, "value": v_void_max_pct,
     "abort_quote": "任一臂 >20% 中止", "abort_band": band_gt_abort},
    {"id": "P-E7", "what": "量具雙向／可見閘門覆蓋（四個計數取最小）",
     "quote": "192/192", "band": band_full_ratio, "value": v_instrument_min},
    {"id": "P-E8", "what": "新 192 題 OFF 失敗率 (%)",
     "quote": "20–60%", "band": band_dash, "value": v_off_fail_pct},
]

if MUTANT == "M-QUOTE":      # 突變：把 P-E4 的門檻字面改寬（模擬「手打門檻」的漂移）
    for _s in SPEC:
        if _s["id"] == "P-E4":
            _s["quote"] = "[1.2, 1.9]"


# r444 口徑、對 r445 不適用的鍵（判準 Q8：要明講，不准安靜不提）
STALE_R444_KEYS = {
    "P-C1_band_3_to_6pp": "r444 的帶是 [3,6]pp；r445 註冊的 P-E1 是 [0,+6]pp",
    "P-C1b_band_0.02_to_0.20": "r444 的 p 值帶；r445 沒有註冊 p 值的帶",
    "P-C2_le_2.0": "r444 的門檻是 ≤2.0；r445 註冊的 P-E4 是 [1.2,1.6]（≤2.0 會給假綠燈）",
    "P-C1_settlement_rule": "文字寫死 n=179；r445 是 192（併庫 371），照抄會寫出字面錯誤的句子",
}


def load_decision_rows(path: pathlib.Path) -> dict[str, str]:
    if not path.exists():
        raise Broken(f"找不到 DECISION：{path}")
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*(P-E\d+)\s*\|", line)
        if m:
            rows[m.group(1)] = line
    return rows


def check(run_dir: pathlib.Path, rows_path: pathlib.Path, decision: pathlib.Path,
          pooled_json: pathlib.Path | None, test_arm: str, baseline: str,
          third: str) -> dict:
    dec_rows = load_decision_rows(decision)
    settled = _cs.settle(run_dir, rows_path, test_arm, baseline, third)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    pooled = (json.loads(pooled_json.read_text(encoding="utf-8"))
              if pooled_json else None)
    ctx = {"settle": settled, "summary": summary, "pooled": pooled,
           "test_arm": test_arm, "baseline": baseline, "third_arm": third}

    results, broken = [], []
    for spec in SPEC:
        r = {"id": spec["id"], "what": spec["what"], "quote": spec["quote"]}
        try:
            row = dec_rows.get(spec["id"])
            if row is None:
                # 安靜量不到・型一：DECISION 少了一列 ⇒ 不准跳過
                raise Broken(f"{decision.name} 裡找不到 | {spec['id']} | 那一列"
                             f"（找到的是 {sorted(dec_rows)}）")
            if spec["quote"] not in row:
                raise Broken(f"門檻字面 {spec['quote']!r} 不在 DECISION 的 {spec['id']} 列裡"
                             f"——工具與註冊的預測對不上，不准用舊值")
            band = spec["band"](spec["quote"])
            r["band"] = band["desc"]
            val = spec["value"](ctx)
            r["value"] = val
            hit = band["test"](val)
            if MUTANT == "M-DECOR":       # 突變：band 判定是裝飾品
                hit = True
            r["status"] = "HIT" if hit else "MISS"
            if spec.get("abort_quote"):
                if spec["abort_quote"] not in row:
                    raise Broken(f"中止線字面 {spec['abort_quote']!r} 不在 {spec['id']} 列裡")
                ab = spec["abort_band"](spec["abort_quote"])
                r["abort_rule"] = ab["desc"]
                r["abort_triggered"] = bool(ab["test"](val))
                if r["abort_triggered"]:
                    r["status"] = "ABORT_TRIGGERED"
        except NotEvaluated as e:
            r["status"] = "NOT_EVALUATED"
            r["why"] = str(e)
        except Broken as e:
            r["status"] = "BROKEN"
            r["why"] = str(e)
            broken.append(f"{spec['id']}: {e}")
        except Exception as e:                      # noqa: BLE001
            r["status"] = "BROKEN"
            r["why"] = f"{type(e).__name__}: {e}"
            broken.append(f"{spec['id']}: {type(e).__name__}: {e}")
        results.append(r)

    return {
        "run": str(run_dir), "decision": str(decision),
        "rows_sha256_8": settled["rows_sha256_8"], "n_rows": settled["n_rows"],
        "run_terminal": settled["run_terminal"],
        "pooled_json": str(pooled_json) if pooled_json else None,
        "predictions": results,
        "broken_reasons": broken,
        "n_hit": sum(1 for r in results if r["status"] == "HIT"),
        "n_miss": sum(1 for r in results if r["status"] == "MISS"),
        "n_abort": sum(1 for r in results if r["status"] == "ABORT_TRIGGERED"),
        "n_broken": len(broken),
        "n_not_evaluated": sum(1 for r in results if r["status"] == "NOT_EVALUATED"),
        "conform_settle_keys_NOT_APPLICABLE_TO_R445": STALE_R444_KEYS,
        "live_snapshot_skew": settled["live_snapshot_skew"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--rows", help="改讀這個 rows 快照；預設用 run 目錄裡的")
    ap.add_argument("--decision", default=DECISION_DEFAULT)
    ap.add_argument("--pooled-json", help="pooled_paired_ci.py --key deliv 的 --json 產物")
    ap.add_argument("--test-arm", default="CONFORM")
    ap.add_argument("--baseline", default="OFF5")
    ap.add_argument("--third", default="OFF")
    ap.add_argument("--final", action="store_true",
                    help="收官模式：run 必須 terminal，且八條都要判得出來，否則 rc≠0")
    ap.add_argument("--json")
    args = ap.parse_args()

    run_dir = pathlib.Path(args.run)
    rows_path = pathlib.Path(args.rows) if args.rows else run_dir / "rows.jsonl"
    try:
        out = check(run_dir, rows_path, pathlib.Path(args.decision),
                    pathlib.Path(args.pooled_json) if args.pooled_json else None,
                    args.test_arm, args.baseline, args.third)
    except _cs.Broken as e:
        print(f"BROKEN: {e}")
        return 2
    except Broken as e:
        print(f"BROKEN: {e}")
        return 2

    print(f"=== {out['run']}  rows={out['n_rows']} sha8={out['rows_sha256_8']} "
          f"terminal={out['run_terminal']} ===")
    print(f"門檻來源：{out['decision']}（每個數字都從該列的 quote parse，工具裡沒有門檻）")
    for r in out["predictions"]:
        val = r.get("value")
        vs = f"{val:>9.4f}" if isinstance(val, float) else f"{str(val):>9}"
        print(f"  {r['id']}  {r['status']:<16} 值={vs}  帶={r.get('band','—'):<14} "
              f"quote={r['quote']!r}")
        if r.get("abort_triggered") is not None:
            print(f"          中止線 {r['abort_rule']} ⇒ triggered={r['abort_triggered']}")
        if r.get("why"):
            print(f"          why: {r['why']}")
    print(f"  合計 HIT={out['n_hit']} MISS={out['n_miss']} ABORT={out['n_abort']} "
          f"NOT_EVALUATED={out['n_not_evaluated']} BROKEN={out['n_broken']}")
    print("  conform_settle 這些鍵對 r445 不適用（r444 口徑）：")
    for k, why in out["conform_settle_keys_NOT_APPLICABLE_TO_R445"].items():
        print(f"    {k}: {why}")

    rc = 0
    if out["n_broken"]:
        rc = 2
    if args.final:
        if not out["run_terminal"]:
            print("BROKEN: --final 但 run 還沒收官（terminal=false）")
            rc = max(rc, 1)
        if out["n_hit"] + out["n_miss"] + out["n_abort"] != len(SPEC):
            print(f"BROKEN: --final 但只判得出 "
                  f"{out['n_hit'] + out['n_miss'] + out['n_abort']}/{len(SPEC)} 條"
                  f"——收官不准帶著沒判的預測過關")
            rc = max(rc, 1)
    elif not out["run_terminal"]:
        print("WARNING: run 未收官 ⇒ 以上是中途快照，不是結論")

    if args.json:
        # round682：--json 的目標目錄不存在就建起來（round680 在 pool_precheck 修過的同一個坑：
        # 判決印對了、退出碼卻是 1，收官會讀成「尺壞了」）。不改任何輸出位元組。
        pathlib.Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.json).write_text(
            json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
