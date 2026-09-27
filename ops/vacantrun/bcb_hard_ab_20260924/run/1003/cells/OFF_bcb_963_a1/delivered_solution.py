import os
import glob
from pathlib import Path
import zipfile

def task_func(source_directory, target_directory, zip_name):
    if not os.path.exists(source_directory):
        raise OSError(f"Source directory {source_directory} does not exist.")

    target_path = Path(target_directory) / f"{zip_name}.zip"
    
    extensions = ('.txt', '.docx', '.xlsx', '.csv')
    files_to_zip = []
    for ext in extensions:
        # Use glob to find files with the extension. 
        # We should use os.path.join for cross-platform compatibility.
        pattern = os.path.join(source_directory, f"*{ext}")
        files_to_zip.extend(glob.glob(pattern))

    with zipfile.ZipFile(target_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in files_to_zip:
            # Use relpath to keep the structure relative to source_directory
            arcname = os.path.relpath(file_path, source_directory)
            zipf.write(file_path, arcname)

    return str(target_path.absolute())
