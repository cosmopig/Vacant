import os
from pathlib import Path
import shutil

def task_func(kwargs, target_dir="non_none_files"):
    source_dict = kwargs.get("source_dict", {})
    target_path = Path(target_dir)
    
    # Ensure the target directory exists
    if not target_path.exists():
        target_path.mkdir(parents=True, exist_ok=True)
    
    copied_files = []
    
    for file_path_str, content in source_dict.items():
        file_path = Path(file_path_str)
        
        # Check if the file exists and has content
        if file_path.exists() and file_path.stat().st_size > 0:
            # Determine target path
            target_file_path = target_path / file_path.name
            
            # Copy the file to the target directory
            shutil.copy2(file_path, target_file_path)
            copied_files.append(str(target_file_path.absolute()))
            
    return copied_files
