import subprocess
import time
import threading

def task_func(file_list):
    results = [None] * len(file_list)
    processes = []
    for i, file_path in enumerate(file_list):
        try:
            p = subprocess.Popen([file_path])
            processes.append((i, p))
        except Exception:
            pass

    for i, p in processes:
        results[i] = p.returncode

    return results
