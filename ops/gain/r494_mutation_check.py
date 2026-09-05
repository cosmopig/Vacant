#!/usr/bin/env python3
"""R494 突變體檢查：每個突變體都要有看得見它的判準（判準 §五 P-6）。

判準寫死每個突變體「該讓哪個量變」——不准只寫 rc!=0（memory：突變體放錯目錄害 import
失敗也是 rc!=0）。crash 收場一律算 BROKEN，不算偵測到。
"""
import json, os, subprocess, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = "ops/gain/r494_r486_r490_census.py"

# (旗標, 該變的量, 判準：clean -> mutant)
CASES = [
    ("M1_STOP_AFTER_FIRST", "n_unreachable", "clean==0 ⇒ 突變後 >0（搜尋被砍到只剩一次）"),
    ("M2_ALWAYS_EVALUABLE", "n_forced_green", "校準 C_POS 必須不再是 FORCED_GREEN ⇒ BROKEN"),
    ("M3_ALWAYS_FORCED", "verdict", "校準 C_NEG 必須不再是 EVALUABLE ⇒ BROKEN"),
    ("M4_DROP_CONSTRUCTIVE", "n_unreachable", "拿掉構造關 ⇒ 回到 4（承重牆）"),
]


def run(env_flag):
    env = dict(os.environ)
    if env_flag:
        env["R494_MUTANT"] = env_flag
    else:
        env.pop("R494_MUTANT", None)
    out = ROOT / "ops/gain/data/_r494_mut.json"
    p = subprocess.run([sys.executable, str(ROOT / TOOL), "--json", "ops/gain/data/_r494_mut.json"],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    if p.returncode != 0:
        return {"_crash": True, "rc": p.returncode, "stderr": p.stderr[-400:]}
    return json.loads(out.read_text())


def main():
    clean = run(None)
    if clean.get("_crash"):
        print("BROKEN: 乾淨基線就 crash", clean)
        return 2
    print(f"clean: verdict={clean['verdict']} unreachable={clean['n_unreachable']} "
          f"forced_green={clean['n_forced_green']} calib={clean['calibration']}")
    ok = 0
    for flag, key, rule in CASES:
        m = run(flag)
        if m.get("_crash"):
            print(f"  {flag:24s} BROKEN(crash rc={m['rc']}) — 不算偵測到")
            continue
        if flag == "M1_STOP_AFTER_FIRST":
            hit = m["n_unreachable"] > clean["n_unreachable"]
            got = f"unreachable {clean['n_unreachable']}->{m['n_unreachable']}"
        elif flag == "M2_ALWAYS_EVALUABLE":
            hit = m["verdict"] == "BROKEN" and m["calibration"]["C_POS"] != "FORCED_GREEN"
            got = f"verdict={m['verdict']} calib={m['calibration']}"
        elif flag == "M3_ALWAYS_FORCED":
            hit = m["verdict"] == "BROKEN" and m["calibration"]["C_NEG"] != "EVALUABLE"
            got = f"verdict={m['verdict']} calib={m['calibration']}"
        else:
            hit = m["n_unreachable"] == 4
            got = f"unreachable={m['n_unreachable']}"
        ok += hit
        print(f"  {flag:24s} {'DETECTED' if hit else 'MISSED  '}  {got}   [{rule}]")
    print(f"{ok}/{len(CASES)} behaved as prereg'd")
    return 0 if ok == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
