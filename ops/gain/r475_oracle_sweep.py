"""R475（round745）：把「參考解要全過」那半邊從「要有參考解」的前提底下解放出來。

這支在架構裡承重什麼
--------------------
SPEC_GAIN 的量具雙向驗證寫死「參考解要全過、壞解要全擋」。R474 已經把**反方向**
（壞解要全擋）從 `probe_instrument()` 的 `covered` 濾網底下解放出來，lcb3 上做到 189/189。
**正方向仍然卡在 12/189**，因為它照字面需要參考解，而 lcb3 只有 12 題手寫解。

它遮住的失效模式是「`hidden_check` 什麼都判失敗」——那會同時**壓低**三條臂，
長得跟「題目太難」一模一樣，而「三臂都低」正是 R461 要拿來下結論的那個形狀。

做法：**不要參考解。** lcb3 的檢查式自己帶著測資表

    __tests = [{'args': [...], 'expected': ...}, ...]
    for __t in __tests:
        __got = <entry>(*__t['args'])
        assert __aeq(__got, __t['expected'])

⇒ 從**檢查式自己的原始碼**逐字取出那張表與被呼叫的函式名，合成一份「查表就回答」
的神諭解，餵回同一條 `meets_demand`。通過 ⇒ **這個檢查式是可滿足的**。

⚠ 誠實邊界（DECISION_20260904_R475 §五，收官不准漏）：
  1. 神諭掃描證明「可滿足」，**不是**「表裡的 expected 是對的」。`expected` 寫錯的
     檢查式照樣接受神諭解、卻擋掉正確的碼——那個失效模式只有真的參考解能抓。
     ⇒ 只能寫「正方向的**結構半邊** N/N」，不准寫成「參考解方向已達 100%」。
  2. 神諭解不是解，是查表。它對題目難度一句話都沒說。
  3. 與 R474 合起來每題可得的最強敘述是：**該檢查式會區分**（接受一份滿足它的碼、
     擋掉一份不作答的樁）。排除的是兩個結構性失效模式，不是全部。

五個分類事前寫死（§二），不准事後合併：

  ORACLE_ACCEPTED    神諭解通過   ⇒ 正方向的結構半邊有證據
  ORACLE_REJECTED    神諭解被擋   ⇒ 缺陷：照它自己的表回答都不過＝結構上不可滿足
  CHECK_UNUSABLE     檢查式自己壞掉（語法錯／InfraVoid／逾時）⇒ **不是**綠燈
  UNSUPPORTED_SHAPE  不是 args/expected 表 ⇒ **沒量到**（「安靜量不到」第三型）
  NO_CHECK           沒有檢查式

⚠ 接線規則：神諭表與函式名一律用 `ast` 從**檢查式原始碼**取出，不得由呼叫端的
  `entry_point` 欄位或手寫副本供給（R474 條 I 的教訓：寫死的副本長得一模一樣）。
  逾時秒數讀 `meets_demand` 的簽章預設，不是這支自己的旋鈕。

用法：
    python3 ops/gain/r475_oracle_sweep.py --bank lcb3 --seed g-r461-lcb3 --json out.json
    python3 ops/gain/r475_oracle_sweep.py --selftest
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import inspect
import json
import pathlib
import sys
import time

_HERE = pathlib.Path(__file__).resolve().parent
_GAIN_RUN = _HERE / "gain_run.py"

ACCEPTED = "ORACLE_ACCEPTED"
REJECTED = "ORACLE_REJECTED"
UNUSABLE = "CHECK_UNUSABLE"
UNSUPPORTED = "UNSUPPORTED_SHAPE"
NO_CHECK = "NO_CHECK"


class UnsupportedShape(RuntimeError):
    """造不出神諭解。要跟「造得出但被擋」分得開（沒量到 ≠ 量到 0）。"""


class OracleWiringError(RuntimeError):
    """接線壞掉：跟「掃描掃到 0 個目標」必須分得開。"""


def _gain_run():
    spec = importlib.util.spec_from_file_location("_gr_r475", _GAIN_RUN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def timeout_default(gr) -> int:
    """逾時秒數取自 `meets_demand` 的簽章預設，不是這支自己的旋鈕。"""
    d = inspect.signature(gr.meets_demand).parameters["timeout_s"].default
    if not isinstance(d, (int, float)):
        raise OracleWiringError(f"meets_demand.timeout_s 預設不是數字：{d!r}")
    return d


def extract_table(check_src: str) -> tuple[str, list]:
    """從檢查式原始碼取出 (被呼叫的函式名, 測資表)。形狀不符一律 `UnsupportedShape`。

    ⚠ 兩樣東西都只從 `check_src` 取。呼叫端的 `entry_point` 不參與——否則
      「檢查式其實呼叫別的名字」這種漂移會被呼叫端的欄位補起來、變安靜。
    """
    tree = ast.parse(check_src)
    tables = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        try:
            val = ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            continue
        if (isinstance(val, list) and val
                and all(isinstance(d, dict) and set(d) == {"args", "expected"}
                        for d in val)):
            tables.append(val)
    if len(tables) != 1:
        raise UnsupportedShape(f"args/expected 測資表不是唯一的（{len(tables)} 張）")
    names = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and len(node.args) == 1 and isinstance(node.args[0], ast.Starred)):
            names.add(node.func.id)
    if len(names) != 1:
        raise UnsupportedShape(f"`<name>(*args)` 的呼叫不是唯一的（{sorted(names)}）")
    return names.pop(), tables[0]


def oracle_source(check_src: str) -> tuple[str, str, list]:
    """合成神諭解。回 (原始碼, 函式名, 測資表)。"""
    entry, table = extract_table(check_src)
    body = (f"def {entry}(*a, **k):\n"
            f"    __table = {table!r}\n"
            f"    __key = list(a)\n"
            f"    for __e in __table:\n"
            f"        if __e['args'] == __key:\n"
            f"            return __e['expected']\n"
            f"    raise AssertionError('oracle: args not in table')\n")
    return body, entry, table


def _dup_conflict(table: list) -> bool:
    """同一組 args 對到不同 expected ⇒ 表自相矛盾（診斷欄位，不另立分類）。"""
    seen = {}
    for e in table:
        k = repr(e["args"])
        if k in seen and repr(seen[k]) != repr(e["expected"]):
            return True
        seen[k] = e["expected"]
    return False


def classify(task: dict, which: str, gr, timeout_s) -> dict:
    """對一題的一種檢查式做一次神諭掃描，回事前寫死的五分類之一。"""
    check = (task.get(which) or {}).get("code") or ""
    out = {"task_id": task.get("task_id"), "which": which}
    if not check:
        return {**out, "cls": NO_CHECK}
    try:
        compile(check, "<check>", "exec")
    except SyntaxError as e:
        return {**out, "cls": UNUSABLE, "reason": f"check_syntax_error: {e}"}
    try:
        oracle, entry, table = oracle_source(check)
    except UnsupportedShape as e:
        return {**out, "cls": UNSUPPORTED, "reason": str(e)}
    out.update({"entry": entry, "n_tests": len(table),
                "entry_mismatch": bool(task.get("entry_point"))
                and task.get("entry_point") != entry,
                "dup_conflict": _dup_conflict(table)})
    t0 = time.monotonic()
    try:
        ok, msg = gr.meets_demand(oracle, check, entry_point=entry)
    except gr.InfraVoid as e:
        return {**out, "cls": UNUSABLE, "reason": f"infra_void: {e}",
                "elapsed_s": round(time.monotonic() - t0, 3)}
    el = time.monotonic() - t0
    if el >= timeout_s:
        return {**out, "cls": UNUSABLE, "reason": "check_timeout",
                "elapsed_s": round(el, 3)}
    return {**out, "cls": ACCEPTED if ok else REJECTED,
            "msg": msg[:120], "elapsed_s": round(el, 3)}


def sweep(tasks, gr, *, whichs=("hidden_check", "visible_check"),
          log=lambda s: None) -> dict:
    timeout_s = timeout_default(gr)
    rows = []
    for i, t in enumerate(tasks, 1):
        for which in whichs:
            rows.append(classify(t, which, gr, timeout_s))
        if i % 20 == 0:
            log(f"  ...{i}/{len(tasks)}")
    counts = {}
    for r in rows:
        counts.setdefault(r["which"], {}).setdefault(r["cls"], 0)
        counts[r["which"]][r["cls"]] += 1
    return {"timeout_s": timeout_s, "n_tasks": len(tasks),
            "counts": counts, "rows": rows}


# ── 自檢（DECISION §三 P4）────────────────────────────────────────
_TBL2 = ("__tests = [{'args': [1], 'expected': 2}, {'args': [3], 'expected': 4}]\n"
         "for __t in __tests:\n"
         "    __got = f(*__t['args'])\n"
         "    assert __got == __t['expected'], __t\n")
_TBL_FALSE = ("__tests = [{'args': [1], 'expected': 2}]\n"
              "for __t in __tests:\n"
              "    __got = f(*__t['args'])\n"
              "    assert False, 'always fails'\n")
_TBL_SPIN = ("__tests = [{'args': [1], 'expected': 2}]\n"
             "for __t in __tests:\n"
             "    __got = f(*__t['args'])\n"
             "    while True:\n"
             "        pass\n")


def _fixture(entry: str, check: str, which: str = "hidden_check") -> dict:
    return {"task_id": f"fix_{entry}_{which}", "entry_point": entry,
            which: {"code": check}}


def selftest() -> int:
    gr = _gain_run()
    timeout_s = timeout_default(gr)
    failed = []

    def want(name, task, which, expect):
        got = classify(task, which, gr, timeout_s)
        if got.get("cls") != expect:
            failed.append(f"{name}: 期望 {expect} 得到 {got.get('cls')} "
                          f"{got.get('reason', '')}{got.get('msg', '')}")
        print(f"  {name:26s} {str(got.get('cls')):18s} (期望 {expect})")
        return got

    # A 可滿足的 check ⇒ ORACLE_ACCEPTED（兩筆不同 expected：也是 M4 的見證）
    want("A_satisfiable_check", _fixture("f", _TBL2), "hidden_check", ACCEPTED)
    # B 恆假的 check ⇒ ORACLE_REJECTED（＝要抓的失效模式：什麼都判失敗）
    want("B_unsatisfiable_check", _fixture("f", _TBL_FALSE), "hidden_check", REJECTED)
    # C 語法壞掉 ⇒ CHECK_UNUSABLE，不准落進 REJECTED
    want("C_syntax_broken", _fixture("f", "def (\n"), "hidden_check", UNUSABLE)
    # D 跑不完 ⇒ CHECK_UNUSABLE（沒有計時規則會被誤記成 REJECTED）
    want("D_timeout_check", _fixture("f", _TBL_SPIN), "hidden_check", UNUSABLE)
    # E 沒有 check ⇒ NO_CHECK
    want("E_missing_check", {"task_id": "fix_none", "entry_point": "f"},
         "hidden_check", NO_CHECK)
    # F visible_check 這條路徑也要走得到
    want("F_visible_path", _fixture("f", _TBL2, "visible_check"),
         "visible_check", ACCEPTED)
    # G 不是表形狀 ⇒ UNSUPPORTED_SHAPE，**不准**當綠燈（安靜量不到第三型）
    want("G_unsupported_shape", _fixture("f", "assert f(1) == 2\n"),
         "hidden_check", UNSUPPORTED)

    # H 計數不准把 UNSUPPORTED／UNUSABLE 併進 ACCEPTED（sweep 層的斷言）
    tasks = [_fixture("f", _TBL2), _fixture("f", _TBL_FALSE),
             _fixture("f", "def (\n"), _fixture("f", "assert f(1) == 2\n")]
    res = sweep(tasks, gr, whichs=("hidden_check",))
    c = res["counts"]["hidden_check"]
    if (c.get(ACCEPTED) != 1 or c.get(REJECTED) != 1
            or c.get(UNUSABLE) != 1 or c.get(UNSUPPORTED) != 1):
        failed.append(f"H_counts_not_merged: {c}")
    print(f"  H_counts_not_merged        {c}")

    # I 神諭表是真的追著檢查式原始碼跑，不是寫死一份（M2 專用；只翻來源、不翻別的）
    src_a = oracle_source(_TBL2)[0]
    src_b = oracle_source(_TBL2.replace("'expected': 4", "'expected': 99"))[0]
    if "99" not in src_b or "99" in src_a or src_a == src_b:
        failed.append(f"I_table_tracks_source: 來源改了但神諭沒變：{src_b!r}")
    print(f"  I_table_tracks_source      {'99' in src_b and src_a != src_b}")

    for f in failed:
        print("FAIL", f)
    print("SELFTEST_PASS" if not failed else f"SELFTEST_FAIL ({len(failed)})")
    return 0 if not failed else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", default="lcb3")
    ap.add_argument("--seed", default="g-r461-lcb3")
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    gr = _gain_run()
    tasks = gr.load_tasks(a.bank, a.seed, 0)
    refs = gr._canonical_solutions(a.bank)
    covered = [t for t in tasks if refs.get(t["task_id"])]
    print(f"bank={a.bank} n_tasks={len(tasks)} probe_covered={len(covered)}"
          f" ({len(covered)}/{len(tasks)})")
    res = sweep(tasks, gr, log=print)
    res.update({"bank": a.bank, "seed": a.seed,
                "probe_covered": len(covered), "n_tasks": len(tasks)})
    for which, c in res["counts"].items():
        print(f"{which}: {c}")
    bad = [r for r in res["rows"] if r["cls"] in (REJECTED, UNUSABLE, UNSUPPORTED)]
    for r in bad:
        print("  ⚠", r["task_id"], r["which"], r["cls"], r.get("reason", ""),
              r.get("msg", ""))
    odd = [r for r in res["rows"] if r.get("dup_conflict") or r.get("entry_mismatch")]
    for r in odd:
        print("  ?", r["task_id"], r["which"], "dup_conflict", r.get("dup_conflict"),
              "entry_mismatch", r.get("entry_mismatch"))
    res["n_dup_conflict"] = sum(1 for r in res["rows"] if r.get("dup_conflict"))
    res["n_entry_mismatch"] = sum(1 for r in res["rows"] if r.get("entry_mismatch"))
    res["verdict"] = ("POSITIVE_STRUCTURAL_FULL" if not bad
                      else "POSITIVE_STRUCTURAL_DEFECTS")
    print("verdict:", res["verdict"], f"(flagged={len(bad)})")
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
