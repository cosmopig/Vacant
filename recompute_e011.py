import json
import os
from pathlib import Path

EXP = "e011_l001_dabench_smoke"
BASE_DIR = Path(f"/srv/vlab/runs/{EXP}")

def get_metrics(arm_suffix):
    dirs = sorted([d for d in BASE_DIR.iterdir() if arm_suffix in d.name and d.is_dir()])
    total_n = 0
    total_pass = 0
    total_calls = 0
    total_tokens = 0
    total_timeouts = 0
    
    for d in dirs:
        score_file = d / "score.json"
        if not score_file.exists():
            continue
            
        with open(score_file, 'r') as f:
            data = json.load(f)
            total_n += 1
            if data.get("pass"):
                total_pass += 1
                # We know calls_per_success and tokens_per_success are NOT in score.json or delivery.json
                # They must be calculated from events.jsonl or something else.
                # However, the REPORT.json has them. Let's see if we can find them anywhere else.
                pass

    rate = total_pass / total_n if total_n > 0 else 0
    avg_calls = 0.0
    avg_tokens = 0.0
    
    return {
        "n": total_n,
        "pass": total_pass,
        "rate": rate,
        "calls_per_success": avg_calls,
        "tokens_per_success": avg_tokens,
        "timeouts": total_timeouts
    }

if __name__ == "__main__":
    metrics_a = get_metrics("pi-A")
    metrics_c = get_metrics("pi-C")
    
    print(f"Arm A: {metrics_a}")
    print(f"Arm C: {metrics_c}")

