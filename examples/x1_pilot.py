"""X1 遷移 pilot 進入點（10 §4.2 一票否決 pilot；17 §P1-3 合格證據包）。

用法（端點以 VACANT_ENDPOINT 或 --base 指定，不寫死機器 IP——G10）：
    VACANT_ENDPOINT=http://<vm-host>:1234 \
        python examples/x1_pilot.py --model qwen3.6-35b-a3b --arm M2 --oracle --seed s0

離線乾跑（工程閘門，無端點也產合格包）：
    python examples/x1_pilot.py --stub --arm M2 --oracle

跑什麼：任務來源三選一（--loader）——x1（內建 3 族 × 17 題，pilot v0 種子集）、
builtin（codebench 六坑型族程序生成）、evalplus（真 MBPP+ 378 題，G1 loader）。
--oracle 時每題稽核後直接把該族正確教訓寫入 episode（一票否決判準：連這樣都
測不到遷移 → 任務集重選，寫死在 10 §4.2）。三臂各跑一次（--arm M0/M1/M2）。

紀律（17 §P1-3）：
  - KS-1 模板 sha256 斷言、A4 教訓防呆結果全落盤（ks1_a4_assertions.jsonl）；
  - 正式跑加 --require-usage：缺端點 usage 的 trial 判 infra_void，不進分母；
  - 每條臂收尾 finalize_run_package → RECORD_SPEC 合格包（record check PASS），
    不 pack 的 run 視同沒跑過（紀錄紅線）。

輸出：runs/x1_pilot/<arm>_<seed>/ ＝ RECORD_SPEC 證據包＋summary.json。
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from vacant.batch import RunLedger, Watchdog
from vacant.identity import Identity
from vacant.logbook import Logbook
from vacant.memory import MemoryManager, MemoryStream
from vacant.x1 import (
    finalize_run_package,
    load_x1_tasks,
    make_pilot_tasks,
    pilot_report,
    run_x1,
)


class _StubBrain:  # noqa: D101 - 檔頭 docstring 已說明
    """離線乾跑腦：輪流回一對一錯（工程閘門用，產物形狀與真跑一致）。

    誠實標注：stub 數字是管線自驗，不是遷移證據——遷移判準只在真模型上成立。"""

    name = "stub:pilot-gate"

    def __init__(self, *, usage: dict | None = None):
        self.last_usage = usage
        self._i = 0

    def generate(self, prompt: str) -> str:
        self._i += 1
        if self._i % 2:
            return "def solve(*args):\n    return args[0] if args else None"
        return "def solve(*args):\n    return None  # 埋錯：讓 audit 有東西抓"


def _build_tasks(args):
    if args.loader == "x1":
        return make_pilot_tasks(args.n_per_family)
    if args.loader == "builtin":
        from vacant.codebench import BuiltinSampleLoader
        return load_x1_tasks(BuiltinSampleLoader(), args.seed, args.n)
    from vacant.codebench import EvalPlusMBPPLoader
    return load_x1_tasks(EvalPlusMBPPLoader(), args.seed, args.n)


def main() -> None:
    ap = argparse.ArgumentParser(description="X1 遷移 pilot（oracle-lesson 一票否決判準）")
    ap.add_argument("--base", default=os.environ.get("VACANT_ENDPOINT", "http://localhost:1234"))
    ap.add_argument("--model", default="qwen3.6-35b-a3b")
    ap.add_argument("--api", default="responses",
                    help="'responses'(/api/v1/chat，reasoning 模型) 或 'openai'(/v1)")
    ap.add_argument("--loader", choices=["x1", "builtin", "evalplus"], default="x1")
    ap.add_argument("--arm", choices=["M0", "M1", "M2"], default="M2")
    ap.add_argument("--seed", default="s0")
    ap.add_argument("--n-per-family", type=int, default=17)
    ap.add_argument("--n", type=int, default=51, help="loader=builtin/evalplus 時的題數")
    ap.add_argument("--budget", type=int, default=2000, help="M2 記憶預算（tokens，15 §1 B=2000）")
    ap.add_argument("--oracle", action="store_true", help="oracle-lesson 條件")
    ap.add_argument("--require-usage", action="store_true",
                    help="正式跑：缺端點 usage → infra_void（測量層紀律）")
    ap.add_argument("--stub", action="store_true", help="離線乾跑（工程閘門，非證據）")
    ap.add_argument("--out", default="runs/x1_pilot")
    args = ap.parse_args()

    run_dir = Path(args.out) / f"{args.arm}_{args.seed}"
    run_dir.mkdir(parents=True, exist_ok=True)

    if args.stub:
        brain = _StubBrain(usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    else:
        from vacant.brains import LMStudioBrain
        wd = Watchdog(args.base, on_down=lambda m: print(f"[watchdog] {m}"))
        if not wd.wait_alive(retries=3, interval=5):
            raise SystemExit(f"端點 {args.base} 不可用；先開 LM Studio 再跑")
        # 批次實驗不設 max_tokens 上限（R1／裁決 B5：demo 才有界）——'responses' 路徑
        # 本就不送 max_tokens；timeout 拉到批次等級（單呼叫可達數分鐘，裁決 B1）。
        brain = LMStudioBrain(args.base, args.model, api=args.api, timeout=600)

    tasks = _build_tasks(args)
    stream = MemoryStream(Logbook(), Identity.generate())  # 每臂新 stream（不跨臂共享）
    manager = MemoryManager(args.arm, budget_tokens=args.budget)
    trace = run_dir / "_trace.jsonl"

    print(f"X1 pilot：arm={args.arm} loader={args.loader} oracle={args.oracle} "
          f"共 {len(tasks)} 題 → {run_dir}")
    records = run_x1(
        brain, args.arm, tasks,
        stream=stream, manager=manager,
        ledger=RunLedger(run_dir / "_resume_ledger.jsonl"),
        seed=args.seed, oracle=args.oracle,
        trace_path=trace,
        require_usage=args.require_usage,
    )

    rep = pilot_report(records)
    n_ok = sum(1 for r in records if r["passed"])
    n_void = sum(1 for r in records if r["outcome"] == "infra_void")
    print(f"\n通過 {n_ok}/{len(records)}（infra_void {n_void}）")
    for fam, d in rep["per_family"].items():
        print(f"  {fam:12s} 前半 {d['front_pass']} → 後半 {d['back_pass']}  b={d['b']} c={d['c']} p={d['p']:.3g}")
    print(f"pooled b={rep['pooled']['b']} c={rep['pooled']['c']} p={rep['pooled']['p']:.3g}"
          f" → {rep['verdict']}")

    ok, problems = finalize_run_package(
        run_dir, policy=args.arm, stream=stream, tasks=tasks, records=records,
        trace_path=trace,
        extra_meta={
            "model_id": getattr(brain, "name", "unknown"),
            "endpoint": ("stub" if args.stub else args.base),
            "no_think": False, "seeds": [args.seed], "trust_arm": args.arm,
            "scripts": [str(Path(__file__).resolve())],
        },
    )
    (run_dir / "summary.json").write_text(
        json.dumps({"arm": args.arm, "seed": args.seed, "oracle": args.oracle,
                    "loader": args.loader, "stub": args.stub,
                    "pass": n_ok, "total": len(records), "infra_void": n_void,
                    "pilot_report": rep, "record_check_ok": ok,
                    "record_check_problems": problems},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"record check：{'PASS' if ok else 'FAIL — ' + '; '.join(problems)}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
