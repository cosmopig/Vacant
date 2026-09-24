import numpy as np
from collections import Counter
from scipy.stats import norm
import matplotlib.pyplot as plt

def task_func(df, bins=4):
    # Identify and count duplicate values in a DataFrame's 'value' column.
    counts = Counter(df['value'])
    duplicates = Counter({k: v for k, v in counts.items() if v > 1})

    # Plotting the histogram
    fig, ax = plt.subplots()
    data = df['value'].values
    
    # Histogram of all values
    ax.hist(data, bins=bins, color='green', alpha=0.6)

    # Overlay a normal distribution curve if applicable (i.e., data has variance)
    if np.std(data) > 0:
        mu, std = norm.fit(data)
        x = np.linspace(min(data), max(data), 100)
        p = norm.pdf(x, mu, std)
        ax.plot(x, p, 'k-', linewidth=2)

    # Set labels and title
    ax.set_title("Distribution")
    ax.set_xlabel("Value")
    ax.set_ylabel("Frequency")

    return duplicates, ax
