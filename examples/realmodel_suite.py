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
    from vacant.memory import lesson_leaks_test_data

    def _headline(prompt: str) -> str:
        """取題目敘述的第一句，且**砍掉任何範例／斷言之後的內容**。

        EvalPlus 的題目敘述本身就內嵌 assert 範例（例如
        `assert sum_list([10,20,30],[15,25,35])==[25,45,65]`），逐字抄進教訓
        就是 A4 違規——實跑時 A4 防呆確實擋下並中止了整條臂。
        """
        text = " ".join(prompt.replace('"""', " ").split())
        for cut in ("assert ", "Example", "example:", ">>>"):
            i = text.find(cut)
            if i > 0:
                text = text[:i]
        return text.strip()[:80]

    def distill(task, answer, audit_passed):
        head = _headline(task.prompt)
        if audit_passed:
            lesson = f"「{head}」型任務：先前交付通過稽核；同型解法可沿用。"
        else:
            lesson = (f"「{head}」型任務：先前交付未通過稽核；重作同型任務前，"
                      f"先列出空輸入、單一元素、邊界值三種情況的期望輸出再實作。")
        # 蒸餾器自己先過 A4，不合格就降級為不含任何題目文字的通用教訓。
        # 讓防呆在寫入點才炸，等於一整夜的 run 會因為一題而全毀（實跑遇到過）。
        if lesson_leaks_test_data(lesson, task.check):
            return ("先前同類任務未通過稽核；重作前先列出空輸入、單一元素、"
                    "邊界值三種情況的期望輸出再實作。") if not audit_passed else None
        return lesson
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
    from vacant.checks import compile_check
    from vacant.ecosystem import Ecosystem

    res = {}
    for on in (False, True):
        arm = "on" if on else "off"
        armdir = out / "E10" / arm
        armdir.mkdir(parents=True, exist_ok=True)
        eco = Ecosystem(armdir / "root", brain, root_mode="demo",
                        audit_rate=1.0, audit_seed=f"E10-{arm}-{seed}")
        eco.toggle(on)
        # 斷點續跑：大 N 的跑動輒數小時，中斷不該從頭再來。
        # 以 (arm, i) 為鍵跳過已完成的格；未完成的照原順序補齊。
        rows_path = armdir / "rows.jsonl"
        done: dict[int, dict] = {}
        if rows_path.exists():
            for line in rows_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    done[r["i"]] = r
        rows = []
        t0 = time.time()
        for i, t in enumerate(tasks):
            if i in done:
                rows.append(done[i])
                continue
            try:
                r = eco.delegate(t.prompt, t.check)
                card = r["trust_card"]
                # **品質必須由臂外的檢查判定，不能讀信任狀的稽核欄。**
                # trust off 依設計就不稽核（audit.passed 恆為 None），照著讀會把
                # off 臂的每一筆都算成失敗，做出一個漂亮但完全虛假的組間差。
                # 這個錯誤在 2026-07-26 的實跑中真的發生過：off 臂顯示 0/11、
                # on 臂 5/10，而兩臂的答案其實一模一樣且都正確。
                passed = bool(compile_check(t.check)(r.get("answer", "")))
                rows.append({
                    "i": i, "task_id": r["task_id"], "arm": arm,
                    "passed": passed,
                    "audit_performed": bool((card.get("audit") or {}).get("performed")),
                    "deliverer": card["deliverer"]["name"],
                    "credit": card["deliverer"]["credit"]["score"],
                    "reviews": len(card.get("reviews") or []),
                })
            except Exception as e:                # noqa: BLE001 — 如實記錄後續跑
                rows.append({"i": i, "arm": arm, "error": repr(e)[:200]})
            print(f"    [{arm}] {i + 1}/{len(tasks)}", end="\r", flush=True)
            # 逐筆落盤（不是跑完才寫）——中斷時已完成的部分要留得住
            with rows_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rows[-1], ensure_ascii=False) + "\n")
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
    # ── 配對分析（兩臂跑的是同一批題目，所以配對檢定才是正確的分析）──
    from vacant.research import boot_ci, mcnemar_exact
    on_by_i = {r["i"]: r for r in _read_rows(out / "E10" / "on" / "rows.jsonl")
               if "error" not in r}
    off_by_i = {r["i"]: r for r in _read_rows(out / "E10" / "off" / "rows.jsonl")
                if "error" not in r}
    both = sorted(set(on_by_i) & set(off_by_i))
    pairs = [(bool(on_by_i[i]["passed"]), bool(off_by_i[i]["passed"])) for i in both]
    b = sum(1 for o, f in pairs if o and not f)      # on 過、off 沒過
    c = sum(1 for o, f in pairs if f and not o)      # off 過、on 沒過
    paired = None
    if pairs:
        deltas = [(1 if o else 0) - (1 if f else 0) for o, f in pairs]
        lo, hi = boot_ci(deltas, lambda s: sum(s) / len(s), n_boot=2000, seed=7)
        paired = {
            "n_pairs": len(pairs),
            "b_on_only": b, "c_off_only": c,
            "discordant": b + c,
            "delta": round(sum(deltas) / len(deltas), 4),
            "ci95": [round(lo, 4), round(hi, 4)],
            "mcnemar_p": round(mcnemar_exact(b, c), 4),
        }

    return {
        "question": "同一批任務、同一顆腦，信任層開關造成的差別？",
        "arms": res,
        "paired": paired,
        "note": "兩臂跑同一批題目，因此**配對檢定（McNemar）才是正確的分析**；"
                "arms 裡的通過率只是描述用。品質由臂外的檢查獨立判定，"
                "不讀信任狀的稽核欄（2026-07-26 的量測錯誤即由此而來）。"
                "生態使用 demo roster（含 2 個人工植入的 saboteur），"
                "所以這一支測的是「路由能不能避開被刻意做壞的代理」，"
                "**不是自然品質差異**——後者只由 X 系列承擔。",
    }


def _read_rows(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()
            if line.strip()]


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
