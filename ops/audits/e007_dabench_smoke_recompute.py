import json
import os

def recompute():
    exp_path = "/srv/vlab/runs/e007_dabench_smoke"
    per_arm = {}
    
    # Get all folders that are arms
    folders = [f for f in os.listdir(exp_path) if os.path.isdir(os.path.join(exp_path, f))]
    
    for folder in folders:
        folder_path = os.path.join(exp_path, folder)
        cell_file = os.path.join(folder_path, "cell.json")
        score_file = os.path.join(folder_path, "score.json")
        events_file = os.path.join(folder_path, "events.jsonl")
        
        if not (os.path.exists(cell_file) and os.path.exists(score_file)):
            continue

        with open(cell_file, 'r') as f:
            cells = json.load(f)
        with open(score_file, 'r') as f:
            scores = json.load(f)
        
        # Denominator is cells where score["pass"] is NOT None
        valid_tasks = []
        for cell in cells:
            if not isinstance(cell, dict): continue
            tid = cell.get("task_id")
            s = scores.get(tid)
            if s and s.get("pass") is not None:
                valid_tasks.append(cell)
        
        n = len(valid_tasks)
        passed = sum(1 for v in valid_tasks if scores[v["task_id"]]["pass"] is True)
        failed = sum(1 for v in valid_tasks if scores[v["task_id"]]["pass"] is False)
        rate = passed / n if n > 0 else 0
        
        calls = []
        timeouts = 0
        tokens = 0
        wall_s = 0
        
        if os.path.exists(events_file):
            with open(events_file, 'r') as f:
                for line in f:
                    event = json.loads(line)
                    if event.get("type") == "model_call":
                        calls.append(event)
                    elif event.get("type") == "timeout":
                        timeouts += 1
        
        # Also check cell for some metrics if they are there (like wall_s or tokens)
        for cell in cells:
            if not isinstance(cell, dict): continue
            tid = cell.get("task_id")
            if tid and scores[tid].get("pass") is True:
                wall_s += cell.get("wall_s", 0)
                tokens += cell.get("metrics", {}).get("output_tokens", 0)

        per_arm[folder] = {
            "n": n,
            "pass": passed,
            "fail": failed,
            "rate": rate,
            "calls": calls,
            "timeouts": timeouts,
            "tokens": tokens,
            "wall_s": wall_s,
            "valid_tasks": valid_tasks
        }

    print(json.dumps(per_arm, indent=2))

if __name__ == "__main__":
    recompute()
