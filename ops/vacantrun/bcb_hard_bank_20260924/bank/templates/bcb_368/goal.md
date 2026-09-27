Moves a random file from the source directory to the specified destination directory.
The function should output with:
    str: The name of the file moved. Format: 'filename.extension' (e.g., 'file1.txt').
You should write self-contained code starting with:
```
import os
import shutil
import random
def task_func(src_dir: str, dest_dir: str, seed:int = 100) -> str:
```