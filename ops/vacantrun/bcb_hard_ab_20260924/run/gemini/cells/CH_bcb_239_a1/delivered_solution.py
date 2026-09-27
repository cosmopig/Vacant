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
    
    data = np.array(numeric_values)
    
    # Compute basic statistics
    stats_dict = {
        'mean': np.mean(data),
        'std': np.std(data),
        'min': np.min(data),
        'max': np.max(data)
    }
    
    # Generate histogram and PDF
    fig, ax = plt.subplots()
    ax.set_title('Histogram with PDF')
    
    # Plot histogram with density=True, alpha=0.6, and bins='auto'
    ax.hist(data, bins='auto', density=True, alpha=0.6)
    
    # Overlay PDF using a normal distribution fit
    mu, std = stats.norm.fit(data)
    x = np.linspace(np.min(data), np.max(data), 100)
    p = stats.norm.pdf(x, mu, std)
    ax.plot(x, p, 'k', linewidth=2)
    
    return data, stats_dict, ax
