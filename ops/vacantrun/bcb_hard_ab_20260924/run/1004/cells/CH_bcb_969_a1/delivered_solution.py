import numpy as np
from sklearn.preprocessing import MinMaxScaler
import pandas as pd

def task_func(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        raise ValueError("The DataFrame is empty.")
    
    if df.isnull().values.any():
        raise ValueError("The DataFrame contains NaN values.")
    
    if not all(pd.api.types.is_numeric_dtype(df[col]) for col in df.columns):
        raise TypeError("The DataFrame contains non-numeric data types.")

    # Compute cumulative sum
    cumsum_df = df.cumsum()

    # Normalize each column using MinMaxScaler
    normalized_df = pd.DataFrame(index=df.index, columns=df.columns)
    
    for col in df.columns:
        scaler = MinMaxScaler()
        col_data = cumsum_df[col].values.reshape(-1, 1)
        # If all values are the same (e.g., all zeros), fit_transform returns all zeros
        normalized_df[col] = scaler.fit_transform(col_data).flatten()

    return normalized_df
