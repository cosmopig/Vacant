import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA

def task_func(data, n_components=2):
    if not isinstance(n_components, int) or n_components <= 0:
        raise ValueError("n_components must be a positive integer.")

    # Ensure data is in a format suitable for PCA (e.g., DataFrame or numpy array)
    if isinstance(data, pd.DataFrame):
        df_values = data.values
    else:
        df_values = np.array(data)

    pca = PCA(n_components=n_components)
    transformed_data = pca.fit_transform(df_values)

    # Create a DataFrame for the transformed data
    if isinstance(data, pd.DataFrame):
        column_names = [f"PC{i+1}" for i in range(n_components)]
        transformed_df = pd.DataFrame(transformed_data, columns=column_names)
    else:
        transformed_df = pd.DataFrame(transformed_data)

    # Generate scatter plot
    fig, ax = plt.subplots()
    if n_components >= 2:
        ax.scatter(transformed_data[:, 0], transformed_data[:, 1])
    elif n_components == 1:
        ax.scatter(transformed_data[:, 0], np.zeros_like(transformed_data[:, 0]))

    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.set_title("PCA Transformed Data")

    return transformed_df, ax
