#!/usr/bin/env python3
"""R496 承重牆檢查：兩個突變體，判準見
DECISION_20260905_R496_EQUAL_N_WINDOW_PREREG.md §六（commit 53eb9c1）。

偵測條寫的是「哪一個具名的量必須變成什麼」，不是 rc≠0。
突變體一律跑**真快照**（同 R495 的理由：G-REPRO 排在 G-CAL 前面）。
"""
from __future__ import annotations
import json, os, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = "ops/gain/r496_equal_n_windows.py"


def census_json(mut):
    env = dict(os.environ)
    env["R496_MUTANT"] = mut
    out = pathlib.Path(f"/tmp/r496_mut_{mut}.json")
    p = subprocess.run([sys.executable, TOOL, "--json", str(out)], cwd=ROOT, env=env,
                       capture_output=True, text=True)
    try:
        return json.loads(out.read_text()), p
    except Exception:
        return None, p


def main() -> int:
    res = {}
    d, p = census_json("M1_ONE_POSITION")
    res["M1_ONE_POSITION"] = {"detected": bool(d) and d.get("verdict") == "BROKEN_WINDOWS",
                              "observed": (d or {}).get("verdict"),
                              "n_windows": (d or {}).get("n_windows"),
                              "expected": "verdict == BROKEN_WINDOWS"}
    d, p = census_json("M2_FORCE_SAME")
    res["M2_FORCE_SAME"] = {"detected": bool(d) and d.get("verdict") == "BROKEN_CALIBRATION"
                            and ((d.get("calibration") or {}).get("C_NEG") != "N_MATTERS"),
                            "observed": (d or {}).get("verdict"),
                            "C_NEG": ((d or {}).get("calibration") or {}).get("C_NEG"),
                            "expected": "verdict == BROKEN_CALIBRATION 且 C_NEG != N_MATTERS"}
    n = sum(1 for v in res.values() if v["detected"])
    print(json.dumps(res, indent=2, ensure_ascii=False))
    print(f"{n}/{len(res)} behaved as prereg'd")
    return 0 if n == len(res) else 1


if __name__ == "__main__":
    sys.exit(main())
