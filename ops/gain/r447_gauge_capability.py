#!/usr/bin/env python3
"""R450 量具能力普查——判準見 DECISION_20260904_R450_GAUGE_CAPABILITY_CENSUS.md（量測前寫定）。

唯讀離線尺，零 API。不改 r447 任何判準；所有輸出標 NOT_ARBITER。

用法：
  python3 ops/gain/r447_gauge_capability.py runs/g_r447_conform_lcb2 [--json out.json]
  python3 ops/gain/r447_gauge_capability.py --selftest
"""
from __future__ import annotations
import ast, json, os, pathlib, sys

REQUIRED = ("arm", "task_id", "meets_demand", "accepted")

# analyze_r447.py 的 _deliv 是 R667 凍結口徑。本尺 §三 的推導以它為前提，
# 所以逐字取出來比對；它一改，本尺就沒有立場宣稱那條結構性結論。
FROZEN_DELIV_EXPR = 'bool(r.get("accepted")) and bool(r.get("meets_demand"))'


def _mut() -> str:
    # r706：突變一律在被測函式內部生效，不在模組層讀（模組層 import 當下為空＝突變不生效）
    return os.environ.get("R450_MUTANT", "")


def deliv_contract_drift(analyze_path: pathlib.Path) -> str | None:
    """從 analyze_r447.py 原始碼逐字取 _deliv 的正式 return，與凍結口徑比對。"""
    src = analyze_path.read_text()
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "_deliv"), None)
    if fn is None:
        return "analyze_r447.py 找不到 _deliv"
    # 取最後一個 return（MUTANT 分支在前，正式口徑在後）
    # ast.walk 是 BFS，不保證原始碼順序 ⇒ 明確按 (lineno, col_offset) 排序後取最後一個
    rets = sorted((n for n in ast.walk(fn)
                   if isinstance(n, ast.Return) and n.value is not None),
                  key=lambda n: (n.lineno, n.col_offset))
    if not rets:
        return "_deliv 沒有 return"
    got = ast.get_source_segment(src, rets[-1].value)
    if got != FROZEN_DELIV_EXPR:
        return f"_deliv 口徑漂移：{got!r} != {FROZEN_DELIV_EXPR!r}"
    return None


def _deliv(r: dict) -> bool:
    return bool(r.get("accepted")) and bool(r.get("meets_demand"))


def _mcnemar_bc(rows_a: list[dict], rows_b: list[dict], skip: set[str]) -> tuple[int, int, int]:
    A = {r["task_id"]: _deliv(r) for r in rows_a if r["task_id"] not in skip}
    B = {r["task_id"]: _deliv(r) for r in rows_b if r["task_id"] not in skip}
    common = A.keys() & B.keys()
    b = sum(1 for t in common if A[t] and not B[t])
    c = sum(1 for t in common if B[t] and not A[t])
    return b, c, len(common)


