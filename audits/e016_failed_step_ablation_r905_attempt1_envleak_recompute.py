import json
import os
from pathlib import Path

def recompute():
    exp_dir = Path("/srv/vlab/runs/e016_failed_step_ablation_r905_attempt1_envleak")
    results = {}
    
    # Arms to check: A, C, C-nf
    arms = ["A", "C", "C-nf"]
    
    for arm in arms:
        n = 0
        pass_count = 0
        total_calls = 0
        total_timeouts = 0
        total_tokens = 0
        
    # Actually, let's just iterate over all directories and group them by arm.
    # The directory names are like 'polyglot_py-pg_affine_cipher-pi-A-r1'
    # We can extract the arm from the suffix '-pi-[ARM]-r[NUM]'
    
    arm_data = {
        "A": {"n": 0, "pass": 0, "calls": 0, "timeouts": 0, "tokens": 0},
        "C": {"n": 0, "pass": 0, "calls": 0, "timeouts": 0, "tokens": 0},
        "C-nf": {"n": 0, "pass": 0, "calls": 0, "timeouts": 0, "tokens": 0}
    }

    for d in exp_dir.iterdir():
        if d.is_dir() and "polyglot_py" in d.name:
            # Extract arm
            arm = None
            if "-pi-A-" in d.name: arm = "A"
            elif "-pi-C-nf-" in d.name: arm = "C-nf"
            elif "-pi-C-" in d.name and "-nf-" not in d.name: arm = "C"
            
            if arm and arm in arm_data:
                cell_path = d / "cell.json"
                score_path = d / "score.json"
                
                if cell_path.exists() and score_path.exists():
                    with open(cell_path, 'r') as f:
                        cell = json.load(f)
                    with open(score_path, 'r') as f:
                        score = json.load(f)
                    
                    arm_data[arm]["n"] += 1
                    if score.get("pass") is True or score.get("status") == "pass":
                        arm_data[arm]["pass"] += 1
                    
                    # Metrics from cell.json
                    metrics = cell.get("metrics", {})
                    arm_data[arm]["calls"] += metrics.get("model_calls", 0)
                    arm_data[arm]["timeouts"] += (1 if metrics.get("timed_out") else 0)
                    arm_data[arm]["tokens"] += metrics.get("input_tokens", 0) + metrics.get("output_tokens", 0)

    # Print summary for manual check first
    print(json.dumps(arm_data, indent=2))
    
    # Now calculate rates and other stats to match REPORT.json
    final_results = {}
    for arm, data in arm_data.items():
        if data["n"] > 0:
            rate = data["pass"] / data["n"]
            calls_per_success = data["calls"] / data["pass"] if data["pass"] > 0 else float('inf')
            tokens_per_success = (data["tokens"]) / data["pass"] if data["pass"] > 0 else float('inf')
            final_results[arm] = {
                "n": data["n"],
                "pass": data["pass"],
                "rate": rate,
                "calls_per_success": calls_per_success,
                "tokens_per_success": tokens_per_success,
                "timeouts": data["timeouts"]
            }
    return final_results

if __name__ == "__main__":
    res = recompute()
    print(json.dumps(res, indent=2))
