"""R475 的外部植入缺陷測試（源碼級突變，跑在獨立 worktree 上）。

為什麼是外部、源碼級：檔內 `MUTANT` env 旗標答不了「把正式那段刪掉會不會紅」
（r473 記過：模組層讀 env 的突變體永遠不生效，長得跟「偵測條沒牙齒」一模一樣）。

判準（DECISION_20260904_R475 §三 P5／P6）：
  - 突變體必須讓 `--selftest` **rc≠0**，而且紅的那一條要**指名**是預期的那一條；
  - crash 收場記 BROKEN，不算 caught（R3）；
  - **承重牆**（`--loadbearing`）：把那一條整段刪掉再跑同一個突變體 ⇒ 應回到 MISSED。
    若仍是紅的，代表**另一條**也蓋得住它——照實記 `STILL_RED_ELSEWHERE` 並指名是誰，
    不回退、不改判準（R471 先例）。
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

REL = "ops/gain/r475_oracle_sweep.py"

MUTANTS = {
    # P5 M1：把「沒量到」寫成「量到綠燈」（UNSUPPORTED_SHAPE 併進 ORACLE_ACCEPTED）
    "M1_unsupported_to_accepted": (
        'return {**out, "cls": UNSUPPORTED, "reason": str(e)}',
        'return {**out, "cls": ACCEPTED, "reason": str(e)}',
        "G_unsupported_shape"),
    # P5 M2：神諭表改成寫死一份，不追檢查式原始碼（漂移會變安靜）
    "M2_hardcode_table": (
        "    entry, table = extract_table(check_src)\n",
        "    entry, _ = extract_table(check_src)\n"
        "    table = [{'args': [1], 'expected': 2}, {'args': [3], 'expected': 4}]\n",
        "I_table_tracks_source"),
    # P5 M3：把逾時規則整段拿掉（跑不完的 check 會被記成「有擋下來」＝REJECTED）
    "M3_drop_timeout_rule": (
        '    if el >= timeout_s:\n'
        '        return {**out, "cls": UNUSABLE, "reason": "check_timeout",\n'
        '                "elapsed_s": round(el, 3)}\n',
        '',
        "D_timeout_check"),
    # P5 M4：神諭忽略 args，恆回第一筆 expected（只有多筆測資的夾具看得見）
    "M4_oracle_ignores_args": (
        "if __e['args'] == __key:",
        "if True:",
        "A_satisfiable_check"),
    # 負對照：語法壞掉 ⇒ BROKEN，不算 caught
    "N1_syntax": ("def selftest() -> int:", "def selftest( -> int:", None),
}

# P6 承重牆：每個突變體對應要刪掉的那一條（逐字，刪不到就記 BROKEN）
CONDITION_SRC = {
    "G_unsupported_shape": (
        '    want("G_unsupported_shape", _fixture("f", "assert f(1) == 2\\n"),\n'
        '         "hidden_check", UNSUPPORTED)\n'),
    "I_table_tracks_source": (
        '    src_a = oracle_source(_TBL2)[0]\n'
        '    src_b = oracle_source(_TBL2.replace("\'expected\': 4", "\'expected\': 99"))[0]\n'
        '    if "99" not in src_b or "99" in src_a or src_a == src_b:\n'
        '        failed.append(f"I_table_tracks_source: 來源改了但神諭沒變：{src_b!r}")\n'
        '    print(f"  I_table_tracks_source      {\'99\' in src_b and src_a != src_b}")\n'),
    "D_timeout_check": (
        '    want("D_timeout_check", _fixture("f", _TBL_SPIN), "hidden_check", UNUSABLE)\n'),
    "A_satisfiable_check": (
        '    want("A_satisfiable_check", _fixture("f", _TBL2), "hidden_check", ACCEPTED)\n'),
}


def run(wt: pathlib.Path) -> tuple[int, str]:
    p = subprocess.run([sys.executable, str(wt / REL), "--selftest"],
                       capture_output=True, text=True, cwd=str(wt), timeout=900)
    return p.returncode, p.stdout + p.stderr


def verdict_of(rc: int, out: str, expect_cond: str | None) -> tuple[str, list]:
    failed_lines = [l for l in out.splitlines() if l.startswith("FAIL")]
    named = expect_cond is not None and any(
        l.startswith(f"FAIL {expect_cond}") for l in failed_lines)
    if "Traceback" in out and "SELFTEST_" not in out:
        return "BROKEN", failed_lines
    if rc == 0:
        return "MISSED", failed_lines
    if expect_cond is None:
        return "RED_UNNAMED", failed_lines
    if named:
        return "DETECTED", failed_lines
    return "RED_ELSEWHERE", failed_lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worktree", required=True)
    ap.add_argument("--loadbearing", action="store_true")
    a = ap.parse_args()
    wt = pathlib.Path(a.worktree).resolve()
    src_path = wt / REL
    clean = src_path.read_text()

    rc, out = run(wt)
    base_ok = rc == 0 and "SELFTEST_PASS" in out
    print(f"[乾淨基線] rc={rc} pass={base_ok}")
    if not base_ok:
        print(out[-1200:])
        print("BASELINE_BROKEN")
        return 1

    results, lb = {}, {}
    for name, (old, new, expect_cond) in MUTANTS.items():
        if old not in clean:
            print(f"{name:28s} BROKEN  （突變字串對不上正式碼＝突變沒生效）")
            results[name] = "BROKEN"
            continue
        mutated = clean.replace(old, new, 1)
        src_path.write_text(mutated)
        rc, out = run(wt)
        v, lines = verdict_of(rc, out, expect_cond)
        results[name] = v
        print(f"{name:28s} {v:18s} rc={rc} 紅的條={lines}")

        if a.loadbearing and expect_cond and v == "DETECTED":
            seg = CONDITION_SRC.get(expect_cond)
            if not seg or seg not in mutated:
                lb[name] = "BROKEN_NO_SEGMENT"
            else:
                src_path.write_text(mutated.replace(seg, "", 1))
                rc2, out2 = run(wt)
                v2, lines2 = verdict_of(rc2, out2, expect_cond)
                lb[name] = ("MISSED_AS_PREDICTED" if v2 == "MISSED"
                            else f"STILL_RED:{v2}:{lines2}")
            print(f"    └ 承重牆（刪掉 {expect_cond}）→ {lb[name]}")
        src_path.write_text(clean)

    rc, out = run(wt)
    print(f"[還原後] rc={rc} pass={'SELFTEST_PASS' in out}")
    print("RESULTS", results)
    if a.loadbearing:
        print("LOADBEARING", lb)
    print("ALL_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
