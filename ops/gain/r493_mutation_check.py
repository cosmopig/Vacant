#!/usr/bin/env python3
"""R493 突變體檢查：五個突變體**全部是真的原始碼突變**（判準 §五只要求 M1/M4/M5 是，
本檔做得更緊：M2/M3 也是真突變，避開 r473「檔內旗標答不了『整段刪掉會不會紅』」的通則）。

每個突變體另存成 ops/gain/_r493_mut_<id>.py（**與正式腳本同一個 import 環境**，
memory：突變體放錯目錄害 import 失敗也是 rc≠0＝infra 壞掉被誤判成有牙齒），
並先斷言 `old in src`（memory：突變字串要照檔案裡的字元寫）。

判準要寫「偵測器該看到的那個量」，不准只寫 rc≠0（memory 鐵律）。
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "r493_appendix_prose_census.py"

MUTANTS = [
    ("M1_drop_on_wins",
     '''    want = {"NON_INFERIOR_BUT_UNRESOLVED", "ON_WINS", "RULED_OUT", "UNINFORMATIVE"}''',
     '''    want = {"NON_INFERIOR_BUT_UNRESOLVED", "RULED_OUT", "UNINFORMATIVE"}''',
     "B1-1 的期望詞彙表少一個判決名"),
    ("M2_drop_cneg",
     '''    ("C_NEG", c_C2_1, "REFUTED"),      # C2-1 的刻意錯版，mut="C_NEG" 觸發''',
     '''''',
     "拿掉負向校準控制"),
    ("M3_no_glive",
     '''    if LIVE in str(rel):
        _live_reads += 1
        raise RuntimeError(f"G-LIVE: 拒絕碰主 run 的路徑：{rel}")''',
     '''    if False:
        _live_reads += 1
        raise RuntimeError(f"G-LIVE: 拒絕碰主 run 的路徑：{rel}")''',
     "拿掉 G-LIVE 硬擋門"),
    ("M4_lineno_blind",
     '''    ok = ("def main" in blk or "sys.argv[1]" in blk)''',
     '''    ok = True''',
     "E2-2 的行號形狀檢查改成恆真"),
    ("M5_drop_claim",
     '''    ("H2-1",  "附錄 H.2", "evidence", c_H2_1),''',
     '''''',
     "刪掉一條宣稱（17 -> 16）"),
]


def _run(path: Path) -> tuple[dict | None, int, str]:
    """⚠ `--json` 的目的地**不能**是 stdout：工具自己也往 stdout 印表格，兩者會混在一起
    （memory 記過的同一型坑：`run <名字> <dest>` 的 dest 不能跟 `--json` 同一個檔）。
    本函式第一版寫 `/dev/stdout`，當場 JSONDecodeError。"""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        jp = Path(td) / "out.json"
        r = subprocess.run([sys.executable, str(path), "--json", str(jp)],
                           cwd=SRC.parents[2], capture_output=True, text=True, timeout=600)
        if not jp.is_file():
            return None, r.returncode, r.stderr
        try:
            return json.loads(jp.read_text(encoding="utf-8")), r.returncode, r.stderr
        except Exception:
            return None, r.returncode, r.stderr


def _baseline() -> dict:
    out, rc, err = _run(SRC)
    if out is None:
        raise SystemExit(f"BASELINE_BROKEN rc={rc} {err[:200]}")
    return out


def main() -> int:
    src = SRC.read_text(encoding="utf-8")
    base = _baseline()
    results, bad = [], []

    # M0：乾淨基線
    ok0 = (base["verdict"] == "CENSUS_OK" and base["n_claims_scanned"] == 17
           and base["live_reads"] == 0
           and base["controls"]["C_NEG"]["got"] == "REFUTED"
           and base["controls"]["C_POS"]["got"] == "VERIFIED")
    results.append(("M0_clean", ok0,
                    f'verdict={base["verdict"]} n={base["n_claims_scanned"]} '
                    f'stale={base["premise_stale_ids"]} live_reads={base["live_reads"]}'))
    if not ok0:
        bad.append("M0_clean")

    base_stale = set(base["premise_stale_ids"])

    for mid, old, new, desc in MUTANTS:
        if old not in src:                       # 唯一擋門：突變字串必須照檔案裡的字元寫
            results.append((mid, False, f"BROKEN：`old` 不在原始碼裡（{desc}）"))
            bad.append(mid)
            continue
        mp = HERE / f"_r493_mut_{mid}.py"
        mp.write_text(src.replace(old, new, 1), encoding="utf-8")
        try:
            out, rc, err = _run(mp)
            if out is None:
                # crash 收場不算偵測到（memory：判準要寫該吐哪個 verdict 字串）
                detected, note = False, f"BROKEN：突變體 crash rc={rc} {err.strip()[:120]}"
            elif mid == "M1_drop_on_wins":
                row = next(c for c in out["claims"] if c["id"] == "B1-1")
                detected = row["status"] == "REFUTED"
                note = f'B1-1 status={row["status"]}（期望 REFUTED）'
            elif mid == "M2_drop_cneg":
                detected = out["verdict"] == "BROKEN_CALIBRATION"
                note = f'verdict={out["verdict"]}（期望 BROKEN_CALIBRATION）blockers={out["blockers"]}'
            elif mid == "M3_no_glive":
                # 該看到的量：G-LIVE 拿掉之後，selftest 的 B 條（正對照）必須紅
                st = subprocess.run([sys.executable, str(mp), "--selftest"],
                                    cwd=SRC.parents[2], capture_output=True, text=True, timeout=600)
                detected = ("G-LIVE 沒有擋下主 run 路徑" in st.stdout)
                note = f'selftest 說：{[l.strip() for l in st.stdout.splitlines() if "G-LIVE" in l]}'
            elif mid == "M4_lineno_blind":
                detected = ("E2-2" in base_stale) and ("E2-2" not in set(out["premise_stale_ids"]))
                note = (f'stale：乾淨={sorted(base_stale)} 突變後={sorted(out["premise_stale_ids"])}'
                        f'（期望 E2-2 從 stale 消失）')
            elif mid == "M5_drop_claim":
                detected = out["verdict"] == "BROKEN_SCAN_COUNT" and out["n_claims_scanned"] == 16
                note = f'verdict={out["verdict"]} n={out["n_claims_scanned"]}（期望 BROKEN_SCAN_COUNT/16）'
            else:
                detected, note = False, "沒有預註冊的判準"
        finally:
            mp.unlink(missing_ok=True)
        results.append((mid, detected, note))
        if not detected:
            bad.append(mid)

    for mid, ok, note in results:
        print(f'  {"PASS" if ok else "FAIL"}  {mid:<20} {note}')
    print(f'{len(results) - len(bad)}/{len(results)} behaved as prereg\'d')
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
