import json
from pathlib import Path
from typing import List, Dict, Any
import os

def audit_run_dir(run_path: Path) -> Dict[str, Any]:
    """
    Scans a directory for cell.json files and checks for environment leaks.
    A leak is defined as the presence of 'VACANT_PI_PARENT' or 'VACANT_PI_SELF' 
    in the content of cell.json.
    """
    total_cells = 0
    violations = []
    violated_cells = []
    clean_cells = []
    missing_cell_json = []

    for root, dirs, files in os.walk(run_path):
        # Skip .infra- directories
        dirs[:] = [d for d in dirs if not d.startswith(".infra-")]
        
        if "cell.json" in files:
            p = Path(root) / "cell.json"
            try:
                with open(p, 'r') as f:
                    data = json.load(f)
                    content = str(data)
                    total_cells += 1
                    # C-nf arm's VACANT_FAILED_STEP_REVIEW is a pre-registered parameter, not a leak
                    if "VACANT_PI_PARENT" in content or "VACANT_PI_SELF" in content:
                        violations.append(str(p))
                        violated_cells.append(str(p))
                    else:
                        clean_cells.append(str(p))
            except Exception as e:
                # Log error but continue scanning other files
                pass
            
    return {
        "total_cells": total_cells,
        "violations": violations,
        "violated_cells": violated_cells,
        "clean_cells": clean_cells,
        "missing_cell_json": missing_cell_json
    }

def audit_run_dir_v2(run_path: Path) -> Dict[str, Any]:
    # Ensure run_path is a Path object
    if not isinstance(run_path, Path):
        run_path = Path(run_path)
    
    # If the path doesn't exist, return empty results instead of crashing
    if not run_path.exists():
        return {
            "total_cells": 0,
            "violations": [],
            "violated_cells": [],
            "clean_cells": [],
            "missing_cell_json": []
        }

    # Use os.walk for more robust recursive scanning than rglob in some environments
    total_cells = 0
    violations = []
    violated_cells = []
    clean_cells = []
    missing_cell_json = []

    for root, dirs, files in os.walk(run_path):
        # Skip .infra- directories
        dirs[:] = [d for d in dirs if not d.startswith(".infra-")]
        
        if "cell.json" in files:
            p = Path(root) / "cell.json"
            try:
                with open(p, 'r') as f:
                    data = json.load(f)
                    content = str(data)
                    total_cells += 1
                    # C-nf arm's VACANT_FAILED_STEP_REVIEW is a pre-registered parameter, not a leak
                    if "VACANT_PI_PARENT" in content or "VACANT_PI_SELF" in content:
                        violations.append(str(p))
                        violated_cells.append(str(p))
                    else:
                        clean_cells.append(str(p))
            except Exception as e:
                # Log error but continue scanning other files
                pass
            
    return {
        "total_cells": total_cells,
        "violations": violations,
        "violated_cells": violated_cells,
        "clean_cells": clean_cells,
        "missing_cell_json": missing_cell_json
    }

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-e016", action="store_true")
    args = parser.parse_args()

    if args.audit_e016:
        # Negative control: e016 attempt-1
        neg_path = Path("/srv/vlab/runs/e016_failed_step_ablation_r905_attempt1_envleak")
        # Positive control: e016 attempt-2
        pos_path = Path("/srv/vlab/runs/e016_failed_step_ablation")

        neg_results = audit_run_dir_v2(neg_path)
        pos_results = audit_run_dir_v2(pos_path)

        # Verify negative control: 14 cells, 11 violations, 3 clean
        if (neg_results["total_cells"] == 14 and 
            len(neg_results["violations"]) == 11 and 
            len(neg_results["clean_cells"]) == 3):
            print("Negative control passed.")
        else:
            print(f"Negative control failed: {neg_results}")
            exit(1)

        # Verify positive control: 102 cells, 0 violations
        if (pos_results["total_cells"] == 102 and 
            len(pos_results["violations"]) == 0):
            print("Positive control passed.")
        else:
            print(f"Positive control failed: {pos_results}")
            exit(1)

        output_path = Path("ops/audits/e016_envleak_resolution_audit.json")
        with open(output_path, "w") as f:
            json.dump({
                "negative_control": neg_results,
                "positive_control": pos_results
            }, f, indent=2)
        
        print(f"Audit results written to {output_path}")
        print("VERDICT: E016_ENVLEAK_AUDIT_OK")

if __name__ == "__main__":
    main()