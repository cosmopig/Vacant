import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from sklearn.datasets import load_iris

def task_func():
    # Load the iris dataset
    iris = load_iris()
    # Create a DataFrame
    df = pd.DataFrame(data=iris.data, columns=iris.feature_names)
    # Add the species column
    df['species'] = [iris.target_names[i] for i in iris.target]

    # Set the global font to Arial
    plt.rcParams['font.family'] = 'Arial'

    # Generate the pair plot
    g = sns.pairplot(df, hue='species')
    
    # Add the title to the figure
    g.fig.suptitle('Iris Dataset Pair Plot', y=1.02)

    # Return the matplotlib Figure object
    return g.fig
