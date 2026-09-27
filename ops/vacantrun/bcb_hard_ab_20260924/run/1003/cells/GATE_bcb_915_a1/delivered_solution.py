import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import zscore

def task_func(df, z_threshold=2):
    # Create a copy of the dataframe to avoid modifying the original input
    df_copy = df.copy()
    
    # Calculate Z-scores for the 'closing_price' column
    z_scores = zscore(df_copy['closing_price'])
    df_copy['Z_score'] = z_scores
    
    # Identify outliers
    outliers_mask = np.abs(df_copy['Z_score']) > z_threshold
    outlier_df = df_copy[outliers_mask].copy()
    
    # Create the plot
    fig, ax = plt.subplots()
    
    # Plot all data points
    ax.scatter(df_copy.index, df_copy['closing_price'], label='Data', alpha=0.6)
    
    # Plot outliers if any exist
    if not outlier_df.empty:
        ax.scatter(outlier_df.index, outlier_df['closing_price'], color='red', label='Outliers')
    
    # Set labels and title as required
    ax.set_xlabel('Index')
    ax.set_ylabel('Closing Price')
    ax.set_title('Outliers in Closing Prices')
    ax.legend()
    
    return outlier_df, ax
