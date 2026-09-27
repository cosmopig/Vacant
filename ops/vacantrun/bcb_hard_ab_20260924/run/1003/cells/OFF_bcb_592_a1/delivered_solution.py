import csv
import os
from datetime import datetime, timedelta
from random import randint

# Constants
SENSORS = ['Temperature', 'Humidity', 'Pressure']
OUTPUT_DIR = './output'

def task_func(hours, output_dir=OUTPUT_DIR):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    file_path = os.path.join(output_dir, 'sensor_data.csv')
    
    start_time = datetime.now()
    
    with open(file_path, mode='w', newline='') as csvfile:
        fieldnames = ['Time', 'Temperature', 'Humidity', 'Pressure']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for i in range(hours):
            current_time = start_time + timedelta(hours=i)
            data = {
                'Time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                'Temperature': randint(-20, 40),
                'Humidity': randint(0, 100),
                'Pressure': randint(950, 1050)
            }
            writer.writerow(data)
