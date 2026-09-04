"""R474 的外部植入缺陷測試（源碼級突變，跑在獨立 worktree 上）。

為什麼是外部、源碼級：檔內 `MUTANT` env 旗標答不了「把正式那段刪掉會不會紅」
（r473 記過：模組層讀 env 的突變體永遠不生效，長得跟「偵測條沒牙齒」一模一樣）。

判準：突變體必須讓 `--selftest` **rc≠0**，而且紅的那一條要**指名**是預期的那一條；
語法壞掉的負對照記 BROKEN（不算 caught）。
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

REL = "ops/gain/r474_stub_sweep.py"

MUTANTS = {
    # 預註冊 P6：把 CHECK_UNUSABLE 併進 STUB_REJECTED（＝把「量不到」寫成「量到 0」）
    "M1_syntax_unusable_to_rejected": (
        'return {**out, "cls": UNUSABLE, "reason": f"check_syntax_error: {e}"}',
        'return {**out, "cls": REJECTED, "reason": f"check_syntax_error: {e}"}',
        "C_syntax_broken"),
    # 探索性：把逾時規則整段拿掉（沒有它，跑不完的 check 會被記成「有擋下來」）
    "M2_drop_timeout_rule": (
        '    if el >= timeout_s:\n'
        '        return {**out, "cls": UNUSABLE, "reason": "check_timeout",\n'
        '                "elapsed_s": round(el, 3)}\n',
        '',
        "D_timeout_check"),
    # 探索性：把「逐字取樁」換成自己重寫一份（漂移會變安靜）
    "M3_hardcode_stub_copy": (
        '            seg = ast.get_source_segment(src, node.value)',
        '            seg = "f\\"def {t.get(\'entry_point\',\'_f\')}(*a, **k):'
        '\\\\n    return None\\\\n\\""',
        "H_stub_wiring"),
    # 負對照：語法壞掉 ⇒ BROKEN，不算 caught
    "N1_syntax": ("def selftest() -> int:", "def selftest( -> int:", None),
}


def run(wt: pathlib.Path) -> tuple[int, str]:
    p = subprocess.run([sys.executable, str(wt / REL), "--selftest"],
                       capture_output=True, text=True, cwd=str(wt), timeout=600)
    return p.returncode, p.stdout + p.stderr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worktree", required=True)
    a = ap.parse_args()
    wt = pathlib.Path(a.worktree).resolve()
    src_path = wt / REL
    clean = src_path.read_text()

    rc, out = run(wt)
    base_ok = rc == 0 and "SELFTEST_PASS" in out
    print(f"[乾淨基線] rc={rc} pass={base_ok}")
    if not base_ok:
        print(out[-800:])
        print("BASELINE_BROKEN")
        return 1

    results = {}
    for name, (old, new, expect_cond) in MUTANTS.items():
        if old not in clean:
            print(f"{name:32s} BROKEN  （突變字串對不上正式碼＝突變沒生效）")
            results[name] = "BROKEN"
            continue
        src_path.write_text(clean.replace(old, new, 1))
        rc, out = run(wt)
        named = expect_cond is not None and re.search(
            rf"FAIL {re.escape(expect_cond)}|{re.escape(expect_cond)}.*期望", out) is not None
        failed_lines = [l for l in out.splitlines() if l.startswith("FAIL")]
        if "Traceback" in out and "SELFTEST_" not in out:
            verdict = "BROKEN"
        elif rc == 0:
            verdict = "MISSED"
        elif expect_cond is None:
            verdict = "RED_UNNAMED"
        elif named:
            verdict = "DETECTED"
        else:
            verdict = "RED_ELSEWHERE"
        results[name] = verdict
        print(f"{name:32s} {verdict:14s} rc={rc} 紅的條={failed_lines}")
        src_path.write_text(clean)

    rc, out = run(wt)
    print(f"[還原後] rc={rc} pass={'SELFTEST_PASS' in out}")
    print("RESULTS", results)
    print("ALL_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
