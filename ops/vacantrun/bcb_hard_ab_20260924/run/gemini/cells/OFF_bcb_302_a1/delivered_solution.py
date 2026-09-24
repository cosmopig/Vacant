import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Constants
COLUMNS = ['Date', 'Value']

def task_func(df, plot=False):
    if df.empty:
        raise ValueError("DataFrame is empty")
    
    if 'Value' not in df.columns:
        raise ValueError("Column 'Value' not found")
    
    # Check if all elements in 'Value' are lists
    for val in df['Value']:
        if not isinstance(val, list):
            raise ValueError("All elements in 'Value' column must be lists")
    
    # Convert 'Value' column to a DataFrame where each element of the list is a column
    try:
        values_list = df['Value'].tolist()
        values_df = pd.DataFrame(values_list)
    except Exception:
        raise ValueError("Invalid 'Value' column content")

    # Calculate Pearson correlation
    corr_df = values_df.corr()

    if plot:
        fig, ax = plt.subplots()
        sns.heatmap(corr_df, ax=ax)
        ax.set_title("Correlation Heatmap")
        return corr_df, ax
    
    return corr_df