def census(rows: list[dict]) -> dict:
    mut = _mut()
    out: dict = {"verdict": "OK", "NOT_ARBITER": True}

    # 擋門 1：缺鍵（型一「安靜量不到」）
    for r in rows:
        missing = [k for k in REQUIRED if k not in r]
        if missing:
            return {"verdict": "BROKEN_SCHEMA", "missing": missing, "task_id": r.get("task_id")}

    # 註：原判準 §五-3「_deliv=True 而 meets_demand=False ⇒ BROKEN」是**恆假的死碼**：
    # _deliv ≡ accepted ∧ meets_demand，故該條件 ≡ (X ∧ Y) ∧ ¬Y ≡ False，任何資料都觸發不了
    # （r695 的「同源擋門」）。已於量測前刪除，其防護意圖由 deliv_contract_drift() 承擔——
    # 真正的風險是 analyze_r447._deliv 的口徑被改掉，那個是逐字比對得出來的。

    by_task: dict[str, list[dict]] = {}
    for r in rows:
        by_task.setdefault(r["task_id"], []).append(r)

    if mut == "M1_include_partial":
        complete = dict(by_task)
    else:
        complete = {t: rs for t, rs in by_task.items() if len(rs) == 3}
    partial = {t: rs for t, rs in by_task.items() if len(rs) != 3}

    # 擋門 2：型二「量到的數量掉下來」
    if mut != "M4_no_complete_guard" and not complete:
        return {"verdict": "BROKEN_NO_COMPLETE_TASKS",
                "n_tasks_seen": len(by_task), "n_partial": len(partial)}

    def passed(rs: list[dict]) -> bool:
        if mut == "M2_capability_uses_deliv":
            return any(_deliv(r) for r in rs)
        return any(bool(r.get("meets_demand")) for r in rs)

    demonstrated = {t for t, rs in complete.items() if passed(rs)}
    undemonstrated = set(complete) - demonstrated

    out.update({
        "n_tasks_complete": len(complete),
        "n_tasks_partial_excluded": len(partial),
        "n_demonstrated": len(demonstrated),
        "n_undemonstrated": len(undemonstrated),
        "pct_undemonstrated": round(100.0 * len(undemonstrated) / len(complete), 3) if complete else None,
        "undemonstrated_task_ids": sorted(undemonstrated),
    })

    # §六 推翻條件：undemonstrated > 50% ⇒ 量測窗口本身要被質疑
    out["window_doubt_triggered"] = bool(complete) and len(undemonstrated) > 0.5 * len(complete)

    # §四 P-Z1 括號（NOT_ARBITER）
    off = [r for r in rows if r["arm"] == "OFF" and r["task_id"] in complete]
    off_dem = [r for r in off if r["task_id"] in demonstrated]

    def fail_pct(rs):
        return round(100.0 * sum(1 for r in rs if not _deliv(r)) / len(rs), 3) if rs else None

    out["pz1_raw_NOT_ARBITER"] = fail_pct(off)
    out["pz1_demonstrated_only_NOT_ARBITER"] = fail_pct(off_dem)

    # §三 結構性結論的真資料對照：排除 undemonstrated 後 b/c 必須逐數不變
    by_arm: dict[str, list[dict]] = {}
    for r in rows:
        if r["task_id"] in complete:
            by_arm.setdefault(r["arm"], []).append(r)
    skip = demonstrated if mut == "M5_exclude_wrong_set" else undemonstrated
    bc = {}
    mismatch = []
    for x, y in (("CONFORM", "OFF"), ("CONFORM", "OFF5"), ("OFF5", "OFF")):
        if x in by_arm and y in by_arm:
            full = _mcnemar_bc(by_arm[x], by_arm[y], set())
            excl = _mcnemar_bc(by_arm[x], by_arm[y], skip)
            bc[f"{x}_vs_{y}"] = {"full_b_c_n": full, "excl_undem_b_c": excl[:2]}
            if full[:2] != excl[:2]:
                mismatch.append(f"{x}_vs_{y}")
    out["bc_cross_check"] = bc
    if mismatch:
        out["verdict"] = "BROKEN_BC_MISMATCH"
        out["bc_mismatch"] = mismatch
    return out


# ── selftest ─────────────────────────────────────────────────────────────
def _row(arm, tid, md, acc):
    """夾具自己造原始列，不共用被測檔的 helper（r699）。"""
    return {"arm": arm, "task_id": tid, "meets_demand": md, "accepted": acc}


def _fixture() -> list[dict]:
    rows = []
    # T1..T4：demonstrated（至少一臂真的過）
    for i, (cm, om, o5m) in enumerate([(True, True, True), (True, False, True),
                                       (False, True, False), (True, False, False)]):
        t = f"T{i+1}"
        rows += [_row("CONFORM", t, cm, cm), _row("OFF", t, om, om), _row("OFF5", t, o5m, o5m)]
    # T5, T6：undemonstrated（三臂全滅）
    for t in ("T5", "T6"):
        rows += [_row("CONFORM", t, False, False), _row("OFF", t, False, False),
                 _row("OFF5", t, False, False)]
    # T7：對的答案被閘門擋掉 ⇒ meets_demand=True 但 accepted=False，
    #     依 §二 仍是 demonstrated（M2 會把它誤判成 undemonstrated）
    rows += [_row("CONFORM", "T7", True, False), _row("OFF", "T7", False, False),
             _row("OFF5", "T7", False, False)]
    # T8：只跑了兩臂 ⇒ 必須排除（M1 會把它算成 undemonstrated）
    rows += [_row("CONFORM", "T8", False, False), _row("OFF", "T8", False, False)]
    return rows


