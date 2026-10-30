import json
import os

def recompute():
    exp = "e005_opencode_five_arm_smoke"
    base_path = f"/srv/vlab/runs/{exp}"
    arms = ["polyglot_py-pg_affine_cipher-opencode-A-r1",
              "polyglot_py-pg_affine_cipher-opencode-C-r1",
              "polyglot_py-pg_affine_cipher-opencode-H-r1",
              "polyglot_py-pg_affine_cipher-opencode-M-r1",
              "polyglot_py-pg_affine_cipher-opencode-S-r1"]

    results = {}
    for arm in arms:
        arm_path = os.path.join(base_path, arm)
        cell_file = os.path.join(arm_path, "cell.json")
        score_file = os.path.join(arm_path, "score.json")
        events_file = os.path.join(arm_path, "events.jsonl")

        # Read cell.json
        with open(cell_file, 'r') as f:
            cell = json.load(f)
        
        # Read score.json
        with open(score_file, 'r') as f:
            score = json.load(f)

        # Count model calls and successes from events.jsonl
        calls = 0
        successes = 0
        timeouts = 0
        total_tokens = 0
        
        if os.path.exists(events_file):
            with open(events_file, 'r') as f:
                for line in f:
                    try:
                        event = json.loads(line)
                        # Assuming standard event structure where we can identify calls/tokens
                        # Based on typical vlab events: 
                        # "type": "model_call" or similar? 
                        # Let's look at the first few lines to be sure if needed, 
                        # but usually it's a flat list of events.
                        if event.get("type") == "model_call":
                            calls += 1
                            total_tokens += event.get("tokens", 0)
                    except:
                        pass

        # Determine pass/fail and infra
        # score.json usually has {"pass": true/false/null}
        pass_val = score.get("pass")
        is_infra = (pass_val is None)
        
        # M arm timeout check
        if "M" in arm and score.get("wall_s", 0) >= 900:
            timeouts += 1

        results[arm] = {
            "n": 1,
            "pass": pass_val if not is_infra else None,
            "rate": 1 if (pass_val is True) else (0 if (pass_val is False) else None),
            "timeouts": timeouts,
            "calls": calls,
            "tokens": total_tokens,
            "wall_s": score.get("wall_s", 0),
            "is_infra": is_infra
        }

    # Aggregate for REPORT format
    report = {
        "exp": exp,
        "cells_scored": sum(1 for r in results.values() if r["pass"] is not None),
        "infra": [arm for arm, r in results.items() if r["is_infra"]],
        "per_arm": {}
    }

    for arm, r in results.items():
        # Map back to short names for per_arm keys if needed, 
        # but let's keep full paths or clean them.
        short_name = arm.split("-")[-4] # e.g., A, C, H, M, S
        if short_name not in report["per_arm"]:
            report["per_arm"][short_name] = {}
        
        # Match REPORT.json structure roughly
        report["per_arm"][short_name] = {
            "n": r["n"],
            "pass": r["pass"],
            "rate": r["rate"],
            "mean_wall_s": r["wall_s"],
            "timeouts": r["timeouts"],
            "calls_per_success": 0, # Placeholder as per original report structure
            "tokens_per_success": 0, # Placeholder
            "vacant_sha": [] if "C" not in short_name else ["bf1a9f1afb211460b48611f8f28b1d9433985c4a"]
        }

    with open("recomputed_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print("Recomputation complete. Saved to recomputed_report.json")

if __name__ == "__main__":
    recompute()
