"""R476 的外部植入缺陷測試（源碼級突變，跑在 /dev/shm 的獨立複本上）。

為什麼是外部、源碼級：檔內 `R476_MUTANT` env 旗標答不了「把正式那段**刪掉**會不會紅」
（r473 記過；r475 §5 又踩過一次「突變字串要照檔案裡的字元寫」）。

判準（DECISION_20260904_R476 §五 雙向校準的延伸；R476b 施工時補寫，**在跑之前**）：
  - 突變體必須讓 `--selftest` **rc≠0**，且紅的那一條要**指名**是預期的那一條；
  - crash 收場記 BROKEN，**不算 caught**（R475 §5 的同一條規則）；
  - `old not in clean` ⇒ 記 BROKEN（突變沒生效，長得跟「偵測條沒牙齒」一模一樣）；
  - **承重牆**（`--loadbearing`）：把那一條整段刪掉再跑同一個突變體 ⇒ 應回到 MISSED。
    仍是紅的就記 `STILL_RED_ELSEWHERE` 並**指名**是誰蓋住的，不回退、不改判準。
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys

REL = "ops/gain/r476_closing_arbiter_drift.py"
PREREG_REL = "DECISION_20260904_R461_LCB3_REPLICATION_PREREG.md"   # 工具的 PREREG 指向 R461（附錄逐字期望值住在那裡）

MUTANTS = {
    # M1：投影擋門整段拿掉 ⇒「夾具沒讀到」又會被記成工具漂移（本輪要修的正是這個）
    "M1_projection_gate_off": (
        '    if direction in ("EXACT", "MORE_CHECKS_SAFE") and MUTANT != "M6_projection_gate_off":\n'
        '        missing = sorted(k for k, v in expected.items()\n'
        '                         if v is not None and observed.get(k) is None)\n'
        '        if missing:\n'
        '            return {"item": item, "box": "BROKEN",\n'
        '                    "why": f"BROKEN_PROJECTION：夾具沒有讀到 {missing}（不是工具漂移）",\n'
        '                    "missing": missing}\n',
        '',
        "M_projection_none_is_broken"),
    # M2：投影擋門忘了寫邊界，對 MORE_STRICT_SAFE 也生效
    #     ⇒ R472 擋門「BROKEN 時不吐能力數字」這個**訊號**會被誤記成夾具缺陷
    "M2_projection_gate_no_boundary": (
        '    if direction in ("EXACT", "MORE_CHECKS_SAFE") and MUTANT != "M6_projection_gate_off":',
        '    if True:',
        "O_strict_withheld_is_still_safe"),
    # M3：浮點容差開到無限大 ⇒ 任何數字差異都判成「一樣」（正對照失效）
    "M3_float_tolerance_blown": (
        "            return abs(float(a) - float(b)) < 5e-3",
        "            return abs(float(a) - float(b)) < 5e9",
        "B_exact_diff_is_unsafe"),
    # M4：條數變**少**也算 safe（漂移方向判反 ⇒ 少了擋門會被寫成「更嚴格」）
    "M4_fewer_checks_called_safe": (
        '                and (observed.get("n_checks") or 0) > expected["n_checks"]',
        '                and (observed.get("n_checks") or 0) != expected["n_checks"]',
        "D_fewer_checks_is_unsafe"),
    # M5：G-LIVE 擋門拿掉 ⇒ 主 run 會被讀（判準 §〇.1 的合法性前提）
    "M5_live_gate_off": (
        '            raise RuntimeError(f"G-LIVE：本輪不准碰主 run（{p}）")',
        '            pass',
        "I_live_gate_bites"),
    # M6：B-LIT 擋門恆真 ⇒ 期望值可以不在預註冊原文裡（＝可以事後編造基準）
    "M6_lit_gate_toothless": (
        '        out[k] = all(bool(l) and (l in text) for l in meta["lits"])',
        '        out[k] = True',
        "K_lit_gate_bites"),
    # 負對照：語法壞掉 ⇒ BROKEN／RED_UNNAMED，不算 caught
    "N1_syntax": ("def selftest() -> int:", "def selftest( -> int:", None),
}

# 承重牆：每個突變體對應要刪掉的那一條（逐字；memory：刪除段落要含所有參照被刪變數的行）
CONDITION_SRC = {
    "M_projection_none_is_broken": (
        '    ck("M_projection_none_is_broken",\n'
        '       classify("t", {"rows": 360}, {"rows": None}, "EXACT")["box"], "BROKEN")\n'),
    "O_strict_withheld_is_still_safe": (
        '    ck("O_strict_withheld_is_still_safe",\n'
        '       classify("t", {"verdict": "OK", "pct": 28.571},\n'
        '                {"verdict": "BROKEN_ROW_ACCOUNTING", "pct": None},\n'
        '                "MORE_STRICT_SAFE")["box"], "DRIFTED_SAFE")\n'),
    "B_exact_diff_is_unsafe": (
        '    ck("B_exact_diff_is_unsafe",\n'
        '       classify("t", e, {**e, "x": 2.5}, "EXACT")["box"], "DRIFTED_UNSAFE")\n'),
    "D_fewer_checks_is_unsafe": (
        '    ck("D_fewer_checks_is_unsafe",\n'
        '       classify("t", {"n_checks": 14, "pass": True},\n'
        '                {"n_checks": 12, "pass": True}, "MORE_CHECKS_SAFE")["box"], "DRIFTED_UNSAFE")\n'),
    "I_live_gate_bites": (
        '    hit = False\n'
        '    try:\n'
        '        guard_live([f"runs/{LIVE}/rows.jsonl"])\n'
        '    except RuntimeError:\n'
        '        hit = True\n'
        '    ck("I_live_gate_bites", hit, True)\n'),
    "K_lit_gate_bites": (
        '    ck("K_lit_gate_bites",\n'
        '       lits_in_prereg(PREREG.read_text(encoding="utf-8"),\n'
        '                      {"fake": {"lits": ["這句話不在預註冊裡_zzz"]}})["fake"], False)\n'),
}


def build_worktree(wt: pathlib.Path, root: pathlib.Path) -> None:
    if wt.exists():
        shutil.rmtree(wt)
    (wt / "ops" / "gain").mkdir(parents=True)
    shutil.copy2(root / REL, wt / REL)
    shutil.copy2(root / PREREG_REL, wt / PREREG_REL)


def run(wt: pathlib.Path) -> tuple[int, str]:
    p = subprocess.run([sys.executable, str(wt / REL), "--selftest"],
                       capture_output=True, text=True, cwd=str(wt), timeout=300)
    return p.returncode, p.stdout + p.stderr


def failed_names(out: str) -> list[str]:
    for ln in out.splitlines():
        if ln.startswith("SELFTEST_FAIL "):
            return [x for x in ln[len("SELFTEST_FAIL "):].split(",") if x]
    return []


def verdict_of(rc: int, out: str, expect_cond: str | None) -> tuple[str, list]:
    names = failed_names(out)
    if "Traceback" in out and "SELFTEST_" not in out:
        return "BROKEN", names
    if rc == 0:
        return "MISSED", names
    if expect_cond is None:
        return "RED_UNNAMED", names
    if expect_cond in names:
        return "DETECTED", names
    return "RED_ELSEWHERE", names


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worktree", default="/dev/shm/r476wt")
    ap.add_argument("--loadbearing", action="store_true")
    a = ap.parse_args()
    root = pathlib.Path(__file__).resolve().parents[2]
    wt = pathlib.Path(a.worktree).resolve()
    build_worktree(wt, root)
    src_path = wt / REL
    clean = src_path.read_text(encoding="utf-8")

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
            print(f"{name:32s} BROKEN  （突變字串對不上正式碼＝突變沒生效）")
            results[name] = "BROKEN"
            continue
        mutated = clean.replace(old, new, 1)
        src_path.write_text(mutated, encoding="utf-8")
        rc, out = run(wt)
        v, names = verdict_of(rc, out, expect_cond)
        results[name] = v
        print(f"{name:32s} {v:16s} rc={rc} 紅的條={names}")

        if a.loadbearing and expect_cond and v == "DETECTED":
            seg = CONDITION_SRC.get(expect_cond)
            if not seg or seg not in mutated:
                lb[name] = "BROKEN_NO_SEGMENT"
            else:
                src_path.write_text(mutated.replace(seg, "", 1), encoding="utf-8")
                rc2, out2 = run(wt)
                v2, names2 = verdict_of(rc2, out2, expect_cond)
                lb[name] = ("MISSED_AS_PREDICTED" if v2 == "MISSED"
                            else f"STILL_RED:{v2}:{names2}")
            print(f"    └ 承重牆（刪掉 {expect_cond}）→ {lb[name]}")
        src_path.write_text(clean, encoding="utf-8")

    rc, out = run(wt)
    print(f"[還原後] rc={rc} pass={'SELFTEST_PASS' in out}")
    print("RESULTS", results)
    if a.loadbearing:
        print("LOADBEARING", lb)
    print("ALL_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
