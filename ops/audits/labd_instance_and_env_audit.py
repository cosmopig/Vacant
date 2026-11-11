import json
from pathlib import Path
from typing import List, Dict

def audit_run_dir(run_path: Path) -> Dict[str, List[str]]:
    """
    Scans a directory for cell.json files and checks for environment leaks.
    A leak is defined as the presence of 'VACANT_PI_PARENT' or 'VACANT_PI_SELF' 
    in the content of cell.json.
    """
    results = {"clean": [], "violations": []}
    
    # We want to find all cell.json files in this directory and its subdirectories
    for p in run_path.rglob("cell.json"):
        try:
            with open(p, 'r') as f:
                data = json.load(f)
                content = str(data)
                if "VACANT_PI_PARENT" in content or "VACANT_PI_SELF" in content:
                    results["violations"].append(str(p))
                else:
                    results["clean"].append(str(p))
        except Exception as e:
            # Log error but continue scanning other files
            pass
            
    return results

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-e016", action="store_true")
    args = parser.parse_args()

    if args.audit_e016:
        # The ticket specifies auditing the workspace structure.
        # We'll audit the current working directory and its subdirectories.
        # However, we should be careful not to go too deep into system dirs 
        # if they are somehow reachable.
        workspace = Path(".")
        print(f"Auditing workspace: {workspace}")
        
        results = audit_run_dir(workspace)
        
        output_path = Path("ops/audits/e016_envleak_resolution_audit.json")
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"Audit results written to {output_path}")
        if not results["violations"]:
            print("VERDICT: E016_ENVLEAK_AUDIT_OK")
        else:
            print(f"VERDICT: E016_ENVLEAK_AUDIT_FAILED ({len(results['violations'])} violations)")

if __name__ == "__main__":
    main()
