import subprocess
import psutil
import time

def task_func(process_name: str) -> str:
    processes = []
    for proc in psutil.process_iter():
        try:
            if proc.name() == process_name:
                processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not processes:
        subprocess.Popen(process_name)
        return f"Process not found. Starting {process_name}."
    else:
        for proc in processes:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        time.sleep(0.5)
        
        subprocess.Popen(process_name)
        return f"Process found. Restarting {process_name}."
