import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from sklearn.datasets import load_iris

def task_func():
    iris = load_iris()
    df = pd.DataFrame(data=iris.data, columns=iris.feature_names)
    df['species'] = [iris.target_names[i] for i in iris.target]
    
    plt.rcParams['font.family'] = 'Arial'
    
    g = sns.pairplot(df, hue='species')
    g.fig.suptitle('Iris Dataset Pair Plot')
    
    return g.fig
