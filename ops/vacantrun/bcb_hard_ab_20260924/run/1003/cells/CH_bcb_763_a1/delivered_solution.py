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
        if isinstance(entry, list):
            for item in entry:
                if isinstance(item, dict):
                    for key, value in item.items():
                        if isinstance(value, (int, float)) and not isinstance(value, bool):
                            key_values[key].append(value)
        elif isinstance(entry, dict):
            for key, value in entry.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    key_values[key].append(value)

    stats = {}
    # We need to maintain some order if possible, but dictionary is fine for return
    # Let's sort keys alphabetically for the CSV output
    sorted_keys = sorted(key_values.keys())

    for key in sorted_keys:
        values = key_values[key]
        if values:
            arr = np.array(values)
            mean_val = float(np.mean(arr))
            median_val = float(np.median(arr))
            stats[key] = {
                "mean": mean_val,
                "median": median_val
            }

    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["key", "mean", "median"])
        for key in sorted_keys:
            if key in stats:
                writer.writerow([key, stats[key]["mean"], stats[key]["median"]])

    return stats
