import json
import os
from pathlib import Path

def recompute_e003():
    base_dir = Path("/srv/vlab/runs/e003_opencode_smoke")
    # The 4 cells are in subdirectories
    cells = list(base_dir.glob("*-r1"))
    
    results = []
    for cell in cells:
        cell_path = Path(cell)
        cell_json = cell_path / "cell.json"
        score_json = cell_path / "score.json"
        events_jsonl = cell_path / "events.jsonl"
        
        # Basic info from cell.json
        with open(cell_json, 'r') as f:
            cell_data = json.load(f)
        
        # Score data
        score_pass = None
        if score_json.exists():
            with open(score_json, 'r') as f:
                score_data = json.load(f)
                score_pass = score_data.get("pass")
        
        # Events for model calls and success/timeout/infra
        model_calls = 0
        successes = 0
        timeouts = 0
        infra_failures = 0 # pass is null or no score.json
        
        if events_jsonl.exists():
            with open(events_jsonl, 'r') as f:
                for line in f:
                    try:
                        event = json.loads(line)
                        # We need to identify model calls vs other events
                        # Based on typical vacant/agent event structures
                        if "model" in event or "completion" in event:
                            model_calls += 1
                            if event.get("success") is True:
                                successes += 1
                            if event.get("timeout") is True:
                                timeouts += 1
                    except:
                        pass

        # Infra check: pass is null or no score.json
        if score_pass is None:
            infra_failures += 1
            
        results.append({
            "cell": str(cell.name),
            "n_model_calls": model_calls,
            "successes": successes,
            "timeouts": timeouts,
            "infra_failures": infra_failures,
            "score_pass": score_pass,
            "has_events": events_jsonl.exists()
        })

    # Print summary for manual check first
    print(f"{'Cell':<40} | {'Calls':<6} | {'Succ':<5} | {'TO':<3} | {'Infra':<5} | {'Pass':<5}")
    print("-" * 80)
    for r in results:
        pass_str = str(r['score_pass']) if r['score_pass'] is not None else "None"
        print(f"{r['cell']:<40} | {r['n_model_calls']:<6} | {r['successes']:<5} | {r['timeouts']:<3} | {r['infra_failures']:<5} | {pass_str:<5}")

    # Also write to a file for the audit
    with open("recompute_results.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    recompute_e003()
