import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def task_func(N=100, CATEGORIES=["A", "B", "C", "D", "E"], seed=42):
    np.random.seed(seed)
    
    # Generate random x and y values
    x = np.random.rand(N)
    y = np.random.rand(N)
    
    num_categories = len(CATEGORIES)
    if N >= num_categories:
        # Ensure each category appears at least once
        all_categories = list(CATEGORIES)
        remaining_count = N - num_categories
        # Randomly sample the remaining counts from CATEGORIES with replacement
        extra_categories = np.random.choice(CATEGORIES, size=remaining_count, replace=True)
        all_categories.extend(extra_categories.tolist())
        np.random.shuffle(all_categories)
    else:
        # Sample without replacement if N < num_categories
        all_categories = np.random.choice(CATEGORIES, size=N, replace=False).tolist()
        np.random.shuffle(all_categories)

    df = pd.DataFrame({
        "x": x,
        "y": y,
        "category": all_categories
    })

    # Plotting
    fig, ax = plt.subplots()
    for cat in CATEGORIES:
        subset = df[df["category"] == cat]
        if not subset.empty:
            ax.scatter(subset["x"], subset["y"], label=cat)
    
    ax.legend()
    return df, ax
