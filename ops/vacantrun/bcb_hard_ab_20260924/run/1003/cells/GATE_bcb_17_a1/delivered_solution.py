import subprocess
import psutil
import time

def task_func(process_name: str) -> str:
    running_processes = []
    for p in psutil.process_iter():
        try:
            # Get the process name from info or .name()
            p_name = None
            if hasattr(p, 'info') and p.info:
                p_name = p.info.get('name')
            else:
                p_name = p.name()

            if not p_name:
                continue

            # Check for match: exact, case-insensitive, or with .exe suffix
            is_match = False
            if p_name == process_name:
                is_match = True
            elif p_name.lower() == process_name.lower():
                is_match = True
            elif not process_name.endswith('.exe') and p_name == process_name + '.exe':
                is_match = True
            elif process_name.endswith('.exe') and p_name == process_name:
                is_match = True

            if is_match:
                running_processes.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    if not running_processes:
        # Process not found. Start it.
        subprocess.Popen([process_name])
        return f"Process not found. Starting {process_name}."
    else:
        # Process found. Terminate and restart it.
        for p in running_processes:
            try:
                p.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Give it a moment to terminate before restarting
        time.sleep(0.5)
        
        subprocess.Popen([process_name])
        return f"Process found. Restarting {process_name}."
