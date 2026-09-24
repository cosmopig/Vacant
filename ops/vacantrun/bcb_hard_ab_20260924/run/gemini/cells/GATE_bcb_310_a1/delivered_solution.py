import os
import csv
import random
from statistics import mean

# Constants
COLUMNS = ['Name', 'Age', 'Height', 'Weight']
PEOPLE_COUNT = 100

def task_func(filename):
    data = []
    for i in range(PEOPLE_COUNT):
        name = f"Person_{i}"
        age = random.randint(0, 100)
        height = random.uniform(100, 250)
        weight = random.uniform(30, 150)
        data.append([name, age, height, weight])

    with open(filename, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        writer.writerows(data)

        ages = [row[1] for row in data]
        heights = [row[2] for row in data]
        weights = [row[3] for row in data]

        avg_age = mean(ages)
        avg_height = mean(heights)
        avg_weight = mean(weights)

        writer.writerow(['Average', avg_age, avg_height, avg_weight])

    return filename
