import json
from pathlib import Path

def run():
    exp_dir = Path("/srv/vlab/runs/e002_smoke")
    subdirs = [d for d in exp_dir.iterdir() if d.is_dir()]
    
    arm_data = {}
    for subdir in subdirs:
        if "REPORT" in subdir.name: continue
        
        arm_name = "UNKNOWN"
        if "-pi-" in subdir.name:
            parts = subdir.name.split("-pi-")
            arm_name = parts[1].split("-")[0]
        
        cell_path = subdir / "cell.json"
        score_path = subdir / "score.json"
        events_path = subdir / "events.jsonl"
        
        if not cell_path.exists() or not score_path.exists():
            continue

        with open(score_path, 'r') as f:
            score = json.load(f)
        
        pass_val = score.get("pass")
        is_pass = pass_val is True
        
        total_calls = 0
        if events_path.exists():
            with open(events_path, 'r') as f:
                for line in f:
                    try:
                        ev = json.loads(line)
                        if ev.get("type") == "model_call":
                            total_calls += 1
                    except: pass

        if arm_name not in arm_data:
            arm_data[arm_name] = {"n": 0, "passes": 0, "total_calls": 0, "timeouts": 0}
        
        arm_data[arm_name]["n"] += 1
        if is_pass:
            arm_data[arm_name]["passes"] += 1
            # If it passed, we count its calls towards the success metric?
            # Let's see if sum of all calls / passes matches REPORT.json
            # For A: n=2, pass=2, calls_per_success=16 -> total_calls = 32
            # For M: n=2, pass=1, calls_per_success=31 -> total_calls = 31? Or 62?
        else:
            pass

    # Let's try the other way: sum all calls for arm, divide by passes.
    # If that doesn't match M, then it only counts calls from passing cells.
    
    print("Raw Data:")
    for arm, data in arm_data.items():
        calls_per_success = 0
        if data["passes"] > 0:
            # Try sum all / passes first
            # We need to know the total calls for this arm across ALL cells.
            pass
            
    # Let's just print everything raw and see.
    for subdir in subdirs:
        if "REPORT" in subdir.name: continue
        arm_name = "UNKNOWN"
        if "-pi-" in subdir.name:
            parts = subdir.name.split("-pi-")
            arm_name = parts[1].split("-")[0]
        
        with open(subdir / "score.json", 'r') as f:
            score = json.load(f)
        
        total_calls = 0
        if (subdir / "events.jsonl").exists():
            with open(subdir / "events.jsonl", 'r') as f:
                for line in f:
                    try:
                        ev = json.loads(line)
                        if ev.get("type") == "model_call":
                            total_calls += 1
                    except: pass
        print(f"{arm_name} | n=1 | pass={score.get('pass')} | calls={total_calls}")

run()
