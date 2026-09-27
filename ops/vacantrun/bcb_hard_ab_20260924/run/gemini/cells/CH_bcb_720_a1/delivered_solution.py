import os
import csv
import random
from datetime import datetime

def task_func():
    file_path = 'task_func_data/Output.txt'
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, mode='a', newline='') as f:
        writer = csv.writer(f)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        temperature = random.uniform(20, 30)
        humidity = random.uniform(50, 60)
        writer.writerow([timestamp, temperature, humidity])
        
    return file_path
