import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
def task_func(data):
    # Convert data to a numeric array/series if it's in string format
    if isinstance(data, str):
        import re
        data_list = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", data)]
    else:
        data_list = data

    data_array = np.array(data_list)
    
    fig, ax = plt.subplots()
    
    # The goal specifies bins as `np.arange(data.min(), data.max()+2) - 0.5`
    d_min = data_array.min()
    d_max = data_array.max()
    
    bins = np.arange(d_min, d_max + 2) - 0.5
    
    ax.hist(data_array, bins=bins, edgecolor='black')
    ax.set_xlabel('Value')
    ax.set_ylabel('Frequency')
    ax.set_title('Histogram of Values')
    
    # Set x-ticks to the unique values in the data (sorted)
    unique_values = np.sort(np.unique(data_array))
    ax.set_xticks(unique_values)
    
    return ax
