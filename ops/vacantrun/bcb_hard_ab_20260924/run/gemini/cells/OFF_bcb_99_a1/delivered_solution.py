import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from sklearn.datasets import load_iris

def task_func():
    # Set global font to Arial
    plt.rcParams['font.family'] = 'Arial'
    
    # Load iris dataset
    iris = load_iris()
    df = pd.DataFrame(data=iris.data, columns=iris.feature_names)
    df['species'] = [iris.target_names[i] for i in iris.target]

    # Create pair plot
    pair_plot = sns.pairplot(df, hue='species')
    
    # Add title
    pair_plot.fig.suptitle('Iris Dataset Pair Plot', y=1.02)

    return pair_plot.fig
