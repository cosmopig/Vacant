"""round393：離線重放 `runs/g_r356_3arm_20260830` 已收集的 calls.jsonl，
量「typing 白名單漏洞」修好之後每個 arm 的需求=產出結果會不會翻盤。

不重跑任何模型呼叫（零成本）——OFF/ON 直接用已落盤的候選碼重跑 sandbox；
OFF5 用**同一套多數決規則**（behavior_signature 對舊白名單）重建當時的
winning bucket 再取樣一個代表，這一步是近似（tie 內若有多個不同程式碼，
不保證選到跟原跑一樣那份），已用「用舊白名單重放能不能重現 old_truth」
自我檢查過：88 題裡 87 題吻合（1 題不吻合，見腳本內建的 sanity check 區塊）。

發現：`_GAIN_ALLOWED_IMPORTS` 沒有 `typing`，而它是零副作用的型別標註模組。
ON 的視覺檢查失敗有 6/7（86%）是這個白名單擋下、不是邏輯錯誤；OFF 是
2/7（29%），OFF5 是 2/6（33%）——ON 只有 initial+revision 兩次真正機會，
OFF5 有 5 個獨立樣本多數決，天然稀釋同一個漏洞的命中率。細節見
`ops/gain/DECISION_20260831_R393_TYPING_IMPORT_WHITELIST_BUG.md`。

用法：`cd ~/vacant/Vacant && VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz python3 ops/gain/reanalyze_typing_fix_r393.py`
"""
import json, pathlib, sys
import os
os.environ.setdefault("VACANT_EVALPLUS_PATH", ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
os.chdir(str(pathlib.Path(__file__).resolve().parents[2]))

from ops.gain.gain_run import load_tasks, meets_demand, extract_code, behavior_signature, _GAIN_ALLOWED_IMPORTS
import hashlib

RUN = pathlib.Path("runs/g_r356_3arm_20260830")
rows = [json.loads(l) for l in (RUN/"rows.jsonl").open() if l.strip()]
calls = [json.loads(l) for l in (RUN/"calls.jsonl").open() if l.strip()]
tasks = {t["task_id"]: t for t in load_tasks("evalplus", "g-r212-route-20260828", 179)}

OLD_IMPORTS = ("bisect", "cmath", "collections", "functools", "heapq", "itertools", "math", "operator", "re", "sys")
assert set(_GAIN_ALLOWED_IMPORTS) == set(OLD_IMPORTS) | {"typing"}, "gain_run.py 現在應已含 typing"

def meets_demand_with(code, check_code, entry_point, imports):
    from vacant.checks import CheckInfraError, run_python_check
    try:
        return run_python_check(code, check_code, timeout=10, allowed_imports=imports,
                                 allowed_entry_points=(entry_point,) if entry_point else ())
    except CheckInfraError:
        return None

by_task = {}
for c in calls:
    m = c.get("meta") or {}
    tid = m.get("task_id")
    if not tid: continue
    by_task.setdefault(tid, []).append(c)

def get_code(tid, arm, role, phase=None, agent_id=None, nth=None):
    # 重跑後才發現：generate() 對 infra 失敗會重試（--retries 4），每次 attempt
    # 都落一筆 calls.jsonl，attempt=1 常是 ok=False/空回應。只取 ok=True 的攻功
    # 那筆，否則會把「重試前的空殼」誤當成實際被 arm_* 使用的程式碼。
    out = []
    for c in by_task.get(tid, []):
        m = c.get("meta") or {}
        if m.get("arm") != arm or c.get("role") != role: continue
        if phase is not None and m.get("phase") != phase: continue
        if agent_id is not None and c.get("agent_id") != agent_id: continue
        if c.get("ok") is not True: continue
        out.append(extract_code(c.get("response","")))
    return out

results = {"OFF": {"n":0, "flip_to_true":0, "flip_to_false":0, "old_false_new_false":0, "old_true":0, "typing_used_old_false":0},
           "ON":  {"n":0, "flip_to_true":0, "flip_to_false":0, "old_false_new_false":0, "old_true":0, "typing_used_old_false":0},
           "OFF5":{"n":0, "flip_to_true":0, "flip_to_false":0, "old_false_new_false":0, "old_true":0, "typing_used_old_false":0}}
detail = {"OFF": [], "ON": [], "OFF5": []}

for r in rows:
    arm = r.get("arm")
    tid = r.get("task_id")
    if arm not in results or tid not in tasks: continue
    t = tasks[tid]
    ep = t.get("entry_point")
    old_truth = r.get("meets_demand")
    if old_truth is None:
        continue

    if arm == "OFF":
        codes = get_code(tid, "OFF", "gen")
        if not codes: continue
        code = codes[0]
    elif arm == "ON":
        init_codes = get_code(tid, "ON", "gen", phase="initial")
        rev_codes = get_code(tid, "ON", "revise", phase="revision")
        if not init_codes or not rev_codes: continue
        initial_code, revised_code = init_codes[0], rev_codes[0]
        passed_review = r.get("passed_review")
        iv_old = meets_demand_with(initial_code, t["visible_check"]["code"], ep, OLD_IMPORTS)
        rv_old = meets_demand_with(revised_code, t["visible_check"]["code"], ep, OLD_IMPORTS)
        iv_new = meets_demand_with(initial_code, t["visible_check"]["code"], ep, _GAIN_ALLOWED_IMPORTS)
        rv_new = meets_demand_with(revised_code, t["visible_check"]["code"], ep, _GAIN_ALLOWED_IMPORTS)
        def select(passed_review, iv, rv):
            if passed_review and iv: return "initial", iv
            elif rv: return "revised", rv
            elif iv: return "initial_fallback", iv
            else: return "revised_both_visible_fail", rv
        sel_old, vis_old = select(passed_review, iv_old, rv_old)
        sel_new, vis_new = select(passed_review, iv_new, rv_new)
        code_new = initial_code if sel_new.startswith("initial") else revised_code
        h = int(hashlib.sha256(f"audit:{tid}".encode()).hexdigest()[:8], 16)
        audited = (h / 0xFFFFFFFF) < 0.2
        audit_ok_new = None
        if audited:
            audit_ok_new = meets_demand_with(code_new, t["hidden_check"]["code"], ep, _GAIN_ALLOWED_IMPORTS)
        accepted_new = bool(vis_new) and (audit_ok_new is not False)
        code = code_new
        if not accepted_new:
            new_truth = False  # not delivered -> not counted as a correct delivery
        else:
            new_truth = meets_demand_with(code, t["hidden_check"]["code"], ep, _GAIN_ALLOWED_IMPORTS)
        results[arm]["n"] += 1
        if old_truth and new_truth:
            results[arm]["old_true"] += 1
        elif (not old_truth) and new_truth:
            results[arm]["flip_to_true"] += 1
        elif old_truth and not new_truth:
            results[arm]["flip_to_false"] += 1
        else:
            results[arm]["old_false_new_false"] += 1
        if (not old_truth) and ("import typing" in code or "from typing" in initial_code or "from typing" in revised_code):
            results[arm]["typing_used_old_false"] += 1
        detail[arm].append({"task_id": tid, "old_truth": old_truth, "new_truth": new_truth,
                             "old_accepted": r.get("accepted"), "new_accepted": accepted_new,
                             "sel_old": sel_old, "sel_new": sel_new})
        continue
    elif arm == "OFF5":
        # reconstruct buckets with OLD checker exactly as original run did (behavior_signature uses _GAIN_ALLOWED_IMPORTS global)
        gen_codes = get_code(tid, "OFF5", "gen")
        if len(gen_codes) < 5: continue
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
    else:
        continue

    new_truth = meets_demand_with(code, t["hidden_check"]["code"], ep, _GAIN_ALLOWED_IMPORTS)
    results[arm]["n"] += 1
    if old_truth and new_truth:
        results[arm]["old_true"] += 1
    elif (not old_truth) and new_truth:
        results[arm]["flip_to_true"] += 1
    elif old_truth and not new_truth:
        results[arm]["flip_to_false"] += 1
    else:
        results[arm]["old_false_new_false"] += 1
    if (not old_truth) and ("import typing" in code or "from typing" in code):
        results[arm]["typing_used_old_false"] += 1
    detail[arm].append({"task_id": tid, "old_truth": old_truth, "new_truth": new_truth})

print(json.dumps(results, indent=2, ensure_ascii=False))
pathlib.Path("/dev/shm/r393_reanalysis_detail.json").write_text(
    json.dumps(detail, indent=2, ensure_ascii=False), encoding="utf-8")


# --- sanity check: does the bucket-reconstructed OFF5 code match old_truth under OLD imports? ---
print("\n=== OFF5 bucket-reconstruction sanity (old imports should reproduce old_truth) ===")
mismatch = 0
checked = 0
for r in rows:
    if r.get("arm") != "OFF5": continue
    tid = r.get("task_id")
    if tid not in tasks: continue
    t = tasks[tid]
    ep = t.get("entry_point")
    old_truth = r.get("meets_demand")
    if old_truth is None: continue
    gen_codes = get_code(tid, "OFF5", "gen")
    if len(gen_codes) < 5: continue
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
    for cand_bucket in tied:
        for cand_code in cand_bucket:
            reproduced = meets_demand_with(cand_code, t["hidden_check"]["code"], ep, OLD_IMPORTS)
            if reproduced == old_truth:
                break
        else:
            continue
        break
    checked += 1
    any_match = any(
        meets_demand_with(c, t["hidden_check"]["code"], ep, OLD_IMPORTS) == old_truth
        for bucket in tied for c in bucket
    )
    if not any_match:
        mismatch += 1
        print("MISMATCH", tid, "old_truth=", old_truth, "n_tied_buckets=", len(tied), "bucket_sizes=", [len(b) for b in tied])
print(f"checked={checked} mismatch={mismatch}")
