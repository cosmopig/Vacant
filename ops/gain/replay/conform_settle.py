#!/usr/bin/env python3
"""r444（CONFORM 臂）的收官結算——算術照 `CRITERION_20260903_R667_CONFORM_SETTLEMENT_ARITHMETIC.md`。

零模型呼叫、零沙箱執行：只讀 rows.jsonl／notes.jsonl／summary.json 已落盤的欄位。

為什麼要獨立成一支（round667）：
  - `paired_gates.py:41` 把臂名寫死成 ("OFF","ON","OFF5") ⇒ CONFORM 被**安靜**濾掉。
  - `analyze_paired.py` 比的是 rows 的 `meets_demand`，而 `gain_run.py:516-520` 在
    CONFORM 拒交時仍把**沒出貨的**候選送去 hidden_check 計分 ⇒ 那一欄對 CONFORM 是
    原始正確率，不是交付率。P-C1 問的是交付。

三種算法一律並列印出，**但只有 deliv 結算 P-C1**（判準 §三）：
  deliv                 = accepted ∧ meets_demand，分母 = measured   （= summary 的 correct_delivery_rate）
  meets_demand only     = meets_demand，          分母 = measured     （= analyze_paired 用的量）
  demand_equals_output  = accepted ∧ meets_demand，分母 = accepted    （拒交會把它墊高）

任何一種「安靜量不到」都要翻成 BROKEN，不准回傳好看的數字：
  缺欄位／某臂零列／同臂 task_id 重複／欄位不是 bool／summary 與逐列覆算對不起來。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import sys

REQUIRED_ROW_FIELDS = ("arm", "task_id", "accepted", "meets_demand", "calls_used")


class Broken(Exception):
    """尺量不到就要叫，不能安靜給數字。"""


def exact_mcnemar_p(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    ctr = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, ctr - half), min(1.0, ctr + half))


def _bool(row: dict, field: str) -> bool:
    v = row[field]
    if not isinstance(v, bool):
        raise Broken(
            f"task {row.get('task_id')!r} 的 {field}={v!r} 型別是 {type(v).__name__} 不是 bool"
            f"（bool('False') 是 True，這種列不准安靜通過）")
    return v


def load_rows(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        raise Broken(f"找不到 {path}")
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not rows:
        raise Broken(f"{path} 是空的")
    for r in rows:
        missing = [f for f in REQUIRED_ROW_FIELDS if f not in r]
        if missing:
            raise Broken(f"列 task_id={r.get('task_id')!r} arm={r.get('arm')!r} 缺欄位 {missing}")
    return rows


def index_by_task(rows: list[dict], arm: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in rows:
        if r["arm"] != arm:
            continue
        t = r["task_id"]
        if t in out:
            raise Broken(f"{arm} 臂的 task_id={t!r} 出現兩次——字典會安靜蓋掉一筆")
        out[t] = r
    if not out:
        raise Broken(f"{arm} 臂一列都沒有")
    return out


def arm_block(idx: dict[str, dict]) -> dict:
    n = len(idx)
    acc = sum(1 for r in idx.values() if _bool(r, "accepted"))
    md = sum(1 for r in idx.values() if _bool(r, "meets_demand"))
    deliv = sum(1 for r in idx.values() if _bool(r, "accepted") and _bool(r, "meets_demand"))
    leaked = sum(1 for r in idx.values() if _bool(r, "accepted") and not _bool(r, "meets_demand"))
    md_not_acc = sum(1 for r in idx.values()
                     if _bool(r, "meets_demand") and not _bool(r, "accepted"))
    calls = sum(int(r["calls_used"]) for r in idx.values())
    return {
        "rows": n, "accepted": acc, "meets_demand": md, "deliv": deliv,
        "leaked": leaked, "meets_demand_and_not_accepted": md_not_acc,
        "refused": n - acc,
        "refusal_rate": (n - acc) / n,
        "rate_deliv": deliv / n,
        "rate_meets_demand": md / n,
        "rate_demand_equals_output": (deliv / acc) if acc else None,
        "calls_used_sum": calls,
        "calls_used_max": max(int(r["calls_used"]) for r in idx.values()),
        "calls_per_task_recomputed": calls / n,
    }


def paired(a: dict[str, dict], b: dict[str, dict], key) -> dict:
    common = sorted(set(a) & set(b))
    if not common:
        raise Broken("兩臂沒有共同的 task_id，配對分母是 0")
    ak = sum(1 for t in common if key(a[t]))
    bk = sum(1 for t in common if key(b[t]))
    disc_b = sum(1 for t in common if key(a[t]) and not key(b[t]))
    disc_c = sum(1 for t in common if key(b[t]) and not key(a[t]))
    return {
        "paired_n": len(common),
        "a_only_in_a": sorted(set(a) - set(b))[:5],
        "unpaired_a": len(set(a) - set(b)), "unpaired_b": len(set(b) - set(a)),
        "a_ok": ak, "b_ok": bk,
        "rate_a": ak / len(common), "rate_b": bk / len(common),
        "delta_pp": 100.0 * (ak - bk) / len(common),
        "b": disc_b, "c": disc_c, "p": exact_mcnemar_p(disc_b, disc_c),
    }


def void_block(notes: list[dict], arm: str, measured: int) -> dict:
    n_void = sum(1 for nt in notes if nt.get("arm") == arm and "infra_void" in nt)
    total = measured + n_void
    ratio = (n_void / total) if total else 0.0
    return {"n_measured": measured, "n_void": n_void, "ratio": ratio,
            "over_20pct_abort": ratio > 0.20, "over_10pct_warn": ratio > 0.10}


def settle(run_dir: pathlib.Path, rows_path: pathlib.Path, test_arm: str,
           baseline: str, third: str) -> dict:
    rows = load_rows(rows_path)
    summary_p = run_dir / "summary.json"
    if not summary_p.exists():
        raise Broken(f"找不到 {summary_p}")
    summary = json.loads(summary_p.read_text(encoding="utf-8"))
    notes_p = run_dir / "notes.jsonl"
    notes = ([json.loads(l) for l in notes_p.read_text(encoding="utf-8").splitlines() if l.strip()]
             if notes_p.exists() else [])

    arms = [a for a in (baseline, test_arm, third) if a]
    declared = list(summary.get("arms", {}))
    for a in arms:
        if a not in declared:
            raise Broken(f"summary.json 的 arms 沒有 {a!r}（有的是 {declared}）")
    idx = {a: index_by_task(rows, a) for a in arms}
    blocks = {a: arm_block(idx[a]) for a in arms}

    terminal = all(summary["arms"][a].get("terminal") for a in arms)

    # summary 與逐列覆算必須對得起來（P-C2 的獨立覆算）。
    # ⚠ 這條不變量**只在 run 靜止時成立**：跑到一半時 rows.jsonl 是逐格 append、
    #   summary.json 是每題重寫一次，快照必然差到一題。所以 terminal=False 時
    #   降級成「照實報 skew」，terminal=True 時（＝收官結算，唯一會被引用的那次）硬擋。
    skew = []

    def flag(msg: str) -> None:
        if terminal:
            raise Broken(msg)
        skew.append(msg)

    # round669：原本這裡對 `calls_per_task` 做 exact 比對並在 terminal 時硬擋。
    # **那條 exact equality 不被碼蘊含**（CRITERION_20260903_R669 §二）：
    #   `calls[0]` 逐格累加，`except InfraVoid` 只做 `n_void += 1; continue`，
    #   **不回捲**（gain_run.py:1329-1337），而 InfraVoid 由 `a.generate` 重試耗盡
    #   （brain_cline.py:246）或沙箱不可用（gain_run.py:133,277）丟出——OFF5／CONFORM
    #   是**依序**抽 k 份，第 5 份才炸的話前 4 次呼叫已經計進 `calls[0]` 卻沒有列。
    # ⇒ 只要 n_void>0，健康的 run 也會讓 summary.calls ≠ 逐列和 ⇒ 收官誤報 BROKEN。
    # 修法不是放寬，是**換成碼真正蘊含的不變量**，並補三條對 void 免疫的 exact 檢查。
    calls_check: dict[str, str] = {}
    for a in arms:
        sa, blk = summary["arms"][a], blocks[a]
        # `gain_run.py:1260-1280` 無條件寫出下列每一個欄位 ⇒ 少了任何一個就是
        # 「安靜量不到」，必須 BROKEN，不准當成 None 跳過（那會讓 M5 型的竄改溜走）。
        for field in ("infra_void", "calls", "processed",
                      "accepted", "accepted_and_meets_demand", "leaked"):
            if sa.get(field) is None:
                raise Broken(f"summary.json 的 {a} 臂沒有 {field} 欄位"
                             f"——這不是通過，是量不到")
        n_void = sa["infra_void"]
        # n_void 取自 summary，跟 `calls` 同一個產出者＝like-for-like；
        # notes 那份獨立計數另外報在 out["void"]（P-C5 用的就是它）。
        if not isinstance(n_void, int):
            raise Broken(f"summary.json 的 {a} 臂 infra_void={n_void!r} 不是整數")

        # (1) 對 void 免疫、且碼精確蘊含的 exact 檢查——牙齒在這裡，不准降級
        for field, recomputed in (("accepted", blk["accepted"]),
                                  ("accepted_and_meets_demand", blk["deliv"]),
                                  ("leaked", blk["leaked"])):
            if sa[field] != recomputed:
                flag(f"{a}.{field}：summary={sa[field]} vs 逐列覆算={recomputed}")

        # (2) processed == 列數 + n_void：抓「列不見了」。現行工具沒有這條。
        if sa["processed"] != blk["rows"] + n_void:
            flag(f"{a}.processed：summary={sa['processed']} vs 列數{blk['rows']}"
                 f"+void{n_void}={blk['rows'] + n_void}——有列不見了")

        # (3) calls：n_void==0 才 exact；n_void>0 換成碼蘊含的兩條界
        s_calls, rows_calls = sa["calls"], blk["calls_used_sum"]
        if n_void == 0:
            calls_check[a] = "exact"
            if s_calls != rows_calls:
                flag(f"{a}.calls：summary={s_calls} vs 逐列和={rows_calls}"
                     f"（n_void=0 ⇒ 必須逐位相同）")
        else:
            cap = blk["calls_used_max"]          # 單格上限由資料導出，零新旋鈕
            calls_check[a] = f"bounded(n_void={n_void},cap={cap})"
            excess = s_calls - rows_calls
            if excess < 0:
                flag(f"{a}.calls：summary={s_calls} < 逐列和={rows_calls}"
                     f"——void 只可能往上加，不可能扣掉")
            elif excess > n_void * cap:
                flag(f"{a}.calls：summary−逐列和={excess} 超過 {n_void} 個 void 格子"
                     f"最多可能吃掉的 {n_void}×{cap}={n_void * cap}")

    keys = {
        "deliv": lambda r: _bool(r, "accepted") and _bool(r, "meets_demand"),
        "meets_demand": lambda r: _bool(r, "meets_demand"),
    }
    pairs = {k: paired(idx[test_arm], idx[baseline], f) for k, f in keys.items()}

    out = {
        "run": str(run_dir), "rows_source": str(rows_path),
        "rows_sha256_8": hashlib.sha256(rows_path.read_bytes()).hexdigest()[:8],
        "n_rows": len(rows), "declared_n": summary.get("n"),
        "run_terminal": bool(terminal),
        "settlement_ready": bool(terminal),
        "arms": blocks,
        "paired_test_vs_baseline": {"test": test_arm, "baseline": baseline, **{"by": pairs}},
        "void": {a: void_block(notes, a, blocks[a]["rows"]) for a in arms},
        "live_snapshot_skew": skew,
        "calls_check_mode": calls_check,
    }

    # P-C1 只由 deliv 結算（判準 §三）
    d = pairs["deliv"]
    out["verdicts"] = {
        "P-C1_delta_pp": d["delta_pp"],
        "P-C1_band_3_to_6pp": (3.0 <= d["delta_pp"] <= 6.0),
        "P-C1b_p": d["p"], "P-C1b_band_0.02_to_0.20": (0.02 <= d["p"] <= 0.20),
        "P-C2_calls_per_task": blocks[test_arm]["calls_per_task_recomputed"],
        "P-C2_le_2.0": blocks[test_arm]["calls_per_task_recomputed"] <= 2.0,
        "P-C2_abort_gt_4.5": blocks[test_arm]["calls_per_task_recomputed"] > 4.5,
        "P-C3a_refusal_rate": blocks[test_arm]["refusal_rate"],
        "P-C3a_band_3_to_10pct": (0.03 <= blocks[test_arm]["refusal_rate"] <= 0.10),
        "P-C3b_leaked": {a: blocks[a]["leaked"] for a in arms},
        "P-C3b_verdict": "REPORTED_ONLY（R440R 未給門檻，判準 §三 降級）",
        "P-C4": "前半只看 receipt_head 齊備（round666）；鏈為 UNVERIFIABLE，不是中止條件",
        "P-C5_void_ratio": {a: out["void"][a]["ratio"] for a in arms},
        "P-C5_any_abort": any(out["void"][a]["over_20pct_abort"] for a in arms),
    }
    if not terminal:
        out["verdicts"]["WARNING"] = "run 未收官（terminal=false）⇒ 以上是中途快照，不是結論"
        out["verdicts"]["live_snapshot_skew"] = skew
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--rows", help="改讀這個 rows 檔（快照）；預設用 run 目錄裡的")
    ap.add_argument("--test-arm", default="CONFORM")
    ap.add_argument("--baseline", default="OFF5")
    ap.add_argument("--third", default="OFF")
    ap.add_argument("--json")
    args = ap.parse_args()

    run_dir = pathlib.Path(args.run)
    rows_path = pathlib.Path(args.rows) if args.rows else run_dir / "rows.jsonl"
    try:
        out = settle(run_dir, rows_path, args.test_arm, args.baseline, args.third)
    except Broken as e:
        print(f"BROKEN: {e}")
        if args.json:
            pathlib.Path(args.json).write_text(
                json.dumps({"status": "BROKEN", "reason": str(e)}, ensure_ascii=False, indent=2),
                encoding="utf-8")
        return 2

    b = out["arms"]
    print(f"=== {out['run']}  rows={out['n_rows']} sha8={out['rows_sha256_8']} "
          f"terminal={out['run_terminal']} ===")
    print(f"{'arm':9s} {'n':>4s} {'acc':>4s} {'refus':>6s} "
          f"{'deliv%':>8s} {'meets%':>8s} {'d=o%':>8s} {'leak':>5s} {'md&!acc':>8s} {'c/task':>7s}")
    for a, x in b.items():
        deo = "  n/a  " if x["rate_demand_equals_output"] is None else f"{100*x['rate_demand_equals_output']:7.2f}"
        print(f"{a:9s} {x['rows']:>4d} {x['accepted']:>4d} {x['refused']:>6d} "
              f"{100*x['rate_deliv']:>7.2f} {100*x['rate_meets_demand']:>7.2f} {deo:>8s} "
              f"{x['leaked']:>5d} {x['meets_demand_and_not_accepted']:>8d} "
              f"{x['calls_per_task_recomputed']:>7.2f}")
    for k, p in out["paired_test_vs_baseline"]["by"].items():
        mark = "  <= P-C1 用這個" if k == "deliv" else "  （analyze_paired 報的是這個）"
        print(f"paired[{k:12s}] n={p['paired_n']:>3d} Δ={p['delta_pp']:+6.2f}pp "
              f"b={p['b']:<3d} c={p['c']:<3d} p={p['p']:.4f}{mark}")
    print(f"calls 檢查層級：{out['calls_check_mode']}"
          "  （exact＝逐位相同；bounded＝該臂有 void，改用碼蘊含的上下界）")
    print(json.dumps(out["verdicts"], ensure_ascii=False, indent=2))
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
