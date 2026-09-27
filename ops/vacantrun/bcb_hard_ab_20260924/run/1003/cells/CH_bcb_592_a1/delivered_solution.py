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
    
    filename = os.path.join(output_dir, 'sensor_data.csv')
    
    with open(filename, mode='w', newline='') as csvfile:
        fieldnames = ['Time', 'Temperature', 'Humidity', 'Pressure']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        start_time = datetime.now()
        for i in range(hours):
            current_time = (start_time + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M:%S')
            writer.writerow({
                'Time': current_time,
                'Temperature': randint(15, 30),
                'Humidity': randint(30, 70),
                'Pressure': randint(980, 1020)
            })

