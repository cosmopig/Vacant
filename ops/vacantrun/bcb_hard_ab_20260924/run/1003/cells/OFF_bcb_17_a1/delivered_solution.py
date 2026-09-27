import subprocess
import psutil
import time

def task_func(process_name: str) -> str:
    found_processes = []
    for proc in psutil.process_iter():
        try:
            if proc.name() == process_name:
                found_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    if not found_processes:
        # Start the process
        subprocess.Popen(process_name)
        return f"Process not found. Starting {process_name}."
    else:
        # Terminate all matching processes
        for proc in found_processes:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        # Start the process again
        subprocess.Popen(process_name)
        return f"Process found. Restarting {process_name}."
