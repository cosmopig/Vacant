"""round438：round437 留下的延伸方向 3——難題子集分析。

為什麼要做這個（見 DECISION_20260901_R437_DECISIVE_RUN_COMPLETE_FINAL.md
「下一輪該做什麼」第 3 點）：全題庫等預算配對分析（ON vs OFF5）在完整
179 題資料上不顯著（typing 修正版 p=0.45），但「簡單題兩臂都接近 100%」
會稀釋掉任何真實效應——天花板效應。如果 Vacant 的 review+revise 機制真的
有用，最可能在「OFF 本身會答錯」的難題子集上顯現，因為那裡兩臂才有
真正的區分空間。

零成本：不打模型，離線重放 `runs/g_r356_3arm_20260830` 已收集的
calls.jsonl，用跟 round393 一樣的 typing 白名單修正邏輯重算三臂在
hidden_check 上的 truth（邏輯抄自 reanalyze_typing_fix_r393.py，因為那支
是一次性腳本沒有可 import 的函式，這裡重寫一份自包含的版本，避免動到
已經被引用穩定的舊腳本）。

難題子集定義（**先於量測寫死，不看數字挑**）：task_id 落在
OFF 臂 typing 修正版 new_truth == False 的集合——也就是「就算不用
Vacant、也不用 self-consistency 多數決，模型單發答案在 hidden_check 上
仍然是錯的」那批題。這個定義只依賴 OFF 臂（最便宜、無審查機制），不依賴
ON/OFF5 自己的結果，所以不會有「用結果去定義子集」的循環論證問題。

在這個子集上，對 ON vs OFF5 重跑跟 analyze_paired.py 相同的 McNemar 精確
配對檢定（複製那支工具的 exact_mcnemar_p/wilson 實作，避免額外相依）。

用法：
    cd ~/vacant/Vacant && VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz \
        python3 ops/gain/analyze_hard_subset.py [--json OUT]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import pathlib
import sys

os.environ.setdefault("VACANT_EVALPLUS_PATH", ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
os.chdir(str(pathlib.Path(__file__).resolve().parents[2]))

from ops.gain.gain_run import load_tasks, extract_code, behavior_signature, _GAIN_ALLOWED_IMPORTS
from vacant.checks import CheckInfraError, run_python_check

RUN = pathlib.Path("runs/g_r356_3arm_20260830")
OLD_IMPORTS = ("bisect", "cmath", "collections", "functools", "heapq", "itertools", "math", "operator", "re", "sys")


def meets_demand_with(code, check_code, entry_point, imports):
    try:
        return run_python_check(code, check_code, timeout=10, allowed_imports=imports,
                                 allowed_entry_points=(entry_point,) if entry_point else ())
    except CheckInfraError:
        return None


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


def load_by_task(calls):
    by_task = {}
    for c in calls:
        m = c.get("meta") or {}
        tid = m.get("task_id")
        if not tid:
            continue
        by_task.setdefault(tid, []).append(c)
    return by_task


def get_code(by_task, tid, arm, role, phase=None):
    out = []
    for c in by_task.get(tid, []):
        m = c.get("meta") or {}
        if m.get("arm") != arm or c.get("role") != role:
            continue
        if phase is not None and m.get("phase") != phase:
            continue
        if c.get("ok") is not True:
            continue
        out.append(extract_code(c.get("response", "")))
    return out


def compute_typing_fixed_truth() -> dict:
    """回傳 {arm: {task_id: bool_or_None}}，None = 這題這臂在原始資料裡沒有
    可重放的候選碼（跳過，不計入任何分母）。"""
    rows = [json.loads(l) for l in (RUN / "rows.jsonl").open() if l.strip()]
    calls = [json.loads(l) for l in (RUN / "calls.jsonl").open() if l.strip()]
    tasks = {t["task_id"]: t for t in load_tasks("evalplus", "g-r212-route-20260828", 179)}
    by_task = load_by_task(calls)

    out = {"OFF": {}, "ON": {}, "OFF5": {}}
    for r in rows:
        arm = r.get("arm")
        tid = r.get("task_id")
        if arm not in out or tid not in tasks:
            continue
        t = tasks[tid]
        ep = t.get("entry_point")
        old_truth = r.get("meets_demand")
        if old_truth is None:
            continue

        if arm == "OFF":
            codes = get_code(by_task, tid, "OFF", "gen")
            if not codes:
                continue
            code = codes[0]
            new_truth = meets_demand_with(code, t["hidden_check"]["code"], ep, _GAIN_ALLOWED_IMPORTS)
            out["OFF"][tid] = new_truth

        elif arm == "ON":
            init_codes = get_code(by_task, tid, "ON", "gen", phase="initial")
            rev_codes = get_code(by_task, tid, "ON", "revise", phase="revision")
            if not init_codes or not rev_codes:
                continue
            initial_code, revised_code = init_codes[0], rev_codes[0]
            passed_review = r.get("passed_review")
            iv_new = meets_demand_with(initial_code, t["visible_check"]["code"], ep, _GAIN_ALLOWED_IMPORTS)
            rv_new = meets_demand_with(revised_code, t["visible_check"]["code"], ep, _GAIN_ALLOWED_IMPORTS)
            if passed_review and iv_new:
                sel_new, vis_new = "initial", iv_new
            elif rv_new:
                sel_new, vis_new = "revised", rv_new
            elif iv_new:
                sel_new, vis_new = "initial_fallback", iv_new
            else:
                sel_new, vis_new = "revised_both_visible_fail", rv_new
            code_new = initial_code if sel_new.startswith("initial") else revised_code
            h = int(hashlib.sha256(f"audit:{tid}".encode()).hexdigest()[:8], 16)
            audited = (h / 0xFFFFFFFF) < 0.2
            audit_ok_new = None
            if audited:
                audit_ok_new = meets_demand_with(code_new, t["hidden_check"]["code"], ep, _GAIN_ALLOWED_IMPORTS)
            accepted_new = bool(vis_new) and (audit_ok_new is not False)
            if not accepted_new:
                out["ON"][tid] = False
            else:
                out["ON"][tid] = meets_demand_with(code_new, t["hidden_check"]["code"], ep, _GAIN_ALLOWED_IMPORTS)

        elif arm == "OFF5":
            gen_codes = get_code(by_task, tid, "OFF5", "gen")
            if len(gen_codes) < 5:
                continue
            import ops.gain.gain_run as gr
            old_global = gr._GAIN_ALLOWED_IMPORTS
            gr._GAIN_ALLOWED_IMPORTS = OLD_IMPORTS
            buckets = {}
            for c in gen_codes:
                try:
                    sig = behavior_signature(c, t)
                except Exception:
                    sig = "EXEC_FAIL"
                buckets.setdefault(sig, []).append(c)
            gr._GAIN_ALLOWED_IMPORTS = old_global
            max_votes = max(len(v) for v in buckets.values())
            tied = [v for v in buckets.values() if len(v) == max_votes]
            win = tied[0]
            code = win[0]
            out["OFF5"][tid] = meets_demand_with(code, t["hidden_check"]["code"], ep, _GAIN_ALLOWED_IMPORTS)

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="把結果寫成 JSON 到這個檔")
    args = ap.parse_args()

    truth = compute_typing_fixed_truth()

    hard_subset = sorted(tid for tid, v in truth["OFF"].items() if v is False)
    print(f"難題子集定義：OFF 臂 typing 修正版 new_truth==False 的題目")
    print(f"OFF 臂可重放題數 = {len(truth['OFF'])}，難題子集大小 = {len(hard_subset)}"
          f"（{100*len(hard_subset)/len(truth['OFF']):.1f}%）")
    print()

    common = sorted(set(hard_subset) & set(truth["ON"]) & set(truth["OFF5"]))
    a_ok = sum(1 for t in common if truth["ON"][t])
    b_ok = sum(1 for t in common if truth["OFF5"][t])
    disc_b = sum(1 for t in common if truth["ON"][t] and not truth["OFF5"][t])
    disc_c = sum(1 for t in common if truth["OFF5"][t] and not truth["ON"][t])
    p = exact_mcnemar_p(disc_b, disc_c)

    print(f"難題子集上 ON vs OFF5（n_paired = {len(common)}）")
    if common:
        print(f"ON    需求=產出  {a_ok}/{len(common)} = {100*a_ok/len(common):.2f}%"
              f"  CI95 {tuple(round(100*x,1) for x in wilson(a_ok, len(common)))}")
        print(f"OFF5  需求=產出  {b_ok}/{len(common)} = {100*b_ok/len(common):.2f}%"
              f"  CI95 {tuple(round(100*x,1) for x in wilson(b_ok, len(common)))}")
        print(f"discordant：只有 ON 對 b={disc_b}，只有 OFF5 對 c={disc_c}"
              f"（證據單位 = {disc_b + disc_c}）")
        print(f"McNemar 精確雙尾 p = {p:.4f}")
    else:
        print("n_paired=0，無法檢定。")

    out = {
        "hard_subset_definition": "OFF arm typing-fixed new_truth == False (hidden_check)",
        "off_replayable_n": len(truth["OFF"]),
        "hard_subset_n": len(hard_subset),
        "hard_subset_task_ids": hard_subset,
        "n_paired": len(common),
        "on_ok": a_ok,
        "off5_ok": b_ok,
        "on_rate": a_ok / len(common) if common else None,
        "off5_rate": b_ok / len(common) if common else None,
        "discordant_on_only": disc_b,
        "discordant_off5_only": disc_c,
        "mcnemar_exact_p_two_sided": p if common else None,
    }
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
