import subprocess
import time
import threading

def task_func(file_list):
    results = [None] * len(file_list)
    threads = []

    def run_process(index, file_path):
        try:
            # Use Popen to start the process. 
            # We don't use shell=True for security reasons unless necessary.
            process = subprocess.Popen([file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            results[index] = process.poll()
        except Exception:
            # If the file cannot be executed or doesn't exist, we return a non-zero code.
            # 1 is a common error code for "command not found" or similar issues in some contexts,
            # but since it's an exception, maybe -1 or something else?
            # Let's use -1 to indicate failure to start the process itself.
            results[index] = -1

    for i, file_path in enumerate(file_list):
        t = threading.Thread(target=run_process, args=(i, file_path))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return results
