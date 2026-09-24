import csv
from collections import Counter
import pandas as pd
import matplotlib.pyplot as plt

def task_func(file_path):
    if not file_path.endswith('.csv'):
        raise ValueError("File must have a .csv extension.")

    with open(file_path, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = [tuple(row) for row in reader]

    # Count occurrences of each row
    counts = Counter(rows)
    
    # Identify duplicates (count > 1)
    duplicates = {row: count for row, count in counts.items() if count > 1}
    
    if not duplicates:
        df = pd.DataFrame(columns=['Row', 'Count'])
    else:
        # Prepare data for DataFrame
        data = []
        for row, count in duplicates.items():
            # Convert tuple to string representation for the plot/dataframe
            data.append({'Row': str(row), 'Count': count})
        df = pd.DataFrame(data)

    # Plotting
    fig, ax = plt.subplots()
    if not df.empty:
        ax.bar(df['Row'], df['Count'])
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        ax.set_title("Duplicate Entries")
        ax.set_ylabel("Count")
    else:
        # If no duplicates, the plot will be empty but we still return the axes
        pass

    return duplicates, ax
