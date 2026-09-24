import warnings
import os
import glob
import shutil
import time

def task_func(SOURCE_DIR, DEST_DIR, EXTENSIONS):
    transferred_files = []
    
    # Ensure destination directory exists
    if not os.path.exists(DEST_DIR):
        os.makedirs(DEST_DIR)
        
    # Get all files in source directory
    for filename in os.listdir(SOURCE_DIR):
        source_path = os.path.join(SOURCE_DIR, filename)
        
        # Skip directories
        if not os.path.isfile(source_path):
            continue
            
        # Check if file has one of the specified extensions
        # We should check if it ends with any of the extensions in EXTENSIONS
        is_target = False
        for ext in EXTENSIONS:
            if filename.lower().endswith(ext.lower()):
                is_target = True
                break
        
        if is_target:
            dest_path = os.path.join(DEST_DIR, filename)
            try:
                shutil.move(source_path, dest_path)
                transferred_files.append(filename)
            except Exception as e:
                warnings.warn(f"Could not transfer file {filename}: {e}")
                
    return transferred_files
