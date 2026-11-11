import sys
import os
import json
import argparse

try:
    from ops.audits.stray_labd_ps_evidence import collect_processes, is_labd
except ImportError:  # direct script run from ops/audits/ (sys.path[0] = script dir)
    from stray_labd_ps_evidence import collect_processes, is_labd

def _cmdline_of(entry):
    """Normalize one proc_list entry to a cmdline argument list.

    Accepts a raw argument list, a dict with "cmdline"/"args"
    (collect_processes() shape), or a bare string (judged as one token).
    """
    if isinstance(entry, dict):
        for key in ("cmdline", "args"):
            value = entry.get(key)
            if isinstance(value, (list, tuple)):
                return [str(a) for a in value]
        return []
    if isinstance(entry, (list, tuple)):
        return [str(a) for a in entry]
    if isinstance(entry, str):
        return [entry]
    return []

def check_labd_instances(proc_list=None):
    """
    Count running labd.py instances.
    0 = idle, 1 = normal; >1 reports MULTIPLE_LABD_INSTANCES and exits 1.

    proc_list=None: live /proc scan via stray_labd_ps_evidence.collect_processes,
    judged by is_labd (an argument ending in labd.py preceded by a python
    interpreter) -- no pgrep -f substring match, so a process whose args merely
    mention "labd.py" never counts (and a bare pid string can never match).
    proc_list given: each entry judged item by item with the same is_labd rule.
    """
    if proc_list is None:
        proc_list = collect_processes()
    count = sum(1 for entry in proc_list if is_labd(_cmdline_of(entry)))
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
        # This shouldn't happen based on typical cell.json but handle just in case
        pass

    # Check for A or C arms (case-insensitive)
    arm_upper = arm.upper()
    # We need to know which arm this cell belongs to. 
    # Usually, the file path or a field in cell.json indicates it.
    # The requirement says "If for A/C arms". Let's check if 'arm' is in data.
    cell_arm = str(data.get("arm", "")).upper()
    
    if arm_upper in ["A", "C"] or cell_arm in ["A", "C"]:
        # Check for VACANT_* keys or values
        for k, v in agent_env.items():
            v_str = str(v)
            if "VACANT_" in k or "VACANT_" in v_str:
                print(f"ERROR: AGENT_ENV_LEAK detected in key '{k}' with value '{v_str}'")
                sys.exit(1)
        
        # Check for host pi session residuals (e.g., PI_PARENT, PI_SELF)
        # These are often injected as env vars.
        for k, v in agent_env.items():
            v_str = str(v)
            if "PI_PARENT" in v_str or "PI_SELF" in v_str:
                print(f"ERROR: AGENT_ENV_LEAK detected host pi session residual in '{k}'")
                sys.exit(1)

    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true", help="Run self-test mode")
    args = parser.parse_args()

    if args.selftest:
        print("Running self-test...")
        # Three-way control: 0 instances
        if check_labd_instances(proc_list=[]) != 0:
            print("FAILURE: expected 0 for empty proc_list")
            sys.exit(1)
        print("SUCCESS: zero instances")
        # Three-way control: 1 instance
        if check_labd_instances(proc_list=[["python3", "/srv/vlab/bin/labd.py"]]) != 1:
            print("FAILURE: expected 1 for a single labd cmdline")
            sys.exit(1)
        print("SUCCESS: single instance")
        # Substring-only args must not count (pgrep -f false positive)
        if check_labd_instances(proc_list=[["pi", "-p", "text mentions labd.py"]]) != 0:
            print("FAILURE: substring-only match must not count")
            sys.exit(1)
        print("SUCCESS: substring non-labd not counted")
        # Test AGENT_ENV_LEAK (should exit 1)
        try:
            audit_cell_env("dummy_path", arm="A")
        except SystemExit as e:
            if e.code == 1:
                print("SUCCESS: Caught AGENT_ENV_LEAK")
            else:
                print(f"FAILURE: Unexpected exit code {e.code}")
                sys.exit(1)
        else:
            print("FAILURE: expected SystemExit for AGENT_ENV_LEAK")
            sys.exit(1)

        # Test MULTIPLE_LABD_INSTANCES (should exit 1) -- last: exits 0 on success
        try:
            check_labd_instances(proc_list=[["python3", "/a/labd.py"], ["python3", "/b/labd.py"]])
        except SystemExit as e:
            if e.code == 1:
                print("SUCCESS: Caught MULTIPLE_LABD_INSTANCES")
                sys.exit(0)
            else:
                print(f"FAILURE: Unexpected exit code {e.code}")
                sys.exit(1)
        else:
            print("FAILURE: expected SystemExit for multiple instances")
            sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: labd_instance_and_env_audit.py [--selftest] <cell_json_path>")
        sys.exit(1)

    cell_json_path = sys.argv[1]
    check_labd_instances()
    audit_cell_env(cell_json_path, arm="A")
    print("VERDICT: LABD_AUDIT_OK")

if __name__ == "__main__":
    main()
