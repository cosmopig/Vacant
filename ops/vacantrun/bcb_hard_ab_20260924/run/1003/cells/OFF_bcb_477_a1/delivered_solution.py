import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def task_func(N=100, CATEGORIES=["A", "B", "C", "D", "E"], seed=42):
    np.random.seed(seed)
    
    x = np.random.rand(N)
    y = np.random.rand(N)
    
    if N >= len(CATEGORIES):
        categories_list = list(CATEGORIES)
        remaining = N - len(CATEGORIES)
        extra_categories = np.random.choice(CATEGORIES, size=remaining)
        categories_list.extend(extra_categories.tolist())
        np.random.shuffle(categories_list)
    else:
        # Sample without replacement from CATEGORIES
        categories_list = np.random.choice(CATEGORIES, size=N, replace=False).tolist()
        
    df = pd.DataFrame({
        'x': x,
        'y': y,
        'category': categories_list
    })
    
    fig, ax = plt.subplots()
    unique_categories = sorted(df['category'].unique())
    # Use a colormap to assign colors to each category
    cmap = plt.get_cmap('tab10')
    colors = cmap(np.linspace(0, 1, len(unique_categories)))
    color_map = dict(zip(unique_categories, colors))
    
    ax.scatter(df['x'], df['y'], c=df['category'].map(color_map))
    
    return df, ax
