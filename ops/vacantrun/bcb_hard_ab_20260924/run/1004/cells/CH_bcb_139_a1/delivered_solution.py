import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
def task_func(df):
    if df is None or df.empty:
        raise ValueError("Input must be a non-empty DataFrame.")
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not numeric_cols:
        raise ValueError("DataFrame must contain at least one numeric column.")
    
    axes = []
    for col in numeric_cols:
        fig, ax = plt.subplots()
        ax.hist(df[col].dropna(), bins=30)
        ax.set_title(col)
        ax.set_xlabel('Value')
        ax.set_ylabel('Frequency')
        axes.append(ax)
    
    return axes
