#!/usr/bin/env python3
"""R492 突變體帳：每個突變體都要有**看得見它的**判準，且判準要挑「那個會變的量」
（不准只寫 rc≠0——放錯目錄害 import 失敗也是 rc≠0）。"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "ops" / "gain" / "r492_conjunct_informativeness.py"

# (突變體, 說明, 判準 fn(clean_out, mut_out, rc) -> (ok, 實測描述))
CASES = [
    ("M1", "判決詞彙表的期望值被改壞（模擬 verdict() 漂移）",
     lambda c, m, rc: (m is not None and m["verdict"] == "CENSUS_BROKEN"
                       and any("VERDICT_VOCAB_DRIFT" in b for b in m["blockers"]),
                       f"verdict={None if m is None else m['verdict']} "
                       f"blockers={None if m is None else m['blockers']}")),
    ("M2", "狀態空間砍到 n_d<=5（負對照該瞎掉）",
     lambda c, m, rc: (m is not None and m["calibration"]["C_NEG"]["class"] != "EVALUABLE",
                       f"C_NEG={None if m is None else m['calibration']['C_NEG']['class']}")),
    ("M3", "G-LIVE 擋門拿掉（selftest B 該紅）",
     None),   # 由 selftest 判，見下
    ("M4", "分類器永遠找不到反例（什麼都判 FORCED）",
     lambda c, m, rc: (m is not None and m["calibration"]["C_NEG"]["class"] == "FORCED_BY_OTHERS",
                       f"C_NEG={None if m is None else m['calibration']['C_NEG']['class']}")),
]


def run_tool(mutant: str, extra=()):
    env = dict(os.environ)
    if mutant:
        env["R492_MUTANT"] = mutant
    out = ROOT / "ops" / "gain" / "data" / f"_r492_mut_{mutant or 'clean'}.json"
    p = subprocess.run([sys.executable, str(TOOL), "--json", str(out), *extra],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    data = None
    if out.exists():
        try:
            data = json.loads(out.read_text())
        except Exception:
            data = None
    return p.returncode, data, p.stdout + p.stderr


def main() -> int:
    # M1 需要改期望值常數，改用 env 注入到工具的 EXPECTED_VERDICTS 不方便
    # ⇒ 改成獨立的原始碼突變（照檔案裡的字元寫，不是照執行後的字串寫）
    src = TOOL.read_text()
    rows, bad = [], 0

    clean_rc, clean, _ = run_tool("")
    if clean is None:
        print("BASELINE_BROKEN: 乾淨版跑不出 json")
        return 2
    rows.append(("clean", "乾淨基線", clean["verdict"] == "CENSUS_OK",
                 f"verdict={clean['verdict']} states={clean['n_states_scanned']}"))

    # --- M1：原始碼突變（把期望詞彙表換掉），驗「old 真的在檔案裡」
    old = 'EXPECTED_VERDICTS = {"ON_WINS", "RULED_OUT", "UNINFORMATIVE",'
    if old not in src:
        print("BASELINE_BROKEN: M1 的突變字串不在原始碼裡")
        return 2
    mut_path = TOOL.parent / "_r492_mutant_m1.py"
    mut_path.write_text(src.replace(old, 'EXPECTED_VERDICTS = {"ON_WINS_TYPO", "RULED_OUT", "UNINFORMATIVE",'))
    try:
        o = ROOT / "ops" / "gain" / "data" / "_r492_mut_M1.json"
        p = subprocess.run([sys.executable, str(mut_path), "--json", str(o)],
                           cwd=ROOT, capture_output=True, text=True)
        m1 = json.loads(o.read_text()) if o.exists() else None
        ok, desc = CASES[0][2](clean, m1, p.returncode)
        rows.append(("M1", CASES[0][1], ok, desc))
    finally:
        mut_path.unlink(missing_ok=True)

    # --- M2 / M4：env 旗標（在函式內部讀）
    for code, desc_txt, judge in (CASES[1], CASES[3]):
        rc, data, _ = run_tool(code)
        ok, desc = judge(clean, data, rc)
        rows.append((code, desc_txt, ok, desc))

    # --- M3：G-LIVE 擋門，判準＝selftest 的 B 條該紅（不是 rc≠0 而已）
    env = dict(os.environ); env["R492_MUTANT"] = "M3"
    p = subprocess.run([sys.executable, str(TOOL), "--selftest"],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    ok = "B: G-LIVE 沒擋住主 run" in p.stdout
    rows.append(("M3", CASES[2][1], ok, f"selftest 輸出含具名 B 條失敗={ok}"))

    for code, d, ok, desc in rows:
        print(f"{'OK ' if ok else 'BAD'} {code:<6} {d:<44} {desc}")
        bad += 0 if ok else 1
    print(f"{len(rows)-bad}/{len(rows)} behaved as prereg'd")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
