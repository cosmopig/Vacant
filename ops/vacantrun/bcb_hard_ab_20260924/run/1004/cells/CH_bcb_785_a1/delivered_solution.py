import subprocess
import os
import glob

# Constants
ARCHIVE_DIR = '/tmp/archive'

def task_func(pattern):
    """
    Archive all files that match a particular pattern and then delete the original files.
    Returns the archive file path.
    """
    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)

    files = glob.glob(pattern)
    if not files:
        return None

    archive_path = os.path.join(ARCHIVE_DIR, 'archive.tar.gz')
    
    # If archive already exists, remove it to start fresh or handle accordingly.
    # For this task, we'll just overwrite/create a new one.
    if os.path.exists(archive_path):
        os.remove(archive_path)

    try:
        # Use tar to archive the files. 
        # -c: create, -z: gzip, -f: file
        # We use absolute paths for safety in some environments, but glob might return relative.
        # Let's ensure we handle the list of files correctly.
        subprocess.run(['tar', '-czf', archive_path] + files, check=True)
        
        for f in files:
            if os.path.isfile(f):
                os.remove(f)
        
        return archive_path
    except Exception as e:
        # In a real scenario, we might want to handle this more gracefully.
        return None
