import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def task_func(column, data):
    cols = ['Age', 'Salary', 'Experience']
    df = pd.DataFrame(data, columns=cols)
    
    if df.empty:
        stats = {
            'sum': 0,
            'mean': np.nan,
            'min': np.nan,
            'max': np.nan
        }
        fig, ax = plt.subplots()
        return stats, ax

    stats = {
        'sum': df[column].sum(),
        'mean': df[column].mean(),
        'min': df[column].min(),
        'max': df[column].max()
    }
    
    fig, ax = plt.subplots()
    ax.pie(df[column], labels=df['Age'])
    
    return stats, ax
