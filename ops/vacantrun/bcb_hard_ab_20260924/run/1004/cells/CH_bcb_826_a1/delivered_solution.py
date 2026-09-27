import re
import os
import shutil
def task_func(source_dir, target_dir, file_pattern=r'\b[A-Za-z0-9]+\.(txt|doc|docx)\b'):
    moved_files_count = 0
    
    # Ensure the target directory exists
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    # Iterate through files in source directory
    for filename in os.listdir(source_dir):
        file_path = os.path.join(source_dir, filename)
        
        # Check if it's a file and matches the pattern
        if os.path.isfile(file_path) and re.search(file_pattern, filename):
            target_path = os.path.join(target_dir, filename)
            try:
                shutil.move(file_path, target_path)
                moved_files_count += 1
            except Exception:
                # If move fails (e.g., file already exists in target), skip it or handle accordingly
                pass
                
    return moved_files_count
