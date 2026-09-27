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
    
    # Work on a copy to avoid modifying the original DataFrame
    df_copy = df.copy()
    
    # Round down ages to nearest integer
    df_copy['age'] = df_copy['age'].apply(np.floor).astype(int)
    
    # Identify duplicate names (names that appear more than once)
    duplicate_mask = df_copy.duplicated(subset=['name'], keep=False)
    duplicates_df = df_copy[duplicate_mask]
    
    if duplicates_df.empty:
        return Counter(), None
    
    # Age distribution among duplicates
    age_distribution = Counter(duplicates_df['age'])
    
    # Histogram plot
    min_age = int(duplicates_df['age'].min())
    max_age = int(duplicates_df['age'].max())
    
    # Bins calculation: adjusted by 0.5 to ensure integer ages fall squarely within bins
    # For example, if min=20 and max=30, we want [19.5, 20.5, ..., 30.5]
    bins = np.arange(min_age - 0.5, max_age + 1.5, 1)
    
    fig, ax = plt.subplots()
    sns.histplot(duplicates_df['age'], bins=bins, ax=ax)
    ax.set_xlabel('Age')
    ax.set_ylabel('Count')
    ax.set_title('Age Distribution')
    
    return age_distribution, ax
