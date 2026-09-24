import csv
from collections import Counter
import pandas as pd
import matplotlib.pyplot as plt

def task_func(file_path):
    if not file_path.endswith('.csv'):
        raise ValueError("File must have .csv extension")
    
    rows = []
    try:
        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                rows.append(tuple(row))
    except Exception as e:
        raise ValueError(f"Error reading CSV file: {e}")

    counts = Counter(rows)
    duplicates = {row: count for row, count in counts.items() if count > 1}
    
    if not duplicates:
        fig, ax = plt.subplots()
        return {}, ax

    # Convert duplicated rows into a pandas DataFrame
    df = pd.DataFrame(list(duplicates.items()), columns=['Row', 'Count'])
    
    # For plotting, we need a string representation of the row for the x-axis labels.
    # We'll join the elements of the tuple with a separator.
    df['Row_Label'] = df['Row'].apply(lambda x: " | ".join(map(str, x)))
    
    fig, ax = plt.subplots()
    ax.bar(df['Row_Label'], df['Count'])
    ax.set_ylabel('Count')
    ax.set_title('Duplicate Entries')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    return duplicates, ax
