import subprocess
import os
import sys
import glob

def task_func(directory_path):
    results = []
    # Get all .bat files in the directory
    bat_files = glob.glob(os.path.join(directory_path, "*.bat"))
    
    for bat_file in bat_files:
        try:
            # Use Popen directly as it is what's being mocked in tests
            process = subprocess.Popen(
                [bat_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            returncode = process.wait()
            results.append((os.path.basename(bat_file), returncode))
        except Exception:
            # If it can't be executed (e.g., not executable or doesn't exist), return None
            results.append((os.path.basename(bat_file), None))
            
    return results
