import numpy as np
from collections import defaultdict
import json
import csv
# Constants
def task_func(input_file, output_file):
    with open(input_file, 'r') as f:
        data = json.load(f)

    key_values = defaultdict(list)
    for entry in data:
        for key, value in entry.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                key_values[key].append(value)

    results = {}
    # Sort keys to ensure consistent order in CSV and return dict if needed
    sorted_keys = sorted(key_values.keys())
    
    for key in sorted_keys:
        values = key_values[key]
        if values:
            mean_val = np.mean(values)
            median_val = np.median(values)
            results[key] = {
                "mean": float(mean_val),
                "median": float(median_val)
            }

    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["key", "mean", "median"])
        for key in sorted(results.keys()):
            writer.writerow([key, results[key]["mean"], results[key]["median"]])

    return results
