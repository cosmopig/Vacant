import csv
import os
import shutil
from datetime import datetime, timedelta
from random import randint
# Constants
WEATHER_CONDITIONS = ['Sunny', 'Cloudy', 'Rainy', 'Snowy', 'Stormy']
OUTPUT_DIR = './output'

def task_func(hours, output_dir=OUTPUT_DIR):
    # Ensure the output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Define the filename
    filename = f"weather_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    file_path = os.path.join(output_dir, filename)
    
    # Generate weather data
    data = []
    base_time = datetime.now()
    for i in range(hours):
        current_time = (base_time + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M:%S')
        condition = randint(0, len(WEATHER_CONDITIONS) - 1)
        data.append([current_time, WEATHER_CONDITIONS[condition]])
    
    # Write to CSV
    with open(file_path, mode='w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Time', 'Condition'])
        writer.writerows(data)
    
    # Backup the file
    backup_dir = './backup'
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    shutil.copy2(file_path, os.path.join(backup_dir, filename))
    
    return file_path
