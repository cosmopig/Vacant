import pandas as pd
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from matplotlib.collections import PathCollection

def task_func(data, n_clusters=3):
    if not isinstance(data, pd.DataFrame):
        raise ValueError("If 'data' is not a pd.DataFrame.")
    if not isinstance(n_clusters, int) or n_clusters <= 1:
        raise ValueError("If 'n_clusters' is not an integer greater than 1.")

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init='auto').fit(data)
    labels = kmeans.labels_
    centroids = kmeans.cluster_centers_

    fig, ax = plt.subplots()
    # Use the first two columns for the scatter plot if they exist
    x = data.iloc[:, 0]
    y = data.iloc[:, 1]
    ax.scatter(x, y, c=labels, s=50, cmap='viridis', alpha=0.7)
    ax.scatter(centroids[:, 0], centroids[:, 1], c=range(n_clusters), s=200, marker='X', cmap='viridis', edgecolors='black', label='Centroids')

    return labels, ax
