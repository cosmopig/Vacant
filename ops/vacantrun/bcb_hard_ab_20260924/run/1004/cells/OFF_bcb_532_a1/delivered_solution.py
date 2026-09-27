import numpy as np
from collections import Counter
from scipy.stats import norm
import matplotlib.pyplot as plt

def task_func(df, bins=4):
    # Identify and count duplicate values in a DataFrame's 'value' column.
    counts = Counter(df['value'])
    duplicates = {val: count for val, count in counts.items() if count > 1}

    # Plotting the histogram
    fig, ax = plt.subplots()
    data = df['value'].values
    
    # Histogram bars are green with 60% opacity
    ax.hist(data, bins=bins, color='green', alpha=0.6)

    # Overlay a normal distribution curve
    if len(np.unique(data)) > 1:
        mu, std = norm.fit(data)
        x = np.linspace(min(data), max(data), 100)
        bin_width = (max(data) - min(data)) / bins
        p = norm.pdf(x, mu, std) * bin_width * len(data)
        ax.plot(x, p, color='black', linewidth=2)

    # Set labels and title
    ax.set_title("Distribution")
    ax.set_xlabel("Value")
    ax.set_ylabel("Frequency")

    return duplicates, ax
