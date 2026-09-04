"""R474（round744）：把「壞解要全擋」這半邊的量具驗證從 `covered` 濾網底下解放出來，
對整個 bank 逐題掃一次（零 API、只讀 bank 檔、不碰任何 run 目錄）。

這支在架構裡承重什麼
--------------------
SPEC_GAIN 的自我驗證寫死「官方參考解要全過、壞解要全擋，任一方向不滿分就停」。
實作是 `gain_run.probe_instrument()`，但它的兩個方向共用同一行濾網：

    covered = [t for t in tasks if refs.get(t["task_id"])][:sample]

正方向需要參考解，**反方向不需要**（樁是 `return None`）。於是「壞解要全擋」
的覆蓋率被一個只有正方向才需要的條件壓下去（lcb3：12/189）。遮住的失效模式是
「`hidden_check` 什麼都判通過」——那會同時抬高三條臂，長得跟天花板效應一模一樣。

三個分類是事前寫死的（DECISION_20260904_R474 §二.1），不准事後合併：

  STUB_REJECTED   樁被擋下來 ⇒ 這一題的反方向有證據
  STUB_ACCEPTED   樁被放行   ⇒ 缺陷：這一題對任何東西都放行
  CHECK_UNUSABLE  檢查式自己壞掉（語法錯／沙箱起不來／逾時）⇒ **不是**綠燈，單獨數

⚠ 單邊保證（誠實邊界，收官不准漏）：樁掃描抓得到「什麼都判通過」，
  **抓不到**「什麼都判失敗」——後者只有正方向（要參考解）能抓。所以本尺的產出
  只能寫成「反方向覆蓋率 N/N」，不能寫成「雙向驗證已達 100%」。

⚠ 樁的字面與逾時秒數都**不是**這支自己的旋鈕：樁用 `ast.get_source_segment` 從
  `probe_instrument` 逐字取出真運算式再 eval，逾時讀 `meets_demand` 的簽章預設值。
  哪天那邊改了，這支要嘛跟著對、要嘛具名地吵（`StubWiringError`），不會安靜錯。

用法：
    python3 ops/gain/r474_stub_sweep.py --bank lcb3 --seed g-r461-lcb3 --json out.json
    python3 ops/gain/r474_stub_sweep.py --selftest
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

REJECTED = "STUB_REJECTED"
ACCEPTED = "STUB_ACCEPTED"
UNUSABLE = "CHECK_UNUSABLE"
NO_CHECK = "NO_CHECK"


class StubWiringError(RuntimeError):
    """接線壞掉：跟「掃描掃到 0 個目標」必須分得開（前者沒量到，後者量到 0）。"""


def _gain_run():
    spec = importlib.util.spec_from_file_location("_gr_r474", _GAIN_RUN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def stub_expr_source() -> str:
    """從 `probe_instrument` 逐字取出 `stub = ...` 的右手邊，不自己重寫一份。"""
    src = _GAIN_RUN.read_text()
    tree = ast.parse(src)
    fns = [n for n in ast.walk(tree)
           if isinstance(n, ast.FunctionDef) and n.name == "probe_instrument"]
    if len(fns) != 1:
        raise StubWiringError(f"probe_instrument 不是唯一的（{len(fns)} 個）")
    for node in ast.walk(fns[0]):
        if isinstance(node, ast.Assign) and any(
                isinstance(tg, ast.Name) and tg.id == "stub" for tg in node.targets):
            seg = ast.get_source_segment(src, node.value)
            if not seg:
                raise StubWiringError("取不到 stub 運算式原文")
            return seg
    raise StubWiringError("probe_instrument 裡沒有 stub 的賦值")


def timeout_default(gr) -> int:
    """逾時秒數取自 `meets_demand` 的簽章預設，不是這支自己的旋鈕。"""
    d = inspect.signature(gr.meets_demand).parameters["timeout_s"].default
    if not isinstance(d, (int, float)):
        raise StubWiringError(f"meets_demand.timeout_s 預設不是數字：{d!r}")
    return d


def classify(task: dict, which: str, gr, stub_src: str, timeout_s) -> dict:
    """對一題的一種檢查式做一次樁掃描，回事前寫死的三分類之一。"""
    check = (task.get(which) or {}).get("code") or ""
    if not check:
        return {"task_id": task.get("task_id"), "which": which, "cls": NO_CHECK}
    out = {"task_id": task.get("task_id"), "which": which}
    try:
        compile(check, "<check>", "exec")
    except SyntaxError as e:
        return {**out, "cls": UNUSABLE, "reason": f"check_syntax_error: {e}"}
    stub = eval(stub_src, {"t": task})                        # noqa: S307 逐字取自 probe_instrument
    t0 = time.monotonic()
    try:
        ok, msg = gr.meets_demand(stub, check, entry_point=task.get("entry_point"))
    except gr.InfraVoid as e:
        return {**out, "cls": UNUSABLE, "reason": f"infra_void: {e}",
                "elapsed_s": round(time.monotonic() - t0, 3)}
    el = time.monotonic() - t0
    if el >= timeout_s:
        return {**out, "cls": UNUSABLE, "reason": "check_timeout",
                "elapsed_s": round(el, 3)}
    return {**out, "cls": ACCEPTED if ok else REJECTED,
            "msg": msg[:120], "elapsed_s": round(el, 3)}


def sweep(tasks, gr, *, whichs=("hidden_check", "visible_check"), log=lambda s: None) -> dict:
    stub_src = stub_expr_source()
    timeout_s = timeout_default(gr)
    rows = []
    for i, t in enumerate(tasks, 1):
        for which in whichs:
            rows.append(classify(t, which, gr, stub_src, timeout_s))
        if i % 20 == 0:
            log(f"  ...{i}/{len(tasks)}")
    counts = {}
    for r in rows:
        counts.setdefault(r["which"], {}).setdefault(r["cls"], 0)
        counts[r["which"]][r["cls"]] += 1
    return {"stub_expr": stub_src, "timeout_s": timeout_s,
            "n_tasks": len(tasks), "counts": counts, "rows": rows}


# ── 自檢（DECISION §三 P5：三格全中才算尺有牙齒）────────────────────
def _fixture(entry: str, check: str, which: str = "hidden_check") -> dict:
    return {"task_id": f"fix_{entry}_{which}", "entry_point": entry,
            which: {"code": check}}


def selftest() -> int:
    gr = _gain_run()
    stub_src = stub_expr_source()
    timeout_s = timeout_default(gr)
    failed = []

    def want(name, task, which, expect):
        got = classify(task, which, gr, stub_src, timeout_s)
        if got.get("cls") != expect:
            failed.append(f"{name}: 期望 {expect} 得到 {got.get('cls')} {got.get('reason','')}")
        print(f"  {name:26s} {got.get('cls'):15s} (期望 {expect})")
        return got

    # A 放行一切的 check ⇒ 必須是 STUB_ACCEPTED（這就是要抓的失效模式）
    want("A_permissive_check", _fixture("f", "pass"), "hidden_check", ACCEPTED)
    # B 正常的 check ⇒ STUB_REJECTED
    want("B_normal_check", _fixture("f", "assert f(1) == 2\n"), "hidden_check", REJECTED)
    # C 語法壞掉的 check ⇒ CHECK_UNUSABLE，**不准**落進 STUB_REJECTED
    want("C_syntax_broken", _fixture("f", "def (\n"), "hidden_check", UNUSABLE)
    # D 永遠跑不完的 check ⇒ CHECK_UNUSABLE（沒有計時規則的話會被誤記成 REJECTED）
    want("D_timeout_check", _fixture("f", "while True:\n    pass\n"), "hidden_check", UNUSABLE)
    # E 沒有 check 的題 ⇒ NO_CHECK（不准算進任何一格）
    want("E_missing_check", {"task_id": "fix_none", "entry_point": "f"},
         "hidden_check", NO_CHECK)
    # F visible_check 這條路徑也要走得到
    want("F_visible_path", _fixture("f", "assert f(1) == 2\n", "visible_check"),
         "visible_check", REJECTED)

    # G 計數不准把 UNUSABLE 併進 REJECTED（sweep 層的斷言）
    tasks = [_fixture("f", "pass"), _fixture("f", "assert f(1) == 2\n"),
             _fixture("f", "def (\n")]
    res = sweep(tasks, gr, whichs=("hidden_check",))
    c = res["counts"]["hidden_check"]
    if c.get(REJECTED) != 1 or c.get(ACCEPTED) != 1 or c.get(UNUSABLE) != 1:
        failed.append(f"G_counts_not_merged: {c}")
    print(f"  G_counts_not_merged        {c}")

    # H 接線：樁字面必須真的來自 probe_instrument（漂移要吵，不要安靜錯）
    if "return None" not in stub_src or "entry_point" not in stub_src:
        failed.append(f"H_stub_wiring: 取到的樁不像樁：{stub_src!r}")
    print(f"  H_stub_wiring              {stub_src!r}")

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
    bad = [r for r in res["rows"] if r["cls"] in (ACCEPTED, UNUSABLE)]
    for r in bad:
        print("  ⚠", r["task_id"], r["which"], r["cls"], r.get("reason", ""))
    res["verdict"] = ("REVERSE_DIRECTION_FULL" if not bad else "REVERSE_DIRECTION_DEFECTS")
    print("verdict:", res["verdict"], f"(flagged={len(bad)})")
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
