import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

def task_func(elements, seed=0):
    if not isinstance(elements, int) or elements <= 0:
        raise ValueError("elements must be a positive integer")

    np.random.seed(seed)
    steps = np.random.choice([-1, 1], size=elements)
    walk = np.cumsum(steps)
    
    df = pd.DataFrame(walk, columns=['value'])
    stats = {
        'count': df['value'].count(),
        'mean': df['value'].mean(),
        'standard deviation': df['value'].std(),
        'minimum': df['value'].min(),
        '5th percentile': df['value'].quantile(0.05),
        '25th percentile': df['value'].quantile(0.25),
        'median': df['value'].median(),
        '75th percentile': df['value'].quantile(0.75),
        '95th percentile': df['value'].quantile(0.95),
        'maximum': df['value'].max()
    }

    fig, ax = plt.subplots()
    ax.plot(walk)
    
    return stats, ax
