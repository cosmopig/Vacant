import re
import os
import zipfile

def task_func(directory, pattern=r'^(.*?)-\d+\.zip$'):
    extracted_dirs = set()
    
    if not os.path.isdir(directory):
        return []

    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        
        if os.path.isfile(filepath) and re.match(pattern, filename):
            # Split the filename at the last occurrence of "-"
            parts = filename.rsplit('-', 1)
            if len(parts) == 2:
                prefix_part = parts[0]
                target_dir = os.path.join(directory, prefix_part)
                
                # Create directory if it doesn't exist
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir)
                
                with zipfile.ZipFile(filepath, 'r') as zip_ref:
                    zip_ref.extractall(target_dir)
                
                extracted_dirs.add(target_dir)
                
    return list(extracted_dirs)
