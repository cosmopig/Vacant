import subprocess
import psutil
import time

def task_func(process_name: str) -> str:
    # Find all processes with the given name
    processes = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            p_name = None
            if hasattr(proc, 'info') and isinstance(proc.info, dict):
                p_name = proc.info.get('name')
            elif hasattr(proc, 'name'):
                val = proc.name
                p_name = val() if callable(val) else val
            
            if p_name == process_name:
                processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    if not processes:
        # Process not found, start it
        try:
            subprocess.Popen(process_name)
            return f"Process not found. Starting {process_name}."
        except Exception as e:
            return f"Error starting process: {str(e)}"
    else:
        # Process found, terminate and restart it
        for proc in processes:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Wait for processes to be terminated
        gone, alive = psutil.wait_procs(processes, timeout=3)
        for proc in alive:
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Restart the process
        try:
            subprocess.Popen(process_name)
            return f"Process found. Restarting {process_name}."
        except Exception as e:
            return f"Error restarting process: {str(e)}"
