import subprocess
import time
import threading

def task_func(file_list):
    results = [None] * len(file_list)
    threads = []

    def run_subprocess(index, file_path):
        try:
            # We use subprocess.run or Popen. 
            # Since we need to wait for it and get the exit code, Popen is good.
            process = subprocess.Popen([file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            exit_code = process.wait()
            results[index] = exit_code
        except Exception:
            # If for some reason it can't be run as a subprocess (e.g. not executable), 
            # we might need to handle that, but usually these tasks assume they are executable.
            results[index] = -1

    for i, file_path in enumerate(file_list):
        t = threading.Thread(target=run_subprocess, args=(i, file_path))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return results
