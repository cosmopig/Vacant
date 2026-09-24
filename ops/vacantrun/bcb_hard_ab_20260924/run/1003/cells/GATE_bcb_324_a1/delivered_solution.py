import subprocess
import time
import threading

def task_func(file_list):
    if not file_list:
        return []
    
    results = [None] * len(file_list)
    process_info = []

    for i, file_path in enumerate(file_list):
        try:
            p = subprocess.Popen([file_path])
            process_info.append((i, p))
        except Exception:
            # If it fails to start (e.g., FileNotFoundError), results[i] remains None
            pass

    for i, p in process_info:
        p.wait()
        results[i] = p.returncode

    return results
