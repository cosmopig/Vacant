import json
from pathlib import Path

def recompute():
    exp = "e007_dabench_smoke"
    base_path = Path(f"/srv/vlab/runs/{exp}")
    arms = [d for d in base_path.iterdir() if d.is_dir()]
    
    results = {}
    for arm in arms:
        arm_name = arm.name
        cell_file = arm / "cell.json"
        score_file = arm / "score.json"
        events_file = arm / "events.jsonl"
        
        if not cell_file.exists():
            continue
            
        with open(cell_file, 'r') as f:
            data = json.load(f)
            
        cells = [data] if "cells" not in data else data["cells"]

        n = 0
        pass_count = 0
        timeouts = 0
        calls_total = 0
        tokens_total = 0
        calls_success = 0
        tokens_success = 0
        infra_count = 0
        
        for cell in cells:
            n += 1
            # Check if it's infra (score.pass is null)
            # In this experiment, score seems to be a separate file or missing from cell.json
            # Let's check the score_file instead for "pass"
            if score_file.exists():
                with open(score_file, 'r') as f:
                    score_data = json.load(f)
                    is_infra = score_data.get("pass") is None
            else:
                is_infra = False # Default if no score file

            if is_infra:
                infra_count += 1
                continue
            
            metrics = cell.get("metrics", {})
            calls_total += metrics.get("model_calls", 0)
            tokens_total += metrics.get("input_tokens", 0) + metrics.get("output_tokens", 0)
            
            # Success is agent_rc == 0
            if cell.get("agent_rc") == 0:
                pass_count += 1
                calls_success += metrics.get("model_calls", 0)
                tokens_success += metrics.get("input_tokens", 0) + metrics.get("output_tokens", 0)
            else:
                # Failed but not infra
                pass
            
            if cell.get("timed_out"):
                timeouts += 1

        results[arm_name] = {
            "n": n,
            "pass": pass_count,
            "timeouts": timeouts,
            "calls_total": calls_total,
            "tokens_total": tokens_total,
            "calls_success": calls_success,
            "tokens_success": tokens_success,
            "infra": infra_count
        }

    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    recompute()
