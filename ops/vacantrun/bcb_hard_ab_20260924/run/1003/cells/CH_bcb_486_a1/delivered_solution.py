from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def task_func(start_time, end_time, step, trend, seed=42):
    np.random.seed(seed)
    
    # Convert start and end to numeric timestamps (seconds since epoch)
    if isinstance(start_time, (int, float)):
        t_start = float(start_time)
    else:
        t_start = pd.to_datetime(start_time).timestamp()
        
    if isinstance(end_time, (int, float)):
        t_end = float(end_time)
    else:
        t_end = pd.to_datetime(end_time).timestamp()

    # Generate numeric times
    # We use a small epsilon to include the end_time if it's exactly on a step
    times_numeric = np.arange(t_start, t_end + step, step)
    times_numeric = times_numeric[times_numeric <= t_end]
    
    # Convert back to datetimes for plotting
    times = pd.to_datetime(times_numeric, unit='s')
    
    # Generate values from a normal distribution (standard normal: mean=0, std=1)
    n = len(times)
    noise = np.random.normal(loc=0.0, scale=1.0, size=n)
    
    # Add linear trend: value = noise + (t - t_start) * trend
    values = noise + (times_numeric - t_start) * trend
    
    # Plotting
    fig, ax = plt.subplots()
    ax.plot(times, values)
    ax.set_xlabel('Time')
    ax.set_ylabel('Value')
    
    return ax
