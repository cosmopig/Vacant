import pandas as pd
import numpy as np
from scipy.stats import zscore
from sklearn.preprocessing import MinMaxScaler

def task_func(data):
    # Create a DataFrame from the input list of tuples
    df = pd.DataFrame(data, columns=['Item', 'Count', 'Weight'])
    
    # Normalize counts using z-score normalization
    # scipy.stats.zscore returns an array with NaNs if standard deviation is zero
    normalized_counts = zscore(df['Count'])
    
    # Normalize weights using min-max scaling
    # MinMaxScaler expects a 2D array, so we use df[['Weight']]
    scaler = MinMaxScaler()
    normalized_weights = scaler.fit_transform(df[['Weight']])
    
    # Create the result DataFrame with specified column names
    result = pd.DataFrame({
        'Item': df['Item'],
        'Normalized Count': normalized_counts,
        'Normalized Weight': normalized_weights.flatten()
    })
    
    return result
