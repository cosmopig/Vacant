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
        # Check if filename has '_processed' suffix
        # A suffix could be before the extension or at the end of the filename
        if re.search(r'_processed(\.[^.]+)?$', filename):
            processed_files.append(filename)
    
    with zipfile.ZipFile(archive_path, 'w') as zipf:
        for file in processed_files:
            file_path = os.path.join(source_dir, file)
            if os.path.isfile(file_path):
                zipf.write(file_path, arcname=file)
                
    return archive_path
