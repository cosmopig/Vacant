import json
import os

def recompute():
    exp = "e005_opencode_five_arm_smoke"
    base_path = f"/srv/vlab/runs/{exp}"
    arms = ["A", "C", "H", "M", "S"]
    results = {}

    for arm in arms:
        # Find the directory for this arm
        dir_name = None
        for d in os.listdir(base_path):
            if f"polyglot_py-pg_affine_cipher-opencode-{arm}-r1" in d:
                dir_name = d
                break
        
        if not dir_name:
            results[arm] = {"error": "directory not found"}
            continue

        path = os.path.join(base_path, dir_name)
        cell_json_path = os.path.join(path, "cell.json")
        score_json_path = os.path.join(path, "score.json")
        events_jsonl_path = os.path.join(path, "events.jsonl")

        # Read cell.json
        try:
            with open(cell_json_path, 'r') as f:
                cell = json.load(f)
        except Exception as e:
            results[arm] = {"error": f"read cell.json failed: {e}"}
            continue

        # Read score.json
        try:
            with open(score_json_path, 'r') as f:
                score = json.load(f)
        except Exception as e:
            results[arm] = {"error": f"read score.json failed: {e}"}
            continue

        # Read events.jsonl (for model calls and timeouts)
        calls = 0
        success_calls = 0
        timeouts = 0
        try:
            with open(events_jsonl_path, 'r') as f:
                for line in f:
                    event = json.loads(line)
                    if event.get("type") == "model_call":
                        calls += 1
                        # Assuming success is indicated by some field or lack of error
                        # In many cases, we check if it's a successful call
                        if event.get("status") == "success":
                            success_calls += 1
                    if event.get("type") == "timeout":
                        timeouts += 1
        except Exception as e:
            results[arm] = {"error": f"read events.jsonl failed: {e}"}
            continue

        # Determine pass/fail and infra
        pass_val = score.get("pass")
        is_infra = (pass_val is None)
        
        # Logic for n, pass, timeouts, calls, success_calls
        n = 1 # Each arm has exactly 1 cell in this smoke test
        results[arm] = {
            "n": n,
            "pass": pass_val if not is_infra else None,
            "timeouts": timeouts,
            "calls": calls,
            "success_calls": success_calls,
            "is_infra": is_infra,
            "cell_json_path": cell_json_path,
            "score_json_path": score_json_path
        }

    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    recompute()
