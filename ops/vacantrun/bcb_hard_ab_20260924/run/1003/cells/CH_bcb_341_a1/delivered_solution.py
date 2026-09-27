import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

def task_func(df, col):
    if not isinstance(df, pd.DataFrame):
        raise ValueError("Input df must be a DataFrame.")
    if df.empty:
        raise ValueError("Input df must not be empty.")
    if col not in df.columns:
        raise ValueError(f"Column '{col}' not found in DataFrame.")

    fig, (ax1, ax2) = plt.subplots(2, 1)

    # Histogram with KDE
    sns.histplot(df[col], kde=True, ax=ax1)

    # Box plot
    sns.boxplot(y=df[col], ax=ax2)

    return fig
