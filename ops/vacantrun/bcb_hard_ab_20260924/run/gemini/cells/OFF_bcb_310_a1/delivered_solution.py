import os
import csv
import random
from statistics import mean
# Constants
COLUMNS = ['Name', 'Age', 'Height', 'Weight']
PEOPLE_COUNT = 100
def task_func(filename):
    people_data = []
    for i in range(1, PEOPLE_COUNT + 1):
        name = f"Person_{i}"
        age = random.randint(0, 100)
        height = random.uniform(140.0, 200.0)
        weight = random.uniform(40.0, 120.0)
        people_data.append([name, age, height, weight])

    with open(filename, mode='w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(COLUMNS)
        writer.writerows(people_data)

        ages = [row[1] for row in people_data]
        heights = [row[2] for row in people_data]
        weights = [row[3] for row in people_data]

        avg_age = mean(ages)
        avg_height = mean(heights)
        avg_weight = mean(weights)

        writer.writerow(['Average', avg_age, avg_height, avg_weight])

    return filename
