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
    
    # Generate data
    now = datetime.now()
    data = []
    for i in range(hours):
        current_time = (now + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S")
        condition = randint(0, len(WEATHER_CONDITIONS) - 1)
        data.append([current_time, WEATHER_CONDITIONS[condition]])
    
    # Write to CSV
    with open(filepath, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Time', 'Condition'])
        writer.writerows(data)
    
    # Backup
    backup_dir = os.path.join(output_dir, 'backup')
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    if not backup_dir.endswith('/'):
        backup_dir += '/'
    
    shutil.copy(filepath, backup_dir)
    
    return filepath
