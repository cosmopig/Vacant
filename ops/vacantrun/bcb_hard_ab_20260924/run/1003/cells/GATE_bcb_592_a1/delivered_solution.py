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

    with open(file_path, mode='w', newline='') as f:
        writer = csv.writer(f)
        # Write header
        writer.writerow(['Time', 'Temperature', 'Humidity', 'Pressure'])

        # Generate data for each hour
        current_time = datetime.now()
        for i in range(hours):
            timestamp = (current_time + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M:%S')
            temperature = randint(15, 30)
            humidity = randint(30, 70)
            pressure = randint(980, 1020)
            writer.writerow([timestamp, temperature, humidity, pressure])
