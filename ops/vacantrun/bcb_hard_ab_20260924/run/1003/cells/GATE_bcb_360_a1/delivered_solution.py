import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

def task_func(file_location, sheet_name):
    if not os.path.exists(file_location):
        raise FileNotFoundError(f"The file {file_location} does not exist.")
    
    try:
        df = pd.read_excel(file_location, sheet_name=sheet_name)
    except ValueError as e:
        # pandas raises ValueError if the sheet name is not found
        raise ValueError(f"The specified sheet '{sheet_name}' does not exist in the workbook.") from e

    # Calculate mean and standard deviation for each column
    # We only consider numeric columns for calculation
    numeric_df = df.select_dtypes(include=[np.number])
    means = numeric_df.mean()
    std_devs = numeric_df.std(ddof=0)

    results = {}
    for col in means.index:
        results[col] = {
            "mean": float(means[col]),
            "std": float(std_devs[col])
        }

    # Draw a bar chart
    fig, ax = plt.subplots()
    
    # The goal says "draw a bar chart". It doesn't specify what to plot exactly.
    # I will plot means and standard deviations as two different bars for each column.
    x_labels = []
    values = []
    for col in means.index:
        x_labels.append(f"{col} Mean")
        values.append(means[col])
        x_labels.append(f"{col} Std Dev")
        values.append(std_devs[col])
    
    ax.bar(x_labels, values)
    ax.set_title('Mean and Standard Deviation')
    ax.set_xlabel('Columns')
    ax.set_ylabel('Values')

    return results, fig
