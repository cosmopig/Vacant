Archive all files that match a particular pattern and then delete the original files.
Note that: This function will return the archive file path.
The function should output with:
    archive_file (str): The archive file path.
You should write self-contained code starting with:
```
import subprocess
import os
import glob
# Constants
ARCHIVE_DIR = '/tmp/archive'
def task_func(pattern):
```