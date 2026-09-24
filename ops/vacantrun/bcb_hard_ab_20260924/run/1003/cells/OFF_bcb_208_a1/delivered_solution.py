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
        "count": df["value"].count(),
        "mean": df["value"].mean(),
        "std": df["value"].std(),
        "min": df["value"].min(),
        "5%": df["value"].quantile(0.05),
        "25%": df["value"].quantile(0.25),
        "50%": df["value"].median(),
        "75%": df["value"].quantile(0.75),
        "95%": df["value"].quantile(0.95),
        "max": df["value"].max()
    }

    fig, ax = plt.subplots()
    ax.plot(walk)
    ax.set_title("Random Walk")
    ax.set_xlabel("Step")
    ax.set_ylabel("Value")

    return stats, ax
