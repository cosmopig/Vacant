import os
from pathlib import Path
import shutil

def task_func(kwargs, target_dir="non_none_files"):
    """
    Process files from a dictionary by checking if the file exists, 
    and if it has content, then copies it to a target directory.
    The function should output with:
        copied_files (list): A list of full file paths that were copied.
    """
    source_files = kwargs
    target_path = Path(target_dir).resolve()
    
    # Ensure target directory exists
    if not target_path.exists():
        target_path.mkdir(parents=True, exist_ok=True)
        
    copied_files = []
    
    for src_rel_path, content in source_files.items():
        src_path = Path(src_rel_path)
        
        # Check if file exists and has content
        if src_path.exists() and src_path.stat().st_size > 0:
            dest_path = target_path / src_path.name
            
            shutil.copy2(src_path, dest_path)
            copied_files.append(str(dest_path.resolve()))
            
    return {"copied_files": copied_files}
