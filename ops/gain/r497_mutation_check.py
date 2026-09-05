#!/usr/bin/env python3
"""R497 承重牆／突變體檢查（判準 §五）。發車前必須跑，判準寫死「該變的是哪個量」。

⚠ 判準不是 rc≠0（memory：突變體放錯目錄害 import 失敗也是 rc≠0）。
⚠ 突變在被測函式**內部**生效（`_mut()` 呼叫時才讀 env）。
"""
from __future__ import annotations
import json, os, subprocess, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = "ops/gain/r497_segment_composition.py"


def run(env_extra) -> dict:
    env = dict(os.environ)
    env.update(env_extra)
    out = ROOT / "ops/gain/data/_r497_mut_tmp.json"
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
    print(f"clean: verdict={clean['verdict']}  exo_tracking={clean['exo_tracking']}")

    results = []

    # M1：只取每層 1 個位置 ⇒ G-WINDOWS
    m1 = run({"R497_MUTANT": "M1_ONE_WINDOW"})
    results.append(("M1_ONE_WINDOW", "verdict==BROKEN_WINDOWS",
                    m1.get("verdict"), m1.get("verdict") == "BROKEN_WINDOWS"))

    # M2：C_NEG 改用 ts ⇒ G-CAL
    m2 = run({"R497_MUTANT": "M2_CNEG_TIME"})
    results.append(("M2_CNEG_TIME", "verdict==BROKEN_CALIBRATION 且 C_NEG==POSITION_TRACKING",
                    f"{m2.get('verdict')} / C_NEG={m2.get('calibration', {}).get('C_NEG')}",
                    m2.get("verdict") == "BROKEN_CALIBRATION"
                    and m2.get("calibration", {}).get("C_NEG") == "POSITION_TRACKING"))

    # M3：放掉「兩層同號」只看第一層 ⇒ exo_tracking 具名清單必須改變
    m3 = run({"R497_MUTANT": "M3_RHO_ONE_TIER"})
    results.append(("M3_RHO_ONE_TIER", "exo_tracking 清單 != 乾淨版",
                    f"{m3.get('exo_tracking')} vs clean {clean['exo_tracking']}",
                    m3.get("exo_tracking") != clean["exo_tracking"]))

    # M4：注入一條來源欄位全 null 的 share 型統計量，A/B 只翻「擋門開/關」一件事
    a = run({"R497_INJECT_NULL_STAT": "1"})
    b = run({"R497_INJECT_NULL_STAT": "1", "R497_MUTANT": "M4_SWALLOW_NULL"})
    ca = a.get("stats", {}).get("INJECTED_ALL_NULL", {}).get("class")
    cb = b.get("stats", {}).get("INJECTED_ALL_NULL", {}).get("class")
    results.append(("M4_SWALLOW_NULL", "擋門開時 STAT_UNSCANNED，關掉之後必須改掉",
                    f"guard_on={ca} guard_off={cb}",
                    ca == "STAT_UNSCANNED" and cb is not None and cb != "STAT_UNSCANNED"))
    # 判準 §五 預測 guard_off 會是 NOT_TRACKING；實際值單獨記，兩個都印
    print(f"\n[M4 附記] 判準預測 guard_off==NOT_TRACKING，實際 guard_off=={cb}")
    # 注入的假統計量不得污染頭條計數
    print(f"[M4 附記] 注入後 n_exogenous={a.get('n_exogenous')} "
          f"exo_tracking={a.get('exo_tracking')} verdict={a.get('verdict')}")

    print()
    ok = 0
    for name, crit, actual, passed in results:
        print(f"  {'DETECTED' if passed else 'MISSED  '}  {name}")
        print(f"            判準：{crit}")
        print(f"            實際：{actual}")
        ok += bool(passed)
    print(f"\n{ok}/{len(results)} behaved as prereg'd")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
