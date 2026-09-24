import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def task_func(df: pd.DataFrame) -> tuple:
    # The test case uses 'closing_price' column
    col = 'closing_price'
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 10))
    
    sns.boxplot(y=df[col], ax=ax1)
    ax1.set_title('Box Plot of Closing Prices')
    
    sns.histplot(df[col], ax=ax2)
    ax2.set_title('Histogram of Closing Prices')
    
    plt.tight_layout()
    return (ax1, ax2)
