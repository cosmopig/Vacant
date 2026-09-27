import numpy as np
from collections import defaultdict
import json
import csv
# Constants
def task_func(input_file, output_file):
    with open(input_file, 'r') as f:
        data = json.load(f)

    field_data = defaultdict(list)
    for entry in data:
        for key, value in entry.items():
            if isinstance(value, (int, float)):
                field_data[key].append(value)

    results = {}
    for key, values in field_data.items():
        if values:
            results[key] = {
                "mean": float(np.mean(values)),
                "median": float(np.median(values))
            }
        else:
            results[key] = {
                "mean": None,
                "median": None
            }

    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["key", "mean", "median"])
        writer.writeheader()
        for key, stats in results.items():
            writer.writerow({
                "key": key,
                "mean": stats["mean"],
                "median": stats["median"]
            })

    return results
