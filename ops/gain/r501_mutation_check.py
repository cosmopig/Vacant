#!/usr/bin/env python3
"""R501 突變表（判準 §五）。乾淨判決預期＝`POSITION_SURVIVES`（判準 §二），
所以表上只放「翻離 POSITION_SURVIVES 或觸發指名 blocker」的突變體。

判準 §五 明文：**crash 收場不算偵測到**，每格要吐出指名的那個字串／量。

用法：python3 ops/gain/r501_mutation_check.py [--json <path>]
"""
from __future__ import annotations
import argparse, json, os, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = "ops/gain/r501_dual_constrained_ladder.py"

# (代號, 預期被哪個量看見)  kind: "blocker" -> 該字串必須出現在 blockers；"headline" -> 兩支都要翻成該值
MUTANTS = [
    ("M1_ONE_POSITION", "blocker", "BROKEN_WINDOWS"),
    ("M2_R498_EDGES", "blocker", "BROKEN_EQSPAN"),
    ("M3_PIN_SHIFT", "blocker", "BROKEN_PINNED"),
    ("M4_FORCE_SAME", "headline", "POSITION_GONE"),
    ("M5_CLUSTERED", "blocker", "BROKEN_DISPERSION"),
]


def run_one(mut: str):
    env = dict(os.environ)
    if mut:
        env["R501_MUTANT"] = mut
    else:
        env.pop("R501_MUTANT", None)
    p = subprocess.run([sys.executable, TOOL], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=900)
    if p.returncode != 0:
        return {"crashed": True, "rc": p.returncode, "stderr": p.stderr.strip()[-400:]}
    try:
        return {"crashed": False, **json.loads(p.stdout)}
    except Exception as e:
        return {"crashed": True, "rc": p.returncode, "stderr": f"unparsable stdout: {e}"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    a = ap.parse_args()
    out = {"tool": TOOL, "clean": None, "mutants": {}, "n_detected": 0, "n_crashed": 0}

    clean = run_one("")
    out["clean"] = {k: clean.get(k) for k in ("verdict", "blockers", "headlines", "disp",
                                              "span_spread", "pin_match", "crashed")}
    # 判準 §二：乾淨那格必須真的是 POSITION_SURVIVES，否則整張表的方向前提不成立
    out["clean_direction_ok"] = (not clean.get("crashed")
                                 and clean.get("verdict") == "DUALWIN_OK"
                                 and set((clean.get("headlines") or {}).values()) == {"POSITION_SURVIVES"})

    for mut, kind, want in MUTANTS:
        r = run_one(mut)
        rec = {"kind": kind, "expected": want, "crashed": r.get("crashed", False),
               "verdict": r.get("verdict"), "blockers": r.get("blockers"),
               "headlines": r.get("headlines"), "disp": r.get("disp"),
               "span_spread": r.get("span_spread"), "pin_match": r.get("pin_match")}
        if rec["crashed"]:
            rec["result"] = "BROKEN"          # crash 不算偵測到
            out["n_crashed"] += 1
        elif kind == "blocker":
            rec["result"] = "DETECTED" if want in (r.get("blockers") or []) else "MISSED"
        else:
            hl = set((r.get("headlines") or {}).values())
            rec["result"] = "DETECTED" if hl == {want} else "MISSED"
        if rec["result"] == "DETECTED":
            out["n_detected"] += 1
        out["mutants"][mut] = rec

    out["n_mutants"] = len(MUTANTS)
    if a.json:
        p = ROOT / a.json
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"clean_direction_ok": out["clean_direction_ok"],
                      "n_detected": out["n_detected"], "n_mutants": out["n_mutants"],
                      "n_crashed": out["n_crashed"],
                      "results": {k: v["result"] for k, v in out["mutants"].items()}},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
