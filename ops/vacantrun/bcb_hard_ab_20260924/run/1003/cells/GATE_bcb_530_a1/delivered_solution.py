import pandas as pd
import numpy as np
from collections import Counter
import seaborn as sns
import matplotlib.pyplot as plt

def task_func(df: pd.DataFrame) -> (Counter, plt.Axes):
    if df.empty:
        raise ValueError("The DataFrame is empty.")
    
    if (df['age'] < 0).any():
        raise ValueError("Age must not be negative.")
    
    # Round down float ages to the nearest integer and ensure they are integers
    # We work on a copy to avoid modifying the original dataframe
    df_processed = df.copy()
    df_processed['age'] = np.floor(df_processed['age']).astype(int)
    
    # Identify duplicate names (keep=False ensures all occurrences of duplicates are marked)
    duplicates = df_processed[df_processed.duplicated(subset='name', keep=False)]
    
    if duplicates.empty:
        return Counter(), None
    
    duplicate_ages = duplicates['age']
    counts = Counter(duplicate_ages)
    
    min_age = int(duplicate_ages.min())
    max_age = int(duplicate_ages.max())
    
    # Bins are calculated based on the minimum and maximum ages found among the duplicates, 
    # adjusted by .5 to ensure that integer ages fall squarely within bins.
    # For example, if min=10 and max=20, we want edges [9.5, 10.5, ..., 20.5]
    bins = np.arange(min_age - 0.5, max_age + 1.5, 1)
    
    fig, ax = plt.subplots()
    ax.hist(duplicate_ages, bins=bins, edgecolor='black')
    ax.set_xlabel('Age')
    ax.set_ylabel('Count')
    ax.set_title('Age Distribution for Duplicate Names')
    
    return counts, ax