def selftest() -> int:
    fails = []

    def ck(label, cond, extra=""):
        print(f"  {'PASS' if cond else 'FAIL'}  {label}{'  ' + extra if extra else ''}")
        if not cond:
            fails.append(label)

    def run(rows, mutant=""):
        os.environ["R450_MUTANT"] = mutant
        try:
            return census(rows)
        finally:
            os.environ.pop("R450_MUTANT", None)

    rows = _fixture()
    a = run(rows)
    print("[乾淨夾具]")
    ck("A verdict OK", a["verdict"] == "OK", a["verdict"])
    ck("B 三臂齊的題 =7（T8 被排除）", a["n_tasks_complete"] == 7, str(a["n_tasks_complete"]))
    ck("C partial 單獨計數 =1", a["n_tasks_partial_excluded"] == 1)
    ck("D demonstrated =5（含被閘門擋掉的 T7）", a["n_demonstrated"] == 5, str(a["n_demonstrated"]))
    ck("E undemonstrated =2（T5,T6）", a["undemonstrated_task_ids"] == ["T5", "T6"])
    ck("F 窗口疑慮未觸發（2/7 < 50%）", a["window_doubt_triggered"] is False)
    ck("G §三 b/c 對照相同", "bc_mismatch" not in a, json.dumps(a["bc_cross_check"]))

    print("[植入缺陷：判準＝該吐哪個 verdict／哪個量要變，不是只看 rc]")
    m1 = run(rows, "M1_include_partial")
    ck("M1 混入未跑完的題 ⇒ undemonstrated 從 2 變 3",
       m1["n_undemonstrated"] == 3 and a["n_undemonstrated"] == 2, str(m1["n_undemonstrated"]))
    m2 = run(rows, "M2_capability_uses_deliv")
    ck("M2 能力改用 _deliv ⇒ T7 被誤判成 undemonstrated",
       m2["undemonstrated_task_ids"] == ["T5", "T6", "T7"], str(m2["undemonstrated_task_ids"]))
    # M3（原判準 §五-3）已刪除：該擋門是恆假死碼，沒有任何夾具能讓它為真。
    # 證明寫成可執行的斷言，而不是留一條永遠 PASS 的空洞綠燈。
    probe = [{"arm": "CONFORM", "task_id": "T9", "meets_demand": m, "accepted": a}
             for m in (True, False) for a in (True, False)]
    ck("M3 一致性擋門恆假（_deliv 與 meets_demand 同源）⇒ 已刪除而非留空綠燈",
       all(not (_deliv(r) and not bool(r.get("meets_demand"))) for r in probe),
       "四種 (meets_demand, accepted) 組合皆無法觸發")

    m4 = run([r for r in rows if r["task_id"] == "T8"], "M4_no_complete_guard")
    clean4 = run([r for r in rows if r["task_id"] == "T8"])
    ck("M4 只有未跑完的題時：乾淨版 BROKEN_NO_COMPLETE_TASKS、突變版沒叫",
       clean4["verdict"] == "BROKEN_NO_COMPLETE_TASKS" and m4["verdict"] != "BROKEN_NO_COMPLETE_TASKS",
       f'{clean4["verdict"]} / {m4["verdict"]}')
    m5 = run(rows, "M5_exclude_wrong_set")
    ck("M5 排錯集合 ⇒ b/c 對照必須叫 BROKEN_BC_MISMATCH",
       m5["verdict"] == "BROKEN_BC_MISMATCH", m5["verdict"])
    bad_schema = run([{"arm": "OFF", "task_id": "T1", "meets_demand": True}])
    ck("M6 缺鍵 ⇒ BROKEN_SCHEMA", bad_schema["verdict"] == "BROKEN_SCHEMA", bad_schema["verdict"])

    print("[契約]")
    drift = deliv_contract_drift(pathlib.Path(__file__).with_name("analyze_r447.py"))
    ck("H analyze_r447._deliv 口徑未漂移", drift is None, drift or "")

    print(f"\n{'SELFTEST_PASS' if not fails else 'SELFTEST_FAIL ' + ','.join(fails)}")
    return 0 if not fails else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    run_dir = pathlib.Path(sys.argv[1])
    drift = deliv_contract_drift(pathlib.Path(__file__).with_name("analyze_r447.py"))
    rows = [json.loads(l) for l in (run_dir / "rows.jsonl").open() if l.strip()]
    out = census(rows)
    out["deliv_contract_drift"] = drift
    if drift:
        out["verdict"] = "BROKEN_CONTRACT_DRIFT"
    out["rows_file_lines"] = len(rows)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if "--json" in sys.argv:
        pathlib.Path(sys.argv[sys.argv.index("--json") + 1]).write_text(
            json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["verdict"] == "OK" else 2


if __name__ == "__main__":
    sys.exit(main())
