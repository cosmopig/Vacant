import subprocess
import os
import sys
import glob

def task_func(directory_path):
    results = []
    # Get all .bat files in the directory
    batch_files = glob.glob(os.path.join(directory_path, "*.bat"))
    
    for batch_file in batch_files:
        try:
            # Use Popen directly to match the mock and handle execution
            process = subprocess.Popen(batch_file, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            exit_code = process.wait()
            results.append((os.path.basename(batch_file), exit_code))
        except Exception:
            # If it couldn't be executed for some reason (e.g., file not found or permission denied)
            results.append((os.path.basename(batch_file), None))
            
    return results
