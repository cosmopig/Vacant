#!/usr/bin/env python3
"""R498 承重牆／突變體檢查（判準 §五）。發車前必須跑。判準不是 rc≠0。"""
from __future__ import annotations
import json, os, subprocess, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = "ops/gain/r498_equal_chat_n.py"


def run(env_extra) -> dict:
    env = dict(os.environ)
    env.update(env_extra)
    out = ROOT / "ops/gain/data/_r498_mut_tmp.json"
    r = subprocess.run([sys.executable, TOOL, "--json", str(out)],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        return {"_rc": r.returncode, "_stderr": r.stderr[-800:]}
    d = json.loads(out.read_text(encoding="utf-8"))
    out.unlink()
    return d


def main() -> int:
    clean = run({})
    if "_rc" in clean:
        print("BROKEN: 乾淨版跑不起來", clean)
        return 2
    print(f"clean: verdict={clean['verdict']} M={clean['M']} cells={clean['cells']}")

    res = []
    m1 = run({"R498_MUTANT": "M1_ONE_POSITION"})
    res.append(("M1_ONE_POSITION", "verdict==BROKEN_WINDOWS",
                m1.get("verdict"), m1.get("verdict") == "BROKEN_WINDOWS"))

    m2 = run({"R498_MUTANT": "M2_TOTAL_ROWS"})
    res.append(("M2_TOTAL_ROWS", "verdict==BROKEN_EQCHAT",
                m2.get("verdict"), m2.get("verdict") == "BROKEN_EQCHAT"))

    m3 = run({"R498_MUTANT": "M3_FORCE_SAME"})
    cells3 = m3.get("cells", {})
    res.append(("M3_FORCE_SAME", "兩工具的 cell 都變成 NEITHER",
                f"{cells3} vs clean {clean['cells']}",
                bool(cells3) and all(v == "NEITHER" for v in cells3.values())))

    m4 = run({"R498_MUTANT": "M4_PIN_M"})
    res.append(("M4_PIN_M", "verdict==BROKEN_DERIVED",
                f"{m4.get('verdict')} M={m4.get('M')}",
                m4.get("verdict") == "BROKEN_DERIVED"))

    # ── 補充（**事後，不在判準 §五 的表上，不計入 N/4**）：
    # 判準的 M4 把 M 釘成 1672/2291，但 len(sub)=728 ⇒ IndexError ⇒ crash 不算偵測到。
    # 釘成可行的錯值 (300,500) 才答得了「G-DERIVED 有沒有牙齒」。
    m4b = run({"R498_MUTANT": "M4b_PIN_M_FEASIBLE"})
    print(f"[補充 M4b_PIN_M_FEASIBLE] verdict={m4b.get('verdict')} M={m4b.get('M')} "
          f"-> {'DETECTED' if m4b.get('verdict') == 'BROKEN_DERIVED' else 'MISSED'}"
          f"（事後補，不計入下面的 N/4）")
    if "_rc" in m4b:
        print(f"    stderr: {m4b.get('_stderr', '')[-300:]}")

    print()
    ok = 0
    for name, crit, actual, passed in res:
        print(f"  {'DETECTED' if passed else 'MISSED  '}  {name}")
        print(f"            判準：{crit}")
        print(f"            實際：{actual}")
        ok += bool(passed)
    print(f"\n{ok}/{len(res)} behaved as prereg'd")
    return 0 if ok == len(res) else 1


if __name__ == "__main__":
    sys.exit(main())
