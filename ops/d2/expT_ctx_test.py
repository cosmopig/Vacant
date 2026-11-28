#!/usr/bin/env python3
"""B4 上下文用完判定的合成測試（2026-11-28；cc-s08 r4/r5 誤判後補）。用法：expT_ctx_test.py OUT.json"""
import json, pathlib, sys
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from ops.d2 import expTc_confirm_analysis as A  # noqa: E402
CASES = [
    ("pi_length", '{"message":{"stopReason":"length"}}', (True, False)),
    ("lmstudio_ctx_only", '{"message":{"stopReason":"error","errorMessage":"Context size has been exceeded."}}', (True, False)),
    ("lmstudio_ctx_plus_other_error", '{"errorMessage":"Context size has been exceeded."}\n{"errorMessage":"connect ECONNREFUSED"}', (True, True)),
    ("endpoint_error_only", '{"message":{"stopReason":"error","errorMessage":"connect ECONNREFUSED"}}', (False, True)),
    ("clean", '{"message":{"stopReason":"stop"}}', (False, False)),
]
rows = []; ok_all = True
for cid, txt, exp in CASES:
    got = A.classify_model_stop(txt); ok = got == exp; ok_all &= ok
    rows.append({"case": cid, "expected": list(exp), "got": list(got), "pass": ok})
    print(("PASS " if ok else "FAIL ") + f"{cid:32s} exp={exp} got={got}")
pathlib.Path(sys.argv[1]).write_text(json.dumps({"all_pass": ok_all, "cases": rows}, indent=1))
print("ALL PASS" if ok_all else "NOT ALL PASS"); sys.exit(0 if ok_all else 1)
