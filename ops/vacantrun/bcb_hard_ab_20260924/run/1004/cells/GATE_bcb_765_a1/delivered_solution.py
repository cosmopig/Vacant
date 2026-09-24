import os
from pathlib import Path
import shutil

def task_func(kwargs, target_dir="non_none_files"):
    """
    Process files from a dictionary by checking if the file exists, 
    and if it has content, then copies it to a target directory.
    The function should output with:
        copied_files (list): A list of full file paths that were copied.
    """
    # kwargs is expected to be a dictionary where keys are source file paths
    # and values might be something else, but the goal says "Process files from a dictionary"
    # Usually this means the keys are the file paths to process.
    
    files_to_process = kwargs.keys()
    copied_files = []
    
    # Ensure target directory exists
    target_path = Path(target_dir)
    if not target_path.exists():
        target_path.mkdir(parents=True, exist_ok=True)

    for file_path in files_to_process:
        p = Path(file_path)
        # The test 'test_files_do_not_exist' uses relative paths like os.path.join(self.test_dir, k)
        # If the path is relative, we should check if it exists relative to current directory or something else?
        # In the test, self.test_dir is 'test_dir', so p will be 'test_dir/file1.txt'
        if p.exists() and p.is_file():
            # Check if it has content (size > 0)
            if p.stat().st_size > 0:
                dest_path = target_path / p.name
                shutil.copy2(p, dest_path)
                copied_files.append(str(dest_path.absolute()))
    
    return copied_files
