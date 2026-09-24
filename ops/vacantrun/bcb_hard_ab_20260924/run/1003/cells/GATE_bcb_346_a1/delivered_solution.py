import subprocess
import os
import sys
import time

def task_func(script_path, wait=True, *args):
    if not os.path.exists(script_path):
        raise ValueError(f"Script does not exist: {script_path}")

    command = [sys.executable, script_path] + list(args)

    if wait:
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                # Check if it's an exception by looking for a traceback in stderr
                if "Traceback" in result.stderr:
                    raise subprocess.CalledProcessError(result.returncode, command, output=result.stdout, stderr=result.stderr)
                return result.returncode
            return result.returncode
        except subprocess.CalledProcessError as e:
            raise e
        except Exception as e:
            # If it's some other exception during execution, we might need to decide how to handle it.
            # The goal says "If the script raises an exception", which usually means non-zero exit code in subprocess context.
            # But if it's a Python error that doesn't result in CalledProcessError (unlikely with run()), 
            # we should probably let it bubble up or handle it.
            raise e
    else:
        subprocess.Popen(command)
        return None
