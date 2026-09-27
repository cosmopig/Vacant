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
    for col in numeric_df.columns:
        results[col] = {
            'mean': means[col],
            'std': std_devs[col]
        }

    # Draw a bar chart
    fig, ax = plt.subplots()
    
    x_labels = numeric_df.columns
    means_values = means.values
    std_devs_values = std_devs.values
    
    x = np.arange(len(x_labels))
    width = 0.35

    ax.bar(x - width/2, means_values, width, label='Mean')
    ax.bar(x + width/2, std_devs_values, width, label='Std Dev')

    ax.set_title('Mean and Standard Deviation')
    ax.set_xlabel('Columns')
    ax.set_ylabel('Values')
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels)
    ax.legend()

    plt.tight_layout()
    
    return results, fig
