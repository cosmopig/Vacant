import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import zscore

def task_func(df, z_threshold=2):
    import pandas as pd
    # Calculate Z-scores for the 'closing_price' column
    z_scores = zscore(df['closing_price'])
    
    # Add Z-scores to the DataFrame
    df['Z_score'] = z_scores
    
    # Identify outliers where the absolute Z-score exceeds the threshold
    outliers = df[np.abs(df['Z_score']) > z_threshold]
    
    # Create a plot to display the data and highlight the outliers
    fig, ax = plt.subplots()
    ax.plot(df.index, df['closing_price'])
    ax.scatter(outliers.index, outliers['closing_price'], color='red')
    
    # Set labels and title as specified in the goal
    ax.set_xlabel('Index')
    ax.set_ylabel('Closing Price')
    ax.set_title('Outliers in Closing Prices')
    
    return outliers, ax
