"""B 層機制驗收六情境 runner（13 §3；17 §P4；15 §2 畢業軌必要項）。

正式掃描（每格 ≥1000 seeds，六情境 × 8 格 × on/off）：
    python examples/b_layer.py --out ~/Library/Mobile\ Documents/com~apple~CloudDocs/專題/實驗記錄/驗收_B層/

快速 smoke（開發用，數字不作歸檔）：
    python examples/b_layer.py --smoke

產出：cells.jsonl（每格 value＋bootstrap 95% CI）＋ summary.md（一頁結果）。
判準全部事前寫死在 vacant/blayer.py 的 `_verdict`；「拆掉數字沒變」＝裝飾、
從一切主張移除（13 §3）。誠實邊界：這是確定性離線機制驗收，不是生態效果
宣稱（效果屬 X 系列、C-3 門後）。
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from vacant.blayer import DEFAULT_N_SEEDS, SCENARIOS, run_all


def main() -> None:
    ap = argparse.ArgumentParser(description="B 層機制驗收六情境")
    ap.add_argument("--n-seeds", type=int, default=DEFAULT_N_SEEDS)
    ap.add_argument("--smoke", action="store_true", help="每格 16 seeds 快速掃描")
    ap.add_argument("--base-seed", default="blayer-v1")
    ap.add_argument("--out", default=None, help="歸檔目錄（cells.jsonl＋summary.md）")
    ap.add_argument("--only", nargs="*", choices=sorted(SCENARIOS), default=None)
    args = ap.parse_args()

    n = 16 if args.smoke else args.n_seeds
    t0 = time.time()
    reports = run_all(n_seeds=n, base_seed=args.base_seed,
                      out_dir=args.out, only=tuple(args.only) if args.only else None)
    ok = True
    print(f"B 層六情境（每格 {n} seeds，耗時 {time.time() - t0:.0f}s）")
    for name, rep in reports.items():
        print(f"  {'✅' if rep.verdict else '❌'} {name:22s} {rep.detail}")
        ok = ok and rep.verdict
    print(f"總判：{'全過 ✅' if ok else '有失敗 ❌——對應機制依 13 §3 降級為裝飾、從主張移除'}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
