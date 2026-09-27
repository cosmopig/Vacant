import pandas as pd
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from matplotlib.collections import PathCollection

def task_func(data, n_clusters=3):
    if not isinstance(data, pd.DataFrame):
        raise ValueError("If 'data' is not a pd.DataFrame.")
    if not isinstance(n_clusters, int) or n_clusters <= 1:
        raise ValueError("If 'n_clusters' is not an integer greater than 1.")

    # Perform K-means clustering
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init='auto')
    labels = kmeans.fit_predict(data)
    centroids = kmeans.cluster_centers_

    # Create the plot
    fig, ax = plt.subplots()
    
    # Plot clusters
    scatter = ax.scatter(data.iloc[:, 0], data.iloc[:, 1], c=labels, cmap='viridis', s=50)
    
    # Plot centroids
    ax.scatter(centroids[:, 0], centroids[:, 1], c='red', marker='X', s=200, label='Centroids')
    
    ax.set_title(f'K-means Clustering (n={n_clusters})')
    ax.set_xlabel('Feature 1')
    ax.set_ylabel('Feature 2')
    ax.legend()

    return labels, ax
