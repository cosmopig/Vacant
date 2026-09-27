import os
import shutil
import glob

def task_func(src_dir, dest_dir, ext):
    if not os.path.isdir(src_dir) or not os.path.isdir(dest_dir):
        raise FileNotFoundError("Source or destination directory does not exist")

    if ext == '':
        return []

    moved_files = []
    # Use glob to find files with the specified extension in src_dir
    pattern = os.path.join(src_dir, f"*{ext}")
    for file_path in glob.glob(pattern):
        if os.path.isfile(file_path):
            filename = os.path.basename(file_path)
            dest_path = os.path.join(dest_dir, filename)
            
            # If a file with the same name already exists in the destination directory, it is not moved.
            if not os.path.exists(dest_path):
                shutil.move(file_path, dest_path)
                moved_files.append(os.path.abspath(dest_path))
    
    return moved_files
