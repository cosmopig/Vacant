Count the number of words in .txt files within a specified directory, export the counts to a JSON file, and then return the total number of words.
The function should output with:
    int: total number of words in .txt files
You should write self-contained code starting with:
```
from collections import Counter
import os
import json
def task_func(filename, directory):
```