#!/usr/bin/env python3
"""真模型實驗（E10–E11）：用 LM Studio 上的實體模型跑，不是離線假腦。

E10  trust on / off 的配對對照：同一批任務、同一顆腦，唯一差異是信任層開關。
E11  記憶三臂 M0 / M1 / M2：同一批任務、同一顆腦，唯一差異是注入的記憶區塊。

紀律（CLAUDE.md 鐵律 1/3/4）：
  - 三臂 prompt 模板逐字相同，唯一差異是記憶區塊（`assert_ks1_clean` 是可執行防呆）。
  - **全 I/O 落 JSONL**：每次呼叫的 prompt、輸出、usage、耗時都留檔，不只留摘要。
  - retry×4、infra_void 不計票。
  - 記憶不跨臂共享（每臂各自新的 MemoryStream）。
  - 不對 reasoning 呼叫設 max_tokens 上限。

用法：
    python examples/realmodel_suite.py --out DIR \\
        --base http://100.119.113.56:1234 --model qwen/qwen3.6-35b-a3b \\
        --tasks 12 --only E10 E11
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vacant.auditor import Auditor  # noqa: E402
from vacant.batch import RunLedger  # noqa: E402
from vacant.brains import LMStudioBrain  # noqa: E402
from vacant.memory import MemoryManager, MemoryStream  # noqa: E402
from vacant.codebench import EvalPlusMBPPLoader  # noqa: E402
from vacant.x1 import make_pilot_tasks, run_x1, task_from_dict  # noqa: E402


def _load_tasks(source: str, n: int, seed: str):
    """任務來源。builtin 的三族對強模型會飽和（實測 3/3 全過，無鑑別力），
    正式量測一律用 EvalPlus MBPP+（sha256 釘死、V/GT 分離、fail-closed）。"""
    if source == "builtin":
        return make_pilot_tasks(n_per_family=max(1, n // 3))
    loader = EvalPlusMBPPLoader()
    rows = list(loader.iter_tasks(seed))[:n]
    return [task_from_dict(r) for r in rows]


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10,
                              cwd=Path(__file__).resolve().parent.parent).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "?"


def _body(ident):
    from vacant.identity import Identity
    from vacant.logbook import Logbook
    i = Identity.generate()
    lb = Logbook()
    lb.append("GENESIS", {"who": ident}, i, ts_ms=0)
    return i, lb


def _rate(records: list[dict]) -> tuple[int, int, float | None]:
    """(通過數, 有效題數, 通過率)。infra_void 不計票——分母要誠實。"""
    valid = [r for r in records if r.get("outcome") != "infra_void"]
    ok = sum(1 for r in valid if r.get("outcome") == "pass")
    return ok, len(valid), (round(ok / len(valid), 4) if valid else None)


def _make_distill(oracle_families: bool):
    """0 呼叫的確定性蒸餾：教訓由管線事實（任務描述＋稽核結論）生成。

    刻意不用模型蒸餾：模型蒸餾要 +1 呼叫（成本三倍），而且會把 A4
    （教訓只准坑型層級抽象、禁逐字測資）的風險從結構性保證降級成
    「靠 prompt 自律」。本 pilot 的處理變項是**注入什麼記憶**，不是
    「蒸餾器多聰明」，所以確定性蒸餾足夠且更乾淨。
    誠實邊界：這使 M2 的上限被蒸餾器的表達力限制住——它測不到
    「更好的蒸餾器會不會更有用」。
    """
    def distill(task, answer, audit_passed):
        head = " ".join(task.prompt.split())[:90]
        if audit_passed:
            return f"「{head}」型任務：先前交付通過稽核；同型解法可沿用。"
        return (f"「{head}」型任務：先前交付未通過稽核；重作同型任務前，"
                f"先列出空輸入、單一元素、邊界值三種情況的期望輸出再實作。")
    return distill


def E11_memory_arms(brain, tasks, out: Path, seed: str, *, use_oracle: bool) -> dict:
    """記憶三臂：M0 無記憶 / M1 原文 dump / M2 被審蒸餾。"""
    arms = {}
    for policy in ("M0", "M1", "M2"):
        armdir = out / "E11" / policy
        armdir.mkdir(parents=True, exist_ok=True)
        ident, lb = _body(f"E11-{policy}")
        stream = MemoryStream(lb, ident)          # 每臂各自的記憶，不跨臂共享
        t0 = time.time()
        records = run_x1(
            brain, policy, tasks,
            stream=stream,
            manager=MemoryManager(policy, budget_tokens=2000),
            auditor=Auditor(rate=1.0, seed=f"E11-{policy}-{seed}"),
            ledger=RunLedger(armdir / "ledger.jsonl"),
            seed=seed,
            oracle=use_oracle,                    # builtin 任務族才有 oracle 教訓
            distill=None if use_oracle else _make_distill(False),
            trace_path=armdir / "model_io.jsonl",  # 全 I/O 落盤
            retries=4,
        )
        (armdir / "records.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
            encoding="utf-8")
        ok, n, rate = _rate(records)
        voids = sum(1 for r in records if r.get("outcome") == "infra_void")
        arms[policy] = {"passed": ok, "valid": n, "pass_rate": rate,
                        "infra_void": voids, "elapsed_s": round(time.time() - t0, 1)}
        print(f"  {policy}: {ok}/{n} 通過"
              f"（{'—' if rate is None else f'{rate:.1%}'}）"
              f"，infra_void {voids}，耗時 {arms[policy]['elapsed_s']}s", flush=True)
    return {
        "question": "被審過的蒸餾記憶（M2）是否勝過原文記憶（M1）與無記憶（M0）？",
        "arms": arms,
        "note": "同一顆腦、同一批任務、模板逐字相同；唯一差異是注入的記憶區塊。"
                "這是 pilot 規模，**不足以支持任何效果宣稱**——它測的是「任務集"
                "有沒有可測的族內遷移」，不是「記憶有沒有用」。",
    }


def E10_trust_toggle(brain, tasks, out: Path, seed: str) -> dict:
    """trust on/off：同一批任務跑兩次，差別在信任層的路由與稽核是否生效。

    以 Ecosystem 跑真迴圈（路由→生成→互審→稽核→信譽回寫），trust off 時
    走確定性隨機路由、不注入記憶、不互審、不回寫。
    """
    from vacant.ecosystem import Ecosystem

    res = {}
    for on in (False, True):
        arm = "on" if on else "off"
        armdir = out / "E10" / arm
        armdir.mkdir(parents=True, exist_ok=True)
        eco = Ecosystem(armdir / "root", brain, root_mode="demo",
                        audit_rate=1.0, audit_seed=f"E10-{arm}-{seed}")
        eco.toggle(on)
        rows = []
        t0 = time.time()
        for i, t in enumerate(tasks):
            try:
                r = eco.delegate(t.prompt, t.check)
                card = r["trust_card"]
                rows.append({
                    "i": i, "task_id": r["task_id"], "arm": arm,
                    "passed": bool((card.get("audit") or {}).get("passed")),
                    "deliverer": card["deliverer"]["name"],
                    "credit": card["deliverer"]["credit"]["score"],
                    "reviews": len(card.get("reviews") or []),
                })
            except Exception as e:                # noqa: BLE001 — 如實記錄後續跑
                rows.append({"i": i, "arm": arm, "error": repr(e)[:200]})
            print(f"    [{arm}] {i + 1}/{len(tasks)}", end="\r", flush=True)
        (armdir / "rows.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
            encoding="utf-8")
        valid = [r for r in rows if "error" not in r]
        ok = sum(1 for r in valid if r["passed"])
        res[arm] = {"passed": ok, "valid": len(valid),
                    "pass_rate": round(ok / len(valid), 4) if valid else None,
                    "errors": len(rows) - len(valid),
                    "elapsed_s": round(time.time() - t0, 1),
                    "counters": eco.counters(), "cost": eco.cost()}
        print(f"  {arm}: {ok}/{len(valid)} 通過，耗時 {res[arm]['elapsed_s']}s", flush=True)
    return {
        "question": "同一批任務、同一顆腦，信任層開關造成的差別？",
        "arms": res,
        "note": "池化差，非同題配對統計；n 遠低於任何判準。"
                "這一支測的是**管線在真模型上跑得起來**，不是效果。",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--base", default="http://100.119.113.56:1234")
    ap.add_argument("--model", default="qwen/qwen3.6-35b-a3b")
    ap.add_argument("--api", default="responses", choices=["responses", "openai"])
    ap.add_argument("--tasks", type=int, default=12)
    ap.add_argument("--source", default="evalplus", choices=["evalplus", "builtin"])
    ap.add_argument("--seed", default="r1")
    ap.add_argument("--only", nargs="*", default=["E10", "E11"])
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    brain = LMStudioBrain(args.base, args.model, api=args.api,
                          timeout=600, max_tokens=None)   # reasoning：不設上限
    tasks = _load_tasks(args.source, args.tasks, args.seed)

    manifest = {
        "suite": "realmodel", "commit": _commit(),
        "started_iso": time.strftime("%Y-%m-%d %H:%M:%S"),
        "endpoint": args.base, "model": args.model, "api": args.api,
        "n_tasks": len(tasks), "task_source": args.source,
        "seed": args.seed, "experiments": args.only,
        "log_api": "http://100.119.113.56:8766/api/requests?include_bodies=true",
        "note": "本 run 的每次模型呼叫也會被中轉站監控 API 記錄，可交叉對帳。",
    }
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"任務數 {len(tasks)}｜模型 {args.model}｜端點 {args.base}", flush=True)

    results = {}
    if "E11" in args.only:
        print("\n=== E11 記憶三臂 ===", flush=True)
        results["E11"] = E11_memory_arms(brain, tasks, args.out, args.seed,
                                         use_oracle=(args.source == "builtin"))
        (args.out / "E11.json").write_text(
            json.dumps(results["E11"], ensure_ascii=False, indent=2), encoding="utf-8")
    if "E10" in args.only:
        print("\n=== E10 trust on/off ===", flush=True)
        results["E10"] = E10_trust_toggle(brain, tasks, args.out, args.seed)
        (args.out / "E10.json").write_text(
            json.dumps(results["E10"], ensure_ascii=False, indent=2), encoding="utf-8")

    (args.out / "summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成。全 I/O 在 {args.out}/E11/*/model_io.jsonl 與 {args.out}/E10/*/rows.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
