import json
import os
from pathlib import Path

def audit():
    base_dir = Path("/srv/vlab/runs/e005_opencode_five_arm_smoke")
    arms = [
        "polyglot_py-pg_affine_cipher-opencode-A-r1",
        "polyglot_py-pg_affine_cipher-opencode-C-r1",
        "polyglot_py-pg_affine_cipher-opencode-H-r1",
        "polyglot_py-pg_affine_cipher-opencode-M-r1",
        "polyglot_py-pg_affine_cipher-opencode-S-r1",
    ]

    results = {}
    for arm in arms:
        arm_dir = base_dir / arm
        cell_path = arm_dir / "cell.json"
        score_path = arm_dir / "score.json"
        events_path = arm_dir / "events.jsonl"

        if not cell_path.exists() or not score_path.exists():
            results[arm] = {"status": "missing", "cell": cell_path.exists(), "score": score_path.exists()}
            continue

        with open(cell_path, 'r') as f:
            cell = json.load(f)
        with open(score_path, 'r') as f:
            score = json.load(f)

        # Basic metrics
        n = cell.get("n", 0)
        passed = cell.get("pass", False)
        if score.get("pass") is not None: # If it's a number or bool, but we want to check if it was actually scored
            # In some cases pass might be null in score.json even if cell has it
            pass_val = score.get("pass")
        else:
            pass_val = cell.get("pass")

        # Infra check (score.pass is null)
        infra = score.get("pass") is None

        # Model calls and tokens from events.jsonl
        model_calls = 0
        total_tokens = 0
        if events_path.exists():
            with open(events_path, 'r') as f:
                for line in f:
                    try:
                        ev = json.loads(line)
                        if ev.get("type") == "model_call":
                            model_calls += 1
                            total_tokens += ev.get("tokens", 0)
                    except:
                        pass

        # Wall time from cell.json (usually in seconds)
        wall_s = cell.get("wall_s", 0.0)

        results[arm] = {
            "n": n,
            "passed": passed,
            "agent_rc": cell.get("agent_rc"),
            "wall_s": wall_s,
            "model_calls": model_calls,
            "total_tokens": total_tokens,
            "infra": infra,
            "cell_pass": pass_val,
            "append_system": cell.get("append_system", {}).get("mode"),
            "install_rc": cell.get("install_rc")
        }

    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    audit()
