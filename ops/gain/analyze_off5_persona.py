"""OFF5 逐 persona 品質分析——round61 前瞻性推翻條件的量測工具。

round61（`DECISION_20260824_NO_RANDOM_ROUTING_ARM.md`）裁決不開
ON-random-routing 臂，但留了一個前瞻性推翻條件：OFF5 跑滿後累積 ~300 次
均勻抽籤（每 persona ~50 次），若**逐 persona 品質離散度 Fisher p<0.05
且最好最差差 ≥15pp**，這個決定要被推翻（開新臂才有意義）。

⚠ 這條量測不能用 `rows.jsonl` 裡 OFF5 那題的 `meets_demand`——那一欄是
  **5 份候選碼經行為簽名多數決之後、被選中那一份**的隱藏測資結果，已經被
  選版邏輯混合過，不是「該 persona 自己交的稿子」的品質。round61 講的
  「逐 persona 品質」要用**每一份候選碼各自**的隱藏測資結果，5 份都要獨立
  判，不能只看誰中選。

做法：從 `calls.jsonl` 撈出每一通 `role=gen, meta.arm=OFF5` 的呼叫（含
`agent_id` 與回應全文），用跟 `gain_run.arm_off5` 完全一樣的 `extract_code`
挖出候選碼，再用 `load_tasks` 重建同一份題目序列（同 seed/bank/n）取得
`hidden_check`／`entry_point`，逐份跑 `meets_demand`。這是**唯讀重算**，
不碰 run 目錄任何既有檔案，也不重新呼叫模型端點。

用法：
    python3 ops/gain/analyze_off5_persona.py \
        --run runs/g_onoff5_qwenonly_v3_20260824 \
        --seed g-smoke-20260820 --n 60 \
        [--json-out /dev/shm/off5_persona.json]

樣本不足（<10 通/persona）時只印警告不擋輸出——round62 交接時 OFF5 才
8/60 題，本工具刻意設計成能在資料還沒跑滿時先跑、先看初步形狀。
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.gain.analyze_routing_mix import fisher_exact_two_sided  # noqa: E402
from ops.gain.gain_run import extract_code, load_tasks, meets_demand  # noqa: E402


def collect(run_dir: pathlib.Path, seed: str, n: int) -> dict:
    calls_path = run_dir / "calls.jsonl"
    if not calls_path.exists():
        raise SystemExit(f"找不到 {calls_path}")

    tasks_by_id = {t["task_id"]: t for t in load_tasks("evalplus", seed, n)}

    gen_calls = []
    for line in calls_path.open(encoding="utf-8"):
        if not line.strip():
            continue
        c = json.loads(line)
        meta = c.get("meta") or {}
        if c.get("role") == "gen" and meta.get("arm") == "OFF5":
            gen_calls.append(c)

    per_agent: dict[str, dict] = collections.defaultdict(lambda: {"n": 0, "ok": 0})
    per_task: dict[str, list] = collections.defaultdict(list)
    skipped_unknown_task = 0
    skipped_failed_call = 0
    for c in gen_calls:
        if not c.get("ok"):
            # 重試中失敗的呼叫沒有 response（有 error）——不是這個 persona
            # 交的稿子，是端點層失敗，略過並算清楚跳了幾筆。
            skipped_failed_call += 1
            continue
        task_id = c["meta"]["task_id"]
        task = tasks_by_id.get(task_id)
        if task is None:
            # 題目不在這次重建的序列裡（seed/n 對不上）——不要用錯的 hidden_check
            # 硬判，寧可跳過並算清楚跳了幾筆。
            skipped_unknown_task += 1
            continue
        code = extract_code(c["response"])
        ok, err = meets_demand(
            code, task["hidden_check"]["code"], entry_point=task.get("entry_point"))
        agent_id = c["agent_id"]
        per_agent[agent_id]["n"] += 1
        per_agent[agent_id]["ok"] += int(ok)
        per_task[task_id].append({"agent_id": agent_id, "ok": ok, "err": err})

    for s in per_agent.values():
        s["rate"] = s["ok"] / s["n"] if s["n"] else None

    agents = sorted(per_agent)
    usable = [a for a in agents if per_agent[a]["n"] > 0]
    spread = {"worst_agent": None}
    if usable:
        worst = min(usable, key=lambda a: per_agent[a]["ok"] / per_agent[a]["n"])
        best = max(usable, key=lambda a: per_agent[a]["ok"] / per_agent[a]["n"])
        w, b = per_agent[worst], per_agent[best]
        rest_ok = sum(per_agent[a]["ok"] for a in usable if a != worst)
        rest_n = sum(per_agent[a]["n"] for a in usable if a != worst)
        spread = {
            "worst_agent": worst,
            "worst": f"{w['ok']}/{w['n']}",
            "worst_rate": w["ok"] / w["n"],
            "best_agent": best,
            "best": f"{b['ok']}/{b['n']}",
            "best_rate": b["ok"] / b["n"],
            "best_minus_worst_pp": (b["ok"] / b["n"] - w["ok"] / w["n"]) * 100.0,
            "rest": f"{rest_ok}/{rest_n}",
            "rest_rate": rest_ok / rest_n if rest_n else None,
            "fisher_two_sided_p_worst_vs_rest": fisher_exact_two_sided(
                w["ok"], w["n"] - w["ok"], rest_ok, rest_n - rest_ok),
        }

    total_n = sum(per_agent[a]["n"] for a in agents)
    min_n_per_agent = min((per_agent[a]["n"] for a in usable), default=0)
    round61_condition_met = bool(
        spread.get("worst_agent")
        and spread["fisher_two_sided_p_worst_vs_rest"] < 0.05
        and spread["best_minus_worst_pp"] >= 15.0
    )

    return {
        "run_dir": str(run_dir),
        "seed": seed,
        "n_tasks_requested": n,
        "off5_gen_calls_total": len(gen_calls),
        "off5_gen_calls_scored": total_n,
        "skipped_unknown_task": skipped_unknown_task,
        "skipped_failed_call": skipped_failed_call,
        "tasks_covered": len(per_task),
        "min_n_per_agent": min_n_per_agent,
        "sample_adequate": min_n_per_agent >= 10,
        "per_agent": {a: per_agent[a] for a in agents},
        "per_task": dict(per_task),
        "persona_spread": spread,
        "round61_reversal_condition_met": round61_condition_met,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=pathlib.Path)
    ap.add_argument("--seed", required=True)
    ap.add_argument("--n", required=True, type=int)
    ap.add_argument("--json-out", type=pathlib.Path, default=None)
    args = ap.parse_args()

    res = collect(args.run, args.seed, args.n)

    print("== OFF5 逐 persona 品質（每份候選碼各自的隱藏測資結果，非多數決結果）==")
    print(f"gen 呼叫共 {res['off5_gen_calls_total']} 通，"
          f"可判 {res['off5_gen_calls_scored']} 通（跳過未知題 {res['skipped_unknown_task']} 通、"
          f"跳過失敗呼叫 {res['skipped_failed_call']} 通），"
          f"涵蓋 {res['tasks_covered']} 題")
    if not res["sample_adequate"]:
        print(f"⚠ 樣本仍薄：min n/persona = {res['min_n_per_agent']}（<10），"
              f"以下數字只是初步形狀，不要拿來判 round61 推翻條件")
    for a, s in res["per_agent"].items():
        rate = f"{s['rate']:.0%}" if s["n"] else "n/a"
        print(f"  {a:10s} {s['ok']}/{s['n']} {rate}")

    sp = res["persona_spread"]
    if sp.get("worst_agent"):
        print(f"\n最差 {sp['worst_agent']}: {sp['worst']} ({sp['worst_rate']:.0%})  "
              f"最好 {sp['best_agent']}: {sp['best']} ({sp['best_rate']:.0%})  "
              f"差 {sp['best_minus_worst_pp']:+.2f}pp")
        print(f"最差 vs 其餘 Fisher 雙尾 p={sp['fisher_two_sided_p_worst_vs_rest']:.4f}")

    print(f"\nround61 前瞻性推翻條件（Fisher p<0.05 且最好最差差 ≥15pp）："
          f"{'✓ 已達成，需要重新判斷是否開新臂' if res['round61_reversal_condition_met'] else '✗ 尚未達成'}")

    if args.json_out:
        args.json_out.write_text(json.dumps(res, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        print(f"\nJSON ⇒ {args.json_out}")


if __name__ == "__main__":
    main()
