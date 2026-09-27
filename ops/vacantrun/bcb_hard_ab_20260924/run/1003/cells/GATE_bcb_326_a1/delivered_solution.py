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
            # Run the batch file and get its return code
            process = subprocess.Popen(batch_file, shell=True)
            returncode = process.wait()
            results.append((os.path.basename(batch_file), returncode))
        except Exception:
            # If for some reason it couldn't be executed (e.g., permission denied or file not found)
            results.append((os.path.basename(batch_file), None))
            
    return results
