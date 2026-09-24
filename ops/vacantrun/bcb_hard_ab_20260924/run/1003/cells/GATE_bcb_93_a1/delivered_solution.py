import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA

def task_func(data, n_components=2):
    if not isinstance(n_components, int) or n_components <= 0:
        raise ValueError("n_components must be a positive integer.")
    
    # Ensure data is a DataFrame for consistency if it's not already
    if not isinstance(data, pd.DataFrame):
        df = pd.DataFrame(data)
    else:
        df = data.copy()

    # Perform PCA
    pca = PCA(n_components=n_components)
    transformed_data = pca.fit_transform(df)
    
    # Create a DataFrame for the transformed data
    transformed_df = pd.DataFrame(
        transformed_data, 
        columns=[f'PC{i+1}' for i in range(n_components)]
    )

    # Generate scatter plot
    fig, ax = plt.subplots()
    if n_components >= 2:
        ax.scatter(transformed_df['PC1'], transformed_df['PC2'])
    else:
        ax.scatter(transformed_df['PC1'], np.zeros(len(transformed_df)))

    ax.set_xlabel('Principal Component 1')
    ax.set_ylabel('Principal Component 2')
    ax.set_title('PCA Transformed Data')

    return transformed_df, ax
