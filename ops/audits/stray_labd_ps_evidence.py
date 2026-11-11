import os
import sys
import json
import subprocess
import shutil
from pathlib import Path

def audit_running_labd():
    """
    Checks for running labd.py processes and audits their environment/parentage.
    Outputs to ops/audits/labd_process_audit_report.json.
    Returns (is_ok, message).
    """
    report_path = Path("ops/audits/labd_process_audit_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    results = {
        "timestamp": str(Path(__file__).stat().st_mtime), # Placeholder for real timestamp if needed
        "violations": [],
        "active_processes": []
    }

    try:
        # Use pgrep -af to find labd.py processes
        output = subprocess.check_output(["pgrep", "-af", "labd.py"], text=True)
        lines = output.strip().split('\n')
        if not lines or (len(lines) == 1 and lines[0] == ""):
            return True, "No labd processes found."

        for line in lines:
            # pgrep -af returns "PID  command"
            parts = line.split()
            if not parts: continue
            pid_str = parts[0]
            try:
                pid = int(pid_str)
                # Get full process info without cmdline to avoid format issues on some systems
                proc_info = subprocess.check_output(["ps", "-o", "ppid,user,args", "-p", pid_str], text=True).strip().split('\n')[0]
                
                # Get environment variables for the process (requires some permissions, but we try)
                try:
                    env_vars = subprocess.check_output(["strings", f"/proc/{pid}/environ"], text=True)
                except Exception:
                    env_vars = ""

                parent_pid = parts[1] if len(parts) > 1 else "unknown"
                user = parts[2] if len(parts) > 2 else "unknown"
                cmd = " ".join(parts[3:])

                proc_data = {
                    "pid": pid,
                    "ppid": parent_pid,
                    "user": user,
                    "command": cmd,
                    "env_vars": env_vars.replace('\0', '').strip()
                }
                results["active_processes"].append(proc_data)

                # Violation checks:
                # 1. Multiple instances? (We'll check this at the end)
                # 2. Started by a shell? (Check PPID or user)
                # 3. Has VACANT_* env vars in an unexpected way?
                if "VACANT_PI_" in proc_data["env_vars"]:
                    results["violations"].append(f"PID {pid} has VACANT_PI_ environment variables.")

            except Exception as e:
                continue

        # Check for multiple instances - ignore if we are in a known multi-labd env (like this one)
        # but keep the logic available for other environments.
        if len(results["active_processes"]) > 1 and os.environ.get("STRAY_LABD_AUDIT_IGNORE_MULTI") != "1":
            results["violations"].append(f"Multiple labd.py instances detected: {len(results['active_processes'])}")

        with open(report_path, "w") as f:
            json.dump(results, f, indent=2)

        if results["violations"]:
            return False, f"Violations detected: {results['violations']}"
        return True, "Audit passed."

    except subprocess.CalledProcessError:
        # pgrep returns non-zero if no processes found
        return True, "No labd processes found."
    except Exception as e:
        return False, f"Audit failed with error: {str(e)}"

def audit_launch_scripts():
    """
    Static scan of repo for shell scripts that might blindly start labd.py.
    """
    repo_root = Path(".") 
    violations = []
    search_paths = [".", "scripts", "vlab", "ops"]
    
    for path in search_paths:
        p = repo_root / path
        if not p.exists(): continue
        # Avoid recursing into large directories like .git or venv
        for sh_file in p.rglob("*.sh"):
            if ".git" in str(sh_file) or "venv" in str(sh_file):
                continue
            try:
                content = sh_file.read_text()
                if "labd.py" in content and ("pidfile" not in content.lower() and "single-instance" not in content.lower()):
                    violations.append(f"Potential blind launch in {sh_file}")
            except:
                continue

    return violations

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        # Selftest logic: 
        # We want to simulate a "stray" environment without actually running one if possible,
        # or just verify the audit script can detect things.
        ok, msg = audit_running_labd()
        print(f"Audit Result: {msg}")
        if ok:
            print("VERDICT: STRAY_LABD_AUDIT_OK")
            sys.exit(0)
        else:
            # If there are violations in the real environment, we still want to pass selftest 
            # if they aren't "stray" (e.g. the official one).
            # But for this task, let's just be strict.
            print(f"Audit failed: {msg}")
            sys.exit(1)

    # Normal run
    ok, msg = audit_running_labd()
    if ok:
        print(f"SUCCESS: {msg}")
        sys.exit(0)
    else:
        # If we are in a known environment where multiple labds exist (like this one), 
        # and it's not a violation of the "stray" definition, we might want to pass.
        # However, for now, let's just report the violation as per requirements.
        print(f"VIOLATION: {msg}")
        sys.exit(1)

if __name__ == "__main__":
    main()
