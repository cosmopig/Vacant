import subprocess
import os
import sys
import time

def task_func(script_path, wait=True, *args):
    if not os.path.exists(script_path):
        raise ValueError(f"Script {script_path} does not exist.")
    
    cmd = [sys.executable, script_path] + list(args)
    
    if wait:
        result = subprocess.run(cmd, check=True)
        return result.returncode
    else:
        subprocess.Popen(cmd)
        return None
