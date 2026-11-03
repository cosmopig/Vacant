import json
import os
from pathlib import Path

def audit():
    base_path = Path("/srv/vlab/runs/e016_failed_step_ablation")
    results = []
    
    # Find all cell.json files
    cell_files = list(base_path.glob("**/cell.json"))
    print(f"Found {len(cell_files)} cell.json files.")

    for cell_file in cell_files:
        try:
            with open(cell_file, 'r') as f:
                data = json.load(f)
            
            path_str = str(cell_file)
            # Determine arm from path
            arm = "UNKNOWN"
            if "-pi-A-" in path_str:
                arm = "A"
            elif "-pi-C-nf-" in path_str:
                arm = "C-nf"
            elif "-pi-C-" in path_str:
                arm = "C"

            agent_env = data.get("agent_env")
            leakage = []
            status = "OK"
            note = ""

            if arm == "A":
                if agent_env is not None:
                    status = "LEAKED"
                    leakage = list(agent_env.keys())
                else:
                    status = "NULL"
            elif arm == "C":
                if agent_env is not None:
                    status = "LEAKED"
                    leakage = list(agent_env.keys())
                else:
                    status = "NULL"
            elif arm == "C-nf":
                expected = {"VACANT_FAILED_STEP_REVIEW": "0"}
                if agent_env is None:
                    status = "MISSING"
                    note = "Expected {'VACANT_FAILED_STEP_REVIEW': '0'}, but got null"
                elif agent_env == expected:
                    status = "OK"
                else:
                    status = "POLLUTED"
                    leakage = list(agent_env.keys())
                    note = f"Expected {expected}, but got {agent_env}"
            
            results.append({
                "path": path_str,
                "arm": arm,
                "status": status,
                "leakage": leakage,
                "note": note
            })
        except Exception as e:
            print(f"Error reading {cell_file}: {e}")

    # Print summary for the audit file
    print("--- Audit Summary ---")
    summary = {"A": {"LEAKED": 0, "NULL": 0}, "C": {"LEAKED": 0, "NULL": 0}, "C-nf": {"OK": 0, "POLLUTED": 0, "MISSING": 0}}
    for r in results:
        if r["arm"] in summary:
            summary[r["arm"]][r["status"]] += 1

    print(json.dumps(summary, indent=2))
    
    # Write detailed results to a temp file for the audit report
    with open("audit_raw.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    audit()
