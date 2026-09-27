import re
import os
import zipfile

def task_func(directory, pattern=r'^(.*?)-\d+\.zip$'):
    extracted_dirs = []
    if not os.path.isdir(directory):
        return extracted_dirs

    for filename in os.listdir(directory):
        if filename.endswith('.zip') and re.match(pattern, filename):
            parts = filename.rsplit('-', 1)
            if len(parts) == 2:
                prefix = parts[0]
                target_dir = os.path.join(directory, prefix)
                
                # Ensure the directory exists
                os.makedirs(target_dir, exist_ok=True)
                
                zip_path = os.path.join(directory, filename)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(target_dir)
                
                extracted_dirs.append(target_dir)
    
    return extracted_dirs
