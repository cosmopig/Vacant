import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def task_func(column, data):
    if not data:
        raise ValueError("Data list is empty")

    df = pd.DataFrame(data)

    # Validate numeric values for steps, calories burned, and distance walked are non-negative
    numeric_cols = ['steps', 'calories burned', 'distance walked']
    for col in numeric_cols:
        if col in df.columns:
            if (df[col] < 0).any():
                raise ValueError(f"Negative value found in {col}")

    if column not in df.columns:
        raise KeyError(f"Column '{column}' not found in data")

    # Calculate statistics
    stats = {
        'sum': float(df[column].sum()),
        'mean': float(df[column].mean()),
        'min': float(df[column].min()),
        'max': float(df[column].max())
    }

    # Draw line chart
    fig, ax = plt.subplots()
    ax.plot(df['Date'], df[column])
    ax.set_title(f"Line Chart of {column}")
    ax.set_xlabel("Date")
    ax.set_ylabel(column)

    return stats, ax
