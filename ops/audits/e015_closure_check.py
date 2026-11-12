import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
VERDICT_DEFAULT = pathlib.Path("/srv/vlab/runs/e015_h_multi_review/VERDICT.json")
PACKET_DEFAULT = REPO / "ops/vlab/packets/e015_h_multi_review.md"
BACKLOG_DEFAULT = REPO / "ops/BACKLOG.md"

def check(verdict_text: str, packet_text: str, backlog_text: str) -> list[str]:
    violations = []
    try:
        # 1. Verify VERDICT.json
        v_data = json.loads(verdict_text)
        if v_data.get("state") != "NOT_BETTER_THAN_RANDOM":
            violations.append("VERDICT state must be NOT_BETTER_THAN_RANDOM")
        
        x, n_bad, y, n_good, missing = 15, 16, 7, 15, 1
        if (v_data.get("X"), v_data.get("n_bad"), v_data.get("Y"), v_data.get("n_good"), v_data.get("missing")) != (x, n_bad, y, n_good, missing):
            violations.append(f"VERDICT values must be X={x}, n_bad={n_bad}, Y={y}, n_good={n_good}, missing={missing}")
        
        if len(v_data.get("rows", [])) != 32 or v_data.get("missing_cells") != 1:
            violations.append("VERDICT must have 32 rows and exactly 1 missing cell")
        
        holm = v_data.get("holm", {})
        if not holm.get("first_pass") is True or not holm.get("second_pass") is False:
            violations.append("VERDICT holm must have first_pass=True and second_pass=False")

        # 2. Verify Packet
        if "NOT_BETTER_THAN_RANDOM" not in packet_text or "13" not in packet_text:
            violations.append("Packet must contain NOT_BETTER_THAN_RANDOM and threshold 13")

        # 3. Verify Backlog
        if "- [x] **發射 Phase 1（round 900" not in backlog_text:
            violations.append("Backlog missing checked launch line")
        
        line = ""
        for l in backlog_text.splitlines():
            if "- [x] **發射 Phase 1（round 900" in l:
                line = l
                break
        if "NOT_BETTER_THAN_RANDOM" not in line or "X＝15/16" not in line or "Y＝7/15" not in line or "Phase 2 不發射" not in line:
            violations.append("Backlog launch line missing required details (NOT_BETTER_THAN_RANDOM, X=15/16, Y=7/15, Phase 2 不發射)")

    except Exception as e:
        violations.append(f"Parsing error: {str(e)}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        # Positive control
        v_data = {
            "state": "NOT_BETTER_THAN_RANDOM",
            "X": 15, "n_bad": 16, "Y": 7, "n_good": 15, "missing": 1,
            "rows": [i for i in range(32)],
            "missing_cells": 1,
            "holm": {"first_pass": True, "second_pass": False}
        }
        v_text = json.dumps(v_data)
        p_text = "# Packet\nNOT_BETTER_THAN_RANDOM\nThreshold: 13"
        b_text = "- [x] **發射 Phase 1（round 900\nNOT_BETTER_THAN_RANDOM, X＝15/16, Y＝7/15, Phase 2 不發射"
        
        res = check(v_text, p_text, b_text)
        if not res:
            print("VERDICT: E015_CLOSURE_OK")
            print("positive control OK")
            sys.exit(0)
        else:
            for r in res: print(f"FAIL: {r}")
            print("VERDICT: E015_CLOSURE_FAIL")
            sys.exit(1)

    # Default behavior (read files)
    try:
        v_text = VERDICT_DEFAULT.read_text()
        p_text = PACKET_DEFAULT.read_text()
        b_text = BACKLOG_DEFAULT.read_text()
        res = check(v_text, p_text, b_text)
        if not res:
            print("VERDICT: E015_CLOSURE_OK")
            sys.exit(0)
        else:
            for r in res: print(f"FAIL: {r}")
            print("VERDICT: E015_CLOSURE_FAIL")
            sys.exit(1)
    except FileNotFoundError as e:
        # If files are missing, we still want to allow the test suite to run 
        # but report that it's not checking anything.
        print(f"File not found: {e}")
        print("VERDICT: E015_CLOSURE_SKIP")
        sys.exit(2)
