import json
from pathlib import Path

def get_stats(run_dir):
    cell = json.loads(Path(run_dir, "cell.json").read_text())
    score = json.loads(Path(run_dir, "score.json").read_text())
    events = []
    if (Path(run_dir, "events.jsonl")).exists():
        with open(Path(run_dir, "events.jsonl"), "r") as f:
            for line in f:
                events.append(json.loads(line))
    
    results = []
    cid = cell["cell"]
    results.append({
        "cell_id": cid,
        "score": score,
        "data": cell,
        "events": [e for e in events if e.get("cell_id") == cid]
    })
    return results

def main():
    base_dir = Path("/srv/vlab/runs/e014_dabstep_block")
    run_dirs = sorted([d for d in base_dir.iterdir() if d.is_dir() and "-pi-" in d.name])
    
    task_stats = {} # cell_id -> {A: {}, C: {}, CB: {}}
    
    for run_dir in run_dirs:
        arm = "A" if "-pi-A-" in run_dir.name else ("C" if "-pi-C-" in run_dir.name else "CB")
        results = get_stats(run_dir)
        
        for res in results:
            cid = res["cell_id"]
            if cid not in task_stats:
                task_stats[cid] = {"A": {}, "C": {}, "CB": {}}
            
            s = res["score"]
            passed = None
            if s and s.get("pass") is True:
                passed = True
            elif s and s.get("pass") is False:
                passed = False
            
            # Determine if infra_void (rc=3)
            is_infra = False
            if s and s.get("rc") == 3:
                is_infra = True

            # Initialize arm dict with defaults if not present
            for a in ["A", "C", "CB"]:
                if a not in task_stats[cid] or "pass" not in task_stats[cid][a]:
                    task_stats[cid][a] = {
                        "pass": None,
                        "is_infra": False,
                        "calls": 0,
                        "tokens": 0,
                        "timeout": False,
                        "hold_count": 0,
                        "is_refusal": False
                    }

            task_stats[cid][arm].update({
                "pass": passed,
                "is_infra": is_infra,
                "calls": s.get("calls", 0) if s else 0,
                "tokens": s.get("tokens", 0) if s else 0,
                "timeout": s.get("timeout", False) if s else False,
            })
            
            # Mechanism details for CB
            if arm == "CB":
                hold_events = [e for e in res["events"] if e.get("action") == "continue" and e.get("round", 0) >= 3]
                refusal = False
                if s and s.get("timeout") is True:
                    # Check last action was continue
                    last_act = None
                    for e in reversed(res["events"]):
                        if e.get("cell_id") == cid:
                            last_act = e.get("action")
                            break
                    if last_act == "continue":
                        refusal = True
                task_stats[cid][arm]["hold_count"] = len(hold_events)
                task_stats[cid][arm]["is_refusal"] = refusal

    print(f"{'Cell ID':<20} | {'A Pass':<6} | {'C Pass':<6} | {'CB Pass':<6} | {'CB Hold':<6} | {'CB Refusal':<8}")
    print("-" * 75)
    for cid, arms in task_stats.items():
        a_p = "P" if arms["A"]["pass"] is True else ("F" if arms["A"]["pass"] is False else "I")
        c_p = "P" if arms["C"]["pass"] is True else ("F" if arms["C"]["pass"] is False else "I")
        cb_p = "P" if arms["CB"]["pass"] is True else ("F" if arms["CB"]["pass"] is False else "I")
        h = arms["CB"].get("hold_count", 0)
        r = "Y" if arms["CB"].get("is_refusal") else "N"
        print(f"{cid:<20} | {a_p:<6} | {c_p:<6} | {cb_p:<6} | {h:<6} | {r:<8}")

if __name__ == "__main__":
    main()
