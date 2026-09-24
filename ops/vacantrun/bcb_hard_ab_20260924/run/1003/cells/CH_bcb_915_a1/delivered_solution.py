import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import zscore

def task_func(df, z_threshold=2):
    # Calculate Z-scores for the 'closing_price' column
    z_scores = zscore(df['closing_price'])
    
    # Identify outliers where absolute Z-score is greater than z_threshold
    outliers = df[np.abs(z_scores) > z_threshold].copy()
    outliers['Z_score'] = z_scores[np.abs(z_scores) > z_threshold]
    
    # Create the plot
    fig, ax = plt.subplots()
    ax.plot(df.index, df['closing_price'], label='Data')
    ax.scatter(outliers.index, outliers['closing_price'], color='red', label='Outliers')
    
    # Set labels and title as specified in the goal
    ax.set_xlabel('Index')
    ax.set_ylabel('Closing Price')
    ax.set_title('Outliers in Closing Prices')
    
    return outliers, ax
