import os
import csv
import random
from datetime import datetime

def task_func():
    path = "task_func_data/Output.txt"
    os.makedirs("task_func_data", exist_ok=True)
    
    file_exists = os.path.exists(path)
    
    with open(path, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['Timestamp', 'Temperature', 'Humidity'])
        
        timestamp = datetime.now().isoformat()
        temp = random.uniform(20, 30)
        humidity = random.uniform(50, 60)
        writer.writerow([timestamp, temp, humidity])
    
    return path
