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

    # Calculate sum, mean, min, max of the specified column
    stats = {
        'sum': df[column].sum(),
        'mean': df[column].mean(),
        'min': df[column].min(),
        'max': df[column].max()
    }

    # Draw a line chart
    fig, ax = plt.subplots()
    ax.plot(df['Date'], df[column])
    ax.set_xlabel('Date')
    ax.set_ylabel(column)
    ax.set_title(f'Line Chart of {column}')

    return stats, ax
