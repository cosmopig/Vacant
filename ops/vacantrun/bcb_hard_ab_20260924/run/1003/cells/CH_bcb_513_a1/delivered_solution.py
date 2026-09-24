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
                raise ValueError(f"Negative values found in column '{col}'")

    # Calculate stats for the specified column
    # This will naturally raise a KeyError if 'column' is not in df.columns
    column_data = df[column]
    stats = {
        'sum': float(column_data.sum()),
        'mean': float(column_data.mean()),
        'min': float(column_data.min()),
        'max': float(column_data.max())
    }

    # Draw line chart
    fig, ax = plt.subplots()
    ax.plot(df['Date'], df[column])
    ax.set_title(f"Line Chart of {column}")
    ax.set_xlabel("Date")
    ax.set_ylabel(column)

    return stats, ax
