import os
import csv
import random
from statistics import mean
# Constants
COLUMNS = ['Name', 'Age', 'Height', 'Weight']
PEOPLE_COUNT = 100
def task_func(filename):
    data = []
    ages = []
    heights = []
    weights = []

    for i in range(1, PEOPLE_COUNT + 1):
        name = f"Person {i}"
        age = random.randint(0, 100)
        height = random.uniform(140.0, 200.0)
        weight = random.uniform(40.0, 120.0)
        
        data.append([name, age, height, weight])
        ages.append(age)
        heights.append(height)
        weights.append(weight)

    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(COLUMNS)
        writer.writerows(data)
        
        avg_age = mean(ages)
        avg_height = mean(heights)
        avg_weight = mean(weights)
        writer.writerow(['Average', avg_age, avg_height, avg_weight])

    return filename
