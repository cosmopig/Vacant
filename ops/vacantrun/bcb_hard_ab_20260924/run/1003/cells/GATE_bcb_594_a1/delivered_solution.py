import csv
import os
import shutil
from datetime import datetime, timedelta
from random import randint
# Constants
WEATHER_CONDITIONS = ['Sunny', 'Cloudy', 'Rainy', 'Snowy', 'Stormy']
OUTPUT_DIR = './output'
def task_func(hours, output_dir=OUTPUT_DIR):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    filename = "weather_data.csv"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, mode='w', newline='') as csvfile:
        fieldnames = ['Time', 'Condition']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        start_time = datetime.now()
        for i in range(hours):
            current_time = (start_time + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M:%S')
            condition = randint(0, len(WEATHER_CONDITIONS) - 1)
            writer.writerow({'Time': current_time, 'Condition': WEATHER_CONDITIONS[condition]})
            
    backup_dir = os.path.join(OUTPUT_DIR, 'backup/')
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    shutil.copy(filepath, backup_dir)
    
    return filepath
