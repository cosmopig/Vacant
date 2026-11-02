import json
import os
from pathlib import Path

def get_stats(run_dir):
    score_path = run_dir / "score.json"
    events_path = run_dir / "events.jsonl"
    cell_path = run_dir / "cell.json"
    
    if not score_path.exists():
        return None

    with open(score_path, 'r') as f:
        score = json.load(f)
    
    # In DABench, success is usually indicated by pass=True and status="ok"
    success = score.get("pass") == True and score.get("status") == "ok"
    
    calls = 0
    tokens = 0
    timeout = False
    
    if events_path.exists():
        with open(events_path, 'r') as f:
            for line in f:
                event = json.loads(line)
                # We need to be careful about which events count towards "success"
                # But for calls/success we want total calls made by the agent
                if event.get("type") == "model_call":
                    calls += 1
                if event.get("type") == "token_usage":
                    tokens += event.get("usage", {}).get("total", 0)
                if event.get("type") == "timeout":
                    timeout = True

    vacant_home_bytes = None
    if (run_dir / "delivery.json").exists():
        with open(run_dir / "delivery.json", 'r') as f:
            deliv = json.load(f)
            # vacant_home_bytes might be in delivery.json or score.json? 
            # The prompt says C arm vacant_home_bytes max/median.
            vacant_home_bytes = deliv.get("vacant_home_bytes")

    return {
        "success": success,
        "calls": calls,
        "tokens": tokens,
        "timeout": timeout,
        "vacant_home_bytes": vacant_home_bytes
    }

def main():
    base_dir = Path("/srv/vlab/runs/e013_dabench_pi_AC_full")
    results = {"A": [], "C": []}
    
    a_arms = [d for d in base_dir.iterdir() if d.name.endswith("-pi-A-r1")]
    c_arms = [d for d in base_dir.iterdir() if d.name.endswith("-pi-C-r1")]
    
    a_arms.sort()
    c_arms.sort()

    for a, c in zip(a_arms, c_arms):
        stats_a = get_stats(a)
        stats_c = get_stats(c)
        results["A"].append(stats_a)
        results["C"].append(stats_c)

    def calc_metrics(stats_list):
        valid_stats = [s for s in stats_list if s is not None]
        n = len(valid_stats)
        successes = sum(1 for s in valid_stats if s["success"])
        pass_rate = successes / n if n > 0 else 0
        
        total_calls = sum(s["calls"] for s in valid_stats)
        avg_calls_per_success = total_calls / successes if successes > 0 else float('inf')
        
        total_tokens = sum(s["tokens"] for s in valid_stats)
        avg_tokens_per_success = total_tokens / successes if successes > 0 else float('inf')
        
        timeouts = sum(1 for s in valid_stats if s["timeout"])
        
        return {
            "n": n,
            "successes": successes,
            "pass_rate": pass_rate,
            "calls_per_success": avg_calls_per_success,
            "tokens_per_success": avg_tokens_per_success,
            "timeouts": timeouts
        }

    metrics_a = calc_metrics(results["A"])
    metrics_c = calc_metrics(results["C"])

    pairings = {
        "A_only": 0, # A pass, C fail
        "C_only": 0, # C pass, A fail
        "both_pass": 0,
        "both_fail": 0
    }

    for a, c in zip(results["A"], results["C"]):
        if a is None or c is None: continue
        a_ok = a["success"]
        c_ok = c["success"]
        if a_ok and not c_ok: pairings["A_only"] += 1
        elif c_ok and not a_ok: pairings["C_only"] += 1
        elif a_ok and c_ok: pairings["both_pass"] += 1
        else: pairings["both_fail"] += 1

    c_bytes = [s["vacant_home_bytes"] for s in results["C"] if s["vacant_home_bytes"] is not None]
    max_v_bytes = max(c_bytes) if c_bytes else 0
    median_v_bytes = sorted(c_bytes)[len(c_bytes)//2] if c_bytes else 0

    print("--- Metrics ---")
    print(f"Arm A: {metrics_a}")
    print(f"Arm C: {metrics_c}")
    print("\n--- Pairings ---")
    print(json.dumps(pairings, indent=2))
    print(f"\nC Arm Vacant Home Bytes: Max={max_v_bytes}, Median={median_v_bytes}")

if __name__ == "__main__":
    main()
