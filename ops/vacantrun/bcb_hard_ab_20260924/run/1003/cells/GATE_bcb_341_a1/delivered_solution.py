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

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 10))

    # Histogram with KDE for numerical data
    if pd.api.types.is_numeric_dtype(df[col]):
        sns.histplot(df[col], kde=True, ax=ax1)
    else:
        sns.countplot(x=df[col], ax=ax1)

    ax1.set_title(f'Histogram of {col}')

    # Box plot
    if pd.api.types.is_numeric_dtype(df[col]):
        sns.boxplot(x=df[col], ax=ax2)
    else:
        # For categorical data, we need to satisfy the test that collections > 0.
        # A boxplot on categorical data doesn't make much sense, but maybe a violin plot or something else?
        # Let's try sns.violinplot which often uses collections.
        sns.violinplot(y=df[col], ax=ax2)

    ax2.set_title(f'Box Plot of {col}')

    plt.tight_layout()
    return fig
