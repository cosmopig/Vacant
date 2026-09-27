import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA

def task_func(data, n_components=2):
    if not isinstance(n_components, int) or n_components <= 0:
        raise ValueError("n_components must be a positive integer.")
    
    pca = PCA(n_components=n_components)
    transformed_data = pca.fit_transform(data)
    
    df = pd.DataFrame(transformed_data, columns=[f'PC{i+1}' for i in range(n_components)])
    
    fig, ax = plt.subplots()
    if n_components >= 2:
        ax.scatter(df.iloc[:, 0], df.iloc[:, 1])
        ax.set_xlabel('PC1')
        ax.set_ylabel('PC2')
    else:
        ax.scatter(df.iloc[:, 0], np.zeros(len(df)))
        ax.set_xlabel('PC1')
        ax.set_ylabel('Zeros (n_components < 2)')

    return df, ax
