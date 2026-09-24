import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def task_func(df: pd.DataFrame) -> tuple:
    # Create a figure with two subplots side by side
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))
    
    # Identify the column for closing prices. 'Close' is standard.
    if 'Close' in df.columns:
        data = df['Close']
    else:
        # If 'Close' is not found, try to find a numeric column that might be it
        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            data = df[numeric_cols[0]]
        else:
            raise ValueError("No numeric columns found in the DataFrame.")

    # Plot Box Plot
    sns.boxplot(x=data, ax=ax1)
    ax1.set_title('Box Plot of Closing Prices')
    
    # Plot Histogram
    sns.histplot(data, ax=ax2)
    ax2.set_title('Histogram of Closing Prices')
    
    return ax1, ax2
