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

    stats = {}
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            stats[col] = {
                'mean': df[col].mean(),
                'std': df[col].std(ddof=0)
            }

    cols = list(stats.keys())
    means = [stats[col]['mean'] for col in cols]
    stds = [stats[col]['std'] for col in cols]

    fig, ax = plt.subplots()
    x = np.arange(len(cols))
    width = 0.35

    ax.bar(x - width/2, means, width, label='Mean')
    ax.bar(x + width/2, stds, width, label='Std Dev')

    ax.set_title('Mean and Standard Deviation')
    ax.set_xlabel('Columns')
    ax.set_ylabel('Values')
    ax.set_xticks(x)
    ax.set_xticklabels(cols)
    ax.legend()

    plt.tight_layout()
    
    return stats, fig
