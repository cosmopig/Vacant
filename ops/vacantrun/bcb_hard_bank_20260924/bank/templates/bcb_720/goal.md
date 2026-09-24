Create and delete a CSV file "task_func_data/Output.txt" with sensor data for temperature and humidity. The data is generated randomly, written in append mode, and the file is deleted after use.
The function should output with:
    Returns the path to the CSV file "task_func_data/Output.txt" before deletion.
You should write self-contained code starting with:
```
import os
import csv
import random
from datetime import datetime
def task_func():
```