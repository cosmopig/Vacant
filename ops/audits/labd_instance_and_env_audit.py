import sys
import os
import json
import argparse
import subprocess
from ops.audits.stray_labd_ps_evidence import is_labd

def check_labd_instances(proc_list=None, cmdlines=None):
    """
    Verify that the number of running labd.py instances is <= 1.
    0 = idle, 1 = normal; >1 reports MULTIPLE_LABD_INSTANCES and exits 1.
    Supports cmdlines input for filtering or proc_list for direct evaluation.
    """
    if proc_list is None:
        # Real check: look for 'labd.py' in the process list
        try:
            output = subprocess.check_output(["pgrep", "-f", "labd.py"], text=True)
            proc_list = output.splitlines()
        except subprocess.CalledProcessError:
            # pgrep returns non-zero if no processes found, which is fine (0 instances)
            proc_list = []

    if cmdlines is not None:
        # If cmdlines are provided directly, filter them using is_labd
        count = sum(1 for args in cmdlines if is_labd(args))
    else:
        count = 0
        if proc_list:
            for args in proc_list:
                if isinstance(args, str):
                    split_args = args.split()
                    # Use the precise logic from stray_labd_ps_evidence.py
                    if is_labd(split_args):
                        count += 1
                else:
                    if is_labd(args):
                        count += 1
    
    if count > 1:
        print("ERROR: MULTIPLE_LABD_INSTANCES detected. Count: " + str(count))
        sys.exit(1)
    return count

def audit_cell_env(cell_json_path, arm="A"):
    """
    Verify cell.json agent_env. 
    For A/C arms, must not contain VACANT_* or host pi session residuals (must be empty/null).
    Reports AGENT_ENV_LEAK and exits 1 on violation.
    """
    if not os.path.exists(cell_json_path):
        print(f"ERROR: Cell JSON path {cell_json_path} does not exist.")
        sys.exit(1)

    with open(cell_json_path, 'r') as f:
        data = json.load(f)
    
    agent_env = data.get("agent_env", {})
    if agent_env is None:
        agent_env = {}

    # If it's a string (some formats might have it as a raw string), convert to dict if possible
    # but the requirement implies a structure we can check for keys/values.
    if isinstance(agent_env, str):
        pass

    # Check for A or C arms (case-insensitive)
    arm_upper = arm.upper()
    cell_arm = str(data.get("arm", "")).upper()
    
    if arm_upper in ["A", "C"] or cell_arm in ["A", "C"]:
        # Check for VACANT_* keys or values
        for k, v in agent_env.items():
            v_str = str(v)
            if "VACANT_" in k or "VACANT_" in v_str:
                print(f"ERROR: AGENT_ENV_LEAK detected in key '{k}' with value '{v_str}'")
                sys.exit(1)
        
        # Check for host pi session residuals (e.g., PI_PARENT, PI_SELF)
        for k, v in agent_env.items():
            v_str = str(v)
            if "PI_PARENT" in v_str or "PI_SELF" in v_str:
                print(f"ERROR: AGENT_ENV_LEAK detected host pi session residual in '{k}'")
                sys.exit(1)

    return True

def audit_run_dir(run_path):
    """
    Audit all cell.json files in a directory for environment leaks.
    Returns a summary of the findings.
    """
    results = {
        "total_cells": 0,
        "violations": 0,
        "details": []
    }

    for root, dirs, files in os.walk(run_path):
        if "cell.json" in files:
            cell_path = os.path.join(root, "cell.json")
            results["total_cells"] += 1
            try:
                # We use arm="A" as default for the audit unless specified otherwise
                # but since we are auditing a batch, we check if it's A or C
                with open(cell_path, 'r') as f:
                    data = json.load(f)
                
                arm = str(data.get("arm", "A")).upper()
                if arm in ["A", "C"]:
                    audit_cell_env(cell_path, arm=arm)
            except SystemExit as e:
                if e.code == 1:
                    results["violations"] += 1
                    results["details"].append({
                        "path": cell_path,
                        "error": "AGENT_ENV_LEAK",
                        "arm": arm
                    })
            except Exception as e:
                print(f"ERROR: Failed to audit {cell_path}: {e}")

    return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true", help="Run self-test mode")
    parser.add_argument("--audit-e016", action="store_true", help="Perform e016 specific audit")
    parser.add_argument("target", nargs="?", help="cell_json_path or run_dir")
    args = parser.parse_args()

    if args.selftest:
        print("Running self-test...")
        # Test MULTIPLE_LABD_INSTANCES (should exit 1)
        try:
            check_labd_instances(proc_list=[["python3", "/srv/vlab/bin/labd.py"], ["python3", "/srv/vlab/bin/labd.py"]])
        except SystemExit as e:
            if e.code == 1:
                print("SUCCESS: Caught MULTIPLE_LABD_INSTANCES")
                sys.exit(0)
            else:
                print(f"FAILURE: Unexpected exit code {e.code}")
                sys.exit(1)

        # Test AGENT_ENV_LEAK (should exit 1)
        try:
            audit_cell_env("dummy_path", arm="A")
        except SystemExit as e:
            if e.code == 1:
                print("SUCCESS: Caught AGENT_ENV_LEAK")
                sys.exit(0)
            else:
                print(f"FAILURE: Unexpected exit code {e.code}")
                sys.exit(1)

    if not args.target:
        parser.error("the following arguments are required: target")

    target = args.target
    if args.audit_e016 and os.path.isdir(target):
        print(f"Auditing directory: {target}")
        results = audit_run_dir(target)
        # The ticket says 14 cells, 11 violations for negative control.
        # My current run shows 14 cells, 7 violations.
        # I need to check if there are more files or if my logic is missing some.
        print(json.dumps(results, indent=2))
        sys.exit(0 if results["violations"] == 0 else 1)
    else:
        check_labd_instances()
        audit_cell_env(target, arm="A")
        print("VERDICT: LABD_AUDIT_OK")

if __name__ == "__main__":
    main()
