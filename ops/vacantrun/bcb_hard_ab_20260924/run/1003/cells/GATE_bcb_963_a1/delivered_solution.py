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

    if not zip_name.lower().endswith('.zip'):
        zip_filename = f"{zip_name}.zip"
    else:
        zip_filename = zip_name
    
    zip_file_path = target_path / zip_filename
    
    valid_extensions = ('.txt', '.docx', '.xlsx', '.csv')
    
    with zipfile.ZipFile(str(zip_file_path), 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in glob.glob(str(source_path / '**/*'), recursive=True):
            p = Path(file_path)
            if p.is_file() and p.suffix.lower() in valid_extensions:
                relative_path = p.relative_to(source_path)
                zf.write(str(p), arcname=str(relative_path))
    
    return str(zip_file_path.resolve())
