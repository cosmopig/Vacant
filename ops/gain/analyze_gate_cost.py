#!/usr/bin/env python3
"""把 ON 臂的「扣住不出貨」拆成閘門擋對的與閘門丟掉的（零 API 重放）。

為什麼可以零 API：`gain_run.py` 的 `truth = meets_demand(...)`（見該檔 1305 行）
是**無條件**算的，跟 `accepted` 無關。所以被扣住沒出貨的成品，rows.jsonl 裡
一樣帶著隱藏測資的真判決。這支工具只是重讀那個欄位，不重跑任何模型。

⚠ 「照樣出貨」不是同一個產品：不出貨爛程式碼正是 ON 宣稱要提供的東西。
本工具算的是**閘門的代價**，不是 ON 的增益。把 a 併進增益是作弊。
判準與推翻條件見 DECISION_20260903_R440U_GATE_COST_PREREG.md。
"""
import argparse
import json
import sys
from pathlib import Path


def load_rows(run: Path, arm: str, exclude: set[str]):
    rows = []
    for line in (run / "rows.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("arm") != arm:
            continue
        if r.get("task_id") in exclude:
            continue
        rows.append(r)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--arm", default="ON")
    ap.add_argument("--exclude-task-ids", default="",
                    help="逗號分隔；比照 R440T，分子分母同時移除")
    ap.add_argument("--min-measured", type=int, default=1,
                    help="量到的列數低於此值一律 BROKEN（防「安靜量不到」）")
    args = ap.parse_args()

    run = Path(args.run)
    exclude = {t for t in args.exclude_task_ids.split(",") if t.strip()}
    rows = load_rows(run, args.arm, exclude)

    if len(rows) < args.min_measured:
        print(f"BROKEN: {args.arm} 臂只量到 {len(rows)} 列 "
              f"(< --min-measured {args.min_measured})，可能是欄位名或臂名過期")
        return 2

    withheld = [r for r in rows if not r.get("accepted")]
    a = sum(1 for r in withheld if r.get("meets_demand"))
    b = len(withheld) - a
    delivered = [r for r in rows if r.get("accepted")]
    delivered_ok = sum(1 for r in delivered if r.get("meets_demand"))
    leaked = len(delivered) - delivered_ok
    all_ok = sum(1 for r in rows if r.get("meets_demand"))

    print(f"run={run}  arm={args.arm}")
    if exclude:
        print(f"排除 task_id：{sorted(exclude)}"
              f"（實際套用 {len({r for r in exclude})} 個，僅供對照，"
              f"不在 rows 裡的不會報錯）")
    print(f"落盤列數 n = {len(rows)}（不含 infra_void，那些根本沒進 rows）")
    print(f"  交付 (accepted=True)  = {len(delivered)}"
          f"    其中正確 = {delivered_ok}   漏出 leaked = {leaked}")
    print(f"  扣住 (accepted=False) = {len(withheld)}"
          f"    其中 a=閘門丟掉對的 = {a}   b=閘門擋對了 = {b}")
    print()
    print(f"  現行計分  correct_delivery_rate = {delivered_ok}/{len(rows)}"
          f" = {delivered_ok / len(rows):.4f}")
    print(f"  照樣出貨（反事實，非同一產品）= {all_ok}/{len(rows)}"
          f" = {all_ok / len(rows):.4f}")

    # ---- 守恆量：不成立一律 BROKEN，不准解讀 ----
    broken = []
    if a + b != len(withheld):
        broken.append(f"守恆1 失敗：a+b={a + b} != |W|={len(withheld)}")
    if delivered_ok + a != all_ok:
        broken.append(f"守恆3 失敗：delivered_ok+a={delivered_ok + a} "
                      f"!= 全體 meets_demand=True={all_ok}")
    summ = run / "summary.json"
    if summ.exists():
        s = json.loads(summ.read_text(encoding="utf-8"))
        arm_s = s.get("arms", {}).get(args.arm)
        if arm_s is not None and not exclude:
            if arm_s.get("accepted_and_meets_demand") != delivered_ok:
                broken.append(
                    f"守恆2 失敗：summary.accepted_and_meets_demand="
                    f"{arm_s.get('accepted_and_meets_demand')} != {delivered_ok}"
                    "（注意 summary 可能比 rows 晚幾列，收官時才是硬條件）")
            if arm_s.get("accepted") != len(delivered):
                broken.append(f"守恆2b 失敗：summary.accepted="
                              f"{arm_s.get('accepted')} != {len(delivered)}")
    if broken:
        print()
        for m in broken:
            print("BROKEN: " + m)
        return 2
    print("\n守恆量 1/2/3 全部成立。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
