import pandas as pd
import numpy as np
from scipy.stats import zscore
from sklearn.preprocessing import MinMaxScaler

def task_func(data):
    # data is a list of tuples (item, count, weight)
    df = pd.DataFrame(data, columns=['Item', 'Count', 'Weight'])
    
    # Z-score normalization for counts
    # zscore returns an array, we can replace the column
    df['Normalized Count'] = zscore(df['Count'])
    
    # Min-max scaling for weights
    scaler = MinMaxScaler()
    # scaler.fit_transform expects a 2D array
    df['Normalized Weight'] = scaler.fit_transform(df[['Weight']])[:, 0]
    
    # The goal says: "returns a pandas DataFrame with the items, normalized counts, and normalized weights."
    # It also says: "DataFrame: A pandas DataFrame with three columns: 'Item', 'Normalized Count', and 'Normalized Weight'."
    return df[['Item', 'Normalized Count', 'Normalized Weight']]
