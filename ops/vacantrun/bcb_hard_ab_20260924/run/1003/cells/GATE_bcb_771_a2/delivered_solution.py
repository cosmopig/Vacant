import re
import os
from pathlib import Path
import csv

def task_func(directory: str, pattern: str = r'^(.*?)-\d+\.csv$') -> list:
    new_files = []
    if not os.path.isdir(directory):
        return new_files

    for filename in os.listdir(directory):
        match = re.match(pattern, filename)
        if match:
            prefix = match.group(1)
            # The part after the prefix starts with a hyphen followed by digits and .csv
            new_name = prefix + "_" + filename[len(prefix):]
            file_path = os.path.join(directory, filename)
            new_file_path = os.path.join(directory, new_name)
            
            if new_file_path != file_path:
                with open(file_path, 'r', encoding='utf-8') as f_in:
                    content = f_in.read()
                with open(new_file_path, 'w', encoding='utf-8') as f_out:
                    f_out.write(content)
                new_files.append(new_name)
    
    return new_files
