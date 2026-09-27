import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

def task_func(original):
    # Extract numeric values from the list of tuples
    numeric_values = []
    for t in original:
        for item in t:
            # Check if item is a number and not a boolean
            if isinstance(item, (int, float, np.number)) and not isinstance(item, bool):
                numeric_values.append(item)
    
    arr = np.array(numeric_values)
    
    # Compute basic statistics
    mean_val = np.mean(arr)
    std_val = np.std(arr)
    min_val = np.min(arr)
    max_val = np.max(arr)
    
    stats_dict = {
        'mean': mean_val,
        'std': std_val,
        'min': min_val,
        'max': max_val
    }
    
    # Generate the histogram and overlaid PDF
    fig, ax = plt.subplots()
    ax.hist(arr, bins='auto', density=True, alpha=0.6)
    
    # Overlaid PDF (Normal distribution)
    x = np.linspace(min_val, max_val, 100)
    pdf = stats.norm.pdf(x, mean_val, std_val)
    ax.plot(x, pdf, 'k', linewidth=2)
    ax.set_title('Histogram with PDF')
    
    return arr, stats_dict, ax
