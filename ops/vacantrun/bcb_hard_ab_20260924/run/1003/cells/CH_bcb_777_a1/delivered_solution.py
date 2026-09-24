import re
import os
import zipfile

def task_func(directory, pattern=r'^(.*?)-\d+\.zip$'):
    extracted_dirs = []
    # List all files in the directory
    try:
        files = os.listdir(directory)
    except FileNotFoundError:
        return extracted_dirs

    for filename in files:
        if filename.endswith('.zip'):
            match = re.match(pattern, filename)
            if match:
                prefix = match.group(1)
                # The directory name is the prefix part of the filename
                target_dir = os.path.join(directory, prefix)
                
                # Create target directory if it doesn't exist
                os.makedirs(target_dir, exist_ok=True)
                
                # Extract zip file
                zip_path = os.path.join(directory, filename)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(target_dir)
                
                extracted_dirs.append(target_dir)
    
    return extracted_dirs
