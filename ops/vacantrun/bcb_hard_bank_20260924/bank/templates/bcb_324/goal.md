Run files from list of files as subprocesses at the same time.
The function should output with:
    list: The exit codes of the subprocesses.
You should write self-contained code starting with:
```
import subprocess
import time
import threading
def task_func(file_list):
```