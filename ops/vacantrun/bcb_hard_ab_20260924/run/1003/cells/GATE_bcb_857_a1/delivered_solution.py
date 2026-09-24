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
        
    # Get all files in SOURCE_DIR
    all_files = glob.glob(os.path.join(SOURCE_DIR, "*"))
    
    for file_path in all_files:
        if os.path.isdir(file_path):
            continue
            
        filename = os.path.basename(file_path)
        # Check if the file has any of the specified extensions
        has_extension = any(filename.lower().endswith(ext.lower()) for ext in EXTENSIONS)
        
        if has_extension:
            try:
                shutil.copy2(file_path, os.path.join(DEST_DIR, filename))
                transferred_files.append(filename)
            except Exception as e:
                warnings.warn(f"Could not transfer {filename}: {e}")
                
    return transferred_files
