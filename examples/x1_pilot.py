"""X1 遷移 pilot 進入點（10 §4.2 一票否決 pilot；裁決 W1 並行項）。

用法（端點以 VACANT_ENDPOINT 或 --base 指定，不寫死機器 IP——G10）：
    VACANT_ENDPOINT=http://<vm-host>:1234 \
        python examples/x1_pilot.py --model qwen3.6-35b-a3b --arm M2 --oracle --seed s0

跑什麼：3 個任務族 × 17 題族內序列（~51 題）。--oracle 時每題稽核後直接把
該族的正確教訓寫入 episode（oracle-lesson 條件：連這樣都測不到遷移 → 任務集
重選，寫死在 10 §4.2）。三臂各跑一次（--arm M0/M1/M2，同 seed 配對）。

輸出：
  runs/x1_pilot/<arm>_<seed>.trace.jsonl   逐題全 I/O（06-30 稽核紀律）
  runs/x1_pilot/ledger.jsonl               斷點續跑帳本（重跑自動跳過）
結束時印每族的逐題通過序列（transfer_curve）——遷移判準的原料。
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from vacant.batch import RunLedger, Watchdog
from vacant.brains import LMStudioBrain
from vacant.identity import Identity
from vacant.logbook import Logbook
from vacant.memory import MemoryManager, MemoryStream
from vacant.x1 import make_pilot_tasks, run_x1, transfer_curve


def main() -> None:
    ap = argparse.ArgumentParser(description="X1 遷移 pilot（oracle-lesson 一票否決判準）")
    ap.add_argument("--base", default=os.environ.get("VACANT_ENDPOINT", "http://localhost:1234"))
    ap.add_argument("--model", default="qwen3.6-35b-a3b")
    ap.add_argument("--api", default="responses",
                    help="'responses'(/api/v1/chat，reasoning 模型) 或 'openai'(/v1)")
    ap.add_argument("--arm", choices=["M0", "M1", "M2"], default="M2")
    ap.add_argument("--seed", default="s0")
    ap.add_argument("--n-per-family", type=int, default=17)
    ap.add_argument("--budget", type=int, default=1500, help="M2 記憶預算（tokens）")
    ap.add_argument("--oracle", action="store_true", help="oracle-lesson 條件")
    ap.add_argument("--out", default="runs/x1_pilot")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    wd = Watchdog(args.base, on_down=lambda m: print(f"[watchdog] {m}"))
    if not wd.wait_alive(retries=3, interval=5):
        raise SystemExit(f"端點 {args.base} 不可用；先開 LM Studio 再跑")

    # 批次實驗不設 max_tokens 上限（裁決 B5：demo 才有界）——'responses' 路徑
    # 本就不送 max_tokens；timeout 拉到批次等級（單呼叫可達數分鐘，裁決 B1）。
    brain = LMStudioBrain(args.base, args.model, api=args.api, timeout=600)
    stream = MemoryStream(Logbook(), Identity.generate())  # 每臂新 stream（不跨臂共享）
    manager = MemoryManager(args.arm, budget_tokens=args.budget)
    tasks = make_pilot_tasks(args.n_per_family)

    print(f"X1 pilot：arm={args.arm} oracle={args.oracle} 共 {len(tasks)} 題 → {out}")
    records = run_x1(
        brain, args.arm, tasks,
        stream=stream, manager=manager,
        ledger=RunLedger(out / "ledger.jsonl"),
        seed=args.seed, oracle=args.oracle,
        trace_path=out / f"{args.arm}_{args.seed}.trace.jsonl",
    )

    curve = transfer_curve(records)
    n_ok = sum(1 for r in records if r["passed"])
    n_void = sum(1 for r in records if r["outcome"] == "infra_void")
    print(f"\n通過 {n_ok}/{len(records)}（infra_void {n_void}）")
    for fam, seq in curve.items():
        marks = "".join("✓" if x else "✗" for x in seq)
        head, tail = seq[: len(seq) // 2], seq[len(seq) // 2:]
        print(f"  {fam:12s} {marks}  前半 {sum(head)}/{len(head)} → 後半 {sum(tail)}/{len(tail)}")
    (out / f"summary_{args.arm}_{args.seed}.json").write_text(
        json.dumps({"arm": args.arm, "seed": args.seed, "oracle": args.oracle,
                    "curve": curve, "pass": n_ok, "total": len(records),
                    "infra_void": n_void}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
