import csv
import math

# Load the data
data_file = 'data/imp.score.ldlr.metabolome.csv'
rows = []
with open(data_file, mode='r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

# Extract "row retention time" values
retention_times = [float(row['row retention time']) for row in rows]

# Calculate mean and standard deviation
n = len(retention_times)
if n == 0:
    removed_count = 0
else:
    mean = sum(retention_times) / n
    variance = sum((x - mean) ** 2 for x in retention_times) / (n - 1) if n > 1 else 0
    std = math.sqrt(variance)

    # Calculate Z-scores and count outliers
    removed_count = 0
    for x in retention_times:
        if std == 0:
            z_score = 0
        else:
            z_score = (x - mean) / std
        
        if z_score > 3 or z_score < -3:
            removed_count += 1

print(f"Removed outliers count: {removed_count}")
