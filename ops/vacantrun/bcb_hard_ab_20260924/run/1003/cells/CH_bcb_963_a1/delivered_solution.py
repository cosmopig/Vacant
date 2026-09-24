import os
import glob
from pathlib import Path
import zipfile

def task_func(source_directory, target_directory, zip_name):
    source_path = Path(source_directory)
    if not source_path.exists():
        raise OSError(f"Source directory {source_directory} does not exist.")
    
    target_path = Path(target_directory)
    # Ensure target directory exists
    target_path.mkdir(parents=True, exist_ok=True)
    
    # Determine the zip file name
    if not zip_name.endswith('.zip'):
        zip_filename = f"{zip_name}.zip"
    else:
        zip_filename = zip_name
        
    zip_full_path = target_path / zip_filename
    
    extensions = ('.txt', '.docx', '.xlsx', '.csv')
    files_to_zip = []
    for ext in extensions:
        # Use glob to find files with the extension in the source directory
        pattern = os.path.join(source_directory, f"*{ext}")
        files_to_zip.extend(glob.glob(pattern))

    with zipfile.ZipFile(str(zip_full_path), 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in files_to_zip:
            if os.path.isfile(file):
                file_path = Path(file)
                # Use the filename only for arcname to avoid including full path inside zip
                zipf.write(file, arcname=file_path.name)

    return str(zip_full_path.absolute())
