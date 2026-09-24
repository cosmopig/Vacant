import os
import shutil
import random

def task_func(src_dir: str, dest_dir: str, seed:int = 100) -> str:
    random.seed(seed)
    
    # Get list of files in src_dir
    files = [f for f in os.listdir(src_dir) if os.path.isfile(os.path.join(src_dir, f))]
    
    if not files:
        return ""

    # Pick a random file
    filename = random.choice(files)
    
    # Move the file
    src_path = os.path.join(src_dir, filename)
    dest_path = os.path.join(dest_dir, filename)
    
    shutil.move(src_path, dest_path)
    
    return filename
