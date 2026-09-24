import zipfile
import os
import re
import shutil

def task_func(source_dir: str, target_dir: str, archive_name: str = 'archive.zip') -> str:
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    
    archive_path = os.path.join(target_dir, archive_name)
    
    processed_files = []
    for filename in os.listdir(source_dir):
        file_path = os.path.join(source_dir, filename)
        if os.path.isfile(file_path):
            # Check if '_processed' is a suffix in the filename.
            if re.search(r'_processed(\.[^.]+)?$', filename):
                processed_files.append(file_path)
    
    with zipfile.ZipFile(archive_path, 'w') as zipf:
        for file in processed_files:
            zipf.write(file, os.path.basename(file))
            
    return archive_path
