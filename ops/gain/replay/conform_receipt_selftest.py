#!/usr/bin/env python3
"""CONFORM 收據「卡在第幾條驗收」的自我驗證——零 API、零模型呼叫、不碰任何 run。

這支在架構裡承重什麼：R440P §六 對外那句「收據上照樣列出那五個人各自卡在第幾條」
只有在 `conform_failure_detail` 真的算得出條號時才成立。而它的輸入是
`vacant/codebench.py` 產生的 check code，形狀哪天改了、切片器就會安靜地回一片 null。
本支把「安靜失效」變成 FAIL。

四層：
  1 形狀層：兩個真題庫（MBPP+ 179 題、LCB 91 題）的 check code 全部要切得動。
  2 語意層：植入已知錯在第 k 條的候選，條號要對；連載入都失敗要判 loads_ok=False。
  3 一致性層：前綴 n 與原本的 check code 必須同判（`prefix_full_disagrees` 不得出現）。
  4 植入缺陷層：故意改壞切片器，上面三層必須 FAIL——證明綠燈有牙齒。

用法：python3 ops/gain/replay/conform_receipt_selftest.py
"""
from __future__ import annotations

import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
os.environ.setdefault(
    "VACANT_EVALPLUS_PATH", ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"
)

from ops.gain import gain_run  # noqa: E402
from ops.gain.gain_run import (_visible_test_slicer, conform_failure_detail,  # noqa: E402
                               load_tasks, meets_demand)

FAILURES: list[str] = []


def check(cond: bool, label: str) -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    if not cond:
        FAILURES.append(label)


def _synth(n_asserts: int) -> dict:
    """扁平形狀（同 evalplus `_check_code`）的合成題：f(i) 應該回 i+1。"""
    body = "\n".join(f"assert f({i}) == {i + 1}" for i in range(1, n_asserts + 1))
    return {"task_id": f"synth_{n_asserts}", "family": "synth", "entry_point": "f",
            "visible_check": {"type": "run_python", "code": body, "timeout": 8}}


def layer_shape() -> None:
    print("[1] 形狀層：真題庫的 check code 切不切得動")
    for bank, seed, n in (("evalplus", "g-r212-route-20260828", 179),
                          ("lcb", "g-r442-lcb", 91)):
        tasks = load_tasks(bank, seed, n)
        counts, bad = [], []
        for t in tasks:
            sl = _visible_test_slicer(t["visible_check"]["code"])
            if sl is None:
                bad.append(t["task_id"])
            else:
                counts.append(sl[0])
        check(not bad, f"{bank}: {len(tasks)} 題全部切得動（切不動 {len(bad)}: {bad[:5]}）")
        check(all(c > 0 for c in counts), f"{bank}: 每題至少一條驗收")
        if counts:
            print(f"        n={len(tasks)} 條數 min={min(counts)} "
                  f"中位={sorted(counts)[len(counts) // 2]} max={max(counts)}")


def layer_semantics() -> None:
    print("[2] 語意層：條號對不對")
    task = _synth(5)
    for k in (1, 3, 5):
        # 前 k-1 條對、第 k 條起錯
        code = f"def f(x): return x + 1 if x < {k} else 999"
        ok, _ = meets_demand(code, task["visible_check"]["code"], entry_point="f")
        d = conform_failure_detail(code, task)
        check(not ok and d["first_failing_test"] == k and d["loads_ok"] is True,
              f"錯在第 {k} 條 → first_failing_test={d['first_failing_test']} "
              f"loads_ok={d['loads_ok']} n={d['n_visible_tests']}")
    d = conform_failure_detail("def f(x):\n    return undefined_name_xyz", task)
    check(d["loads_ok"] is True and d["first_failing_test"] == 1,
          f"執行期才炸（第1條就炸）→ loads_ok={d['loads_ok']} "
          f"first={d['first_failing_test']}")
    d = conform_failure_detail("this is not python at all (((", task)
    check(d["loads_ok"] is False and d["first_failing_test"] is None,
          f"語法就壞、一條驗收都跑不到 → loads_ok={d['loads_ok']} "
          f"reason={d['detail_reason']}")
    sl = _visible_test_slicer("x = 1\nassert f(1) == 2\ny = 2")
    check(sl is None, "assert 不在尾端連續 → 拒絕切（回 None，不亂切）")


def layer_consistency() -> None:
    print("[3] 一致性層：前綴 n 與原 check code 同判（抽樣真題）")
    tasks = load_tasks("evalplus", "g-r212-route-20260828", 179)[:12]
    t0, disagree, n_fail = time.time(), [], 0
    for t in tasks:
        sl = _visible_test_slicer(t["visible_check"]["code"])
        if sl is None:
            continue
        n, make_prefix = sl
        bad_code = f"def {t['entry_point']}(*a, **k): return '__vacant_wrong__'"
        d = conform_failure_detail(bad_code, t)
        n_fail += 1
        if d["detail_reason"] == "prefix_full_disagrees":
            disagree.append(t["task_id"])
    check(not disagree, f"12 題壞候選全部切片一致（disagree {len(disagree)}: {disagree[:3]}）")
    print(f"        {n_fail} 個失敗候選算條號共 {time.time() - t0:.1f}s "
          f"（≈{(time.time() - t0) / max(n_fail, 1):.2f}s/候選）")


def layer_injected_defect() -> None:
    print("[4] 植入缺陷層：改壞切片器，上面幾層必須 FAIL")
    task, real = _synth(5), _visible_test_slicer

    def broken_ignores_i(check_code):
        sl = real(check_code)
        if sl is None:
            return None
        n, _mk = sl
        return n, (lambda i: check_code)          # 前綴永遠是完整版

    def broken_shape_blind(check_code):
        return None                                # 什麼形狀都認不出來

    def broken_off_by_one(check_code):
        sl = real(check_code)
        if sl is None:
            return None
        n, mk = sl
        return n, (lambda i: mk(min(i + 1, n)))    # 差一條 → 報出一個「錯的數字」

    for name, fake, want in (
        ("前綴忽略 i", broken_ignores_i, "條號錯"),
        ("形狀一律認不出（收據一片 null）", broken_shape_blind, "算不出條號"),
        ("前綴差一條", broken_off_by_one, "條號錯"),
    ):
        gain_run._visible_test_slicer = fake
        try:
            d = conform_failure_detail("def f(x): return x + 1 if x < 3 else 999", task)
            caught = d.get("first_failing_test") != 3
        finally:
            gain_run._visible_test_slicer = real
        check(caught, f"改壞「{name}」被抓到（{want}：first={d.get('first_failing_test')}）")

    d = conform_failure_detail("def f(x): return x + 1 if x < 3 else 999", task)
    check(d["first_failing_test"] == 3, "還原後原版仍然判對第 3 條")


def main() -> int:
    layer_shape()
    layer_semantics()
    layer_consistency()
    layer_injected_defect()
    print()
    if FAILURES:
        print(f"SELFTEST FAIL：{len(FAILURES)} 項\n  - " + "\n  - ".join(FAILURES))
        return 1
    print("SELFTEST PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
