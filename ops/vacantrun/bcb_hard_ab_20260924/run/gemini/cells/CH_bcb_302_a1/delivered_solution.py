import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Constants
COLUMNS = ['Date', 'Value']

def task_func(df, plot=False):
    if df.empty:
        raise ValueError("DataFrame is empty")
    
    if 'Value' not in df.columns:
        raise ValueError("DataFrame must contain 'Value' column")

    # Validate that all entries in 'Value' are lists
    if not df['Value'].apply(lambda x: isinstance(x, list)).all():
        raise ValueError("All entries in 'Value' column must be lists")

    # Expand the lists in 'Value' into separate columns
    expanded_df = pd.DataFrame(df['Value'].tolist(), index=df.index)

    # Calculate Pearson correlation coefficient
    corr_matrix = expanded_df.corr(method='pearson')

    if plot:
        fig, ax = plt.subplots()
        sns.heatmap(corr_matrix, ax=ax)
        ax.set_title("Correlation Heatmap")
        return corr_matrix, ax
    
    return corr_matrix
