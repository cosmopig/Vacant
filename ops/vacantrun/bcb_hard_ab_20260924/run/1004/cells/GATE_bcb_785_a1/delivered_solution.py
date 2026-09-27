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

    # Create a unique name for the archive based on the pattern or some other identifier
    # Since we need to return "the" archive file path, and there might be multiple matches,
    # let's create an archive containing all matching files.
    archive_name = f"archive_{hash(pattern)}.tar.gz"
    archive_path = os.path.join(ARCHIVE_DIR, archive_name)

    # Use tar to archive the files and delete them (using --remove-files flag in tar)
    # However, we need to be careful with glob patterns that might expand to directories.
    # The goal says "Archive all files", so let's filter for files only.
    files_to_archive = [f for f in files if os.path.isfile(f)]

    if not files_to_archive:
        return None

    try:
        # Use subprocess to call tar
        # -c: create, -z: gzip, -f: file
        # --remove-files: delete files after they are added to the archive
        subprocess.run(['tar', '-czf', archive_path] + files_to_archive + ['--remove-files'], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error during archiving: {e}")
        return None

    return archive_path
