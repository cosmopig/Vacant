import pandas as pd
import numpy as np
from collections import Counter
import seaborn as sns
import matplotlib.pyplot as plt

def task_func(df: pd.DataFrame) -> (Counter, plt.Axes):
    if df.empty:
        raise ValueError("DataFrame is empty")
    
    if (df['age'] < 0).any():
        raise ValueError("Age must not be negative")
    
    # Round down floats to nearest integer and convert to int
    df = df.copy()
    df['age'] = df['age'].apply(np.floor).astype(int)
    
    # Identify duplicate names (keep=False ensures all occurrences are included)
    duplicates = df[df.duplicated('name', keep=False)]
    
    if duplicates.empty:
        return Counter(), None
    
    # Age distribution for duplicate names
    ages = duplicates['age']
    age_counts = Counter(ages)
    
    # Plotting
    min_age = ages.min()
    max_age = ages.max()
    
    # Bins calculation: adjusted by .5 to ensure that integer ages fall squarely within bins.
    # For example, if min=10 and max=12, we want [9.5, 10.5, 11.5, 12.5]
    bins = np.arange(min_age - 0.5, max_age + 1.5, 1)
    
    fig, ax = plt.subplots()
    sns.histplot(ages, bins=bins, ax=ax)
    ax.set_xlabel('Age')
    ax.set_ylabel('Count')
    ax.set_title('Age Distribution')
    
    return age_counts, ax
