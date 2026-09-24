import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def task_func(df: pd.DataFrame) -> tuple:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))
    
    sns.boxplot(data=df, x='closing_price', ax=ax1)
    ax1.set_title('Box Plot of Closing Prices')
    # Ensure xlabel is 'closing_price' as required by test
    ax1.set_xlabel('closing_price')
    
    sns.histplot(data=df, x='closing_price', ax=ax2)
    ax2.set_title('Histogram of Closing Prices')
    # sns.histplot usually sets xlabel to 'closing_price' and ylabel to 'Count' automatically
    
    return ax1, ax2
