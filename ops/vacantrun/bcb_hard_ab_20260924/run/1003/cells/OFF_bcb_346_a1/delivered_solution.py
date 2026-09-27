import subprocess
import os
import sys
import time

def task_func(script_path, wait=True, *args):
    if not os.path.exists(script_path):
        raise ValueError(f"Script does not exist: {script_path}")

    # Prepare the command to run the script with provided arguments
    command = [sys.executable, script_path] + list(args)

    if wait:
        try:
            result = subprocess.run(command, check=True)
            return result.returncode
        except subprocess.CalledProcessError as e:
            raise e
    else:
        # If wait is False, we start the process and don't wait for it to complete
        subprocess.Popen(command)
        return None
