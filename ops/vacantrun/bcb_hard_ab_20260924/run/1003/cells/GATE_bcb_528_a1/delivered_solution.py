import csv
from collections import Counter
import pandas as pd
import matplotlib.pyplot as plt

def task_func(file_path):
    if not file_path.endswith('.csv'):
        raise ValueError("File must have a .csv extension.")
    
    try:
        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = [tuple(row) for row in reader]
    except Exception as e:
        raise ValueError(f"Invalid CSV format: {e}")

    counts = Counter(rows)
    duplicates = {row: count for row, count in counts.items() if count > 1}
    
    # Convert to DataFrame
    df = pd.DataFrame([list(item) for item in duplicates.items()], columns=['Row', 'Count'])
    
    # Plotting
    fig, ax = plt.subplots()
    if not df.empty:
        # Use a string representation of the tuple as labels to avoid issues with plotting tuples directly
        df['Label'] = df['Row'].apply(lambda x: str(x))
        df.plot(kind='bar', x='Label', y='Count', ax=ax)
        ax.set_title("Duplicate Entries")
        ax.set_ylabel("Count")
    else:
        # If no duplicates, we still return the axes object as required.
        pass

    return duplicates, ax
