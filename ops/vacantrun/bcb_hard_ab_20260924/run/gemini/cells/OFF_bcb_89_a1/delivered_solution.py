import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
from sklearn.preprocessing import StandardScaler

def task_func(data, column, outlier_z_score):
    """
    Identifies and removes outliers from a specified column of a dataset based on the Z-score.
    It standardizes the column, calculates Z-scores, and removes data points where the Z-score exceeds a threshold.
    The function also visualizes the data before and after outlier removal.

    Args:
        data (numpy.ndarray): The input dataset.
        column (int): The index of the column to check for outliers.
        outlier_z_score (float): The Z-score threshold for outlier detection.

    Returns:
        tuple: (original_data, data_without_outliers, outlier_indices)
    """
    # 1. Standardize the column and calculate Z-scores
    # Reshape the column to 2D as required by StandardScaler
    col_data = data[:, column].reshape(-1, 1)
    scaler = StandardScaler()
    z_scores = scaler.fit_transform(col_data).flatten()

    # 2. Identify outlier indices
    outlier_indices = np.where(np.abs(z_scores) > outlier_z_score)[0]

    # 3. Remove outliers
    data_without_outliers = np.delete(data, outlier_indices, axis=0)

    # 4. Visualization
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Plot 1: Data with Outliers
    if data.ndim == 1:
        ax1.scatter(np.arange(len(data)), data)
    elif data.shape[1] >= 2:
        ax1.scatter(data[:, 0], data[:, 1])
    else:  # data.shape[1] == 1
        ax1.scatter(np.arange(len(data)), data[:, 0])
    ax1.set_title('Data with Outliers')

    # Plot 2: Data without Outliers
    if data_without_outliers.ndim == 1:
        ax2.scatter(np.arange(len(data_without_outliers)), data_without_outliers)
    elif data_without_outliers.shape[1] >= 2:
        ax2.scatter(data_without_outliers[:, 0], data_without_outliers[:, 1])
    else:  # data_without_outliers.shape[1] == 1
        ax2.scatter(np.arange(len(data_without_outliers)), data_without_outliers[:, 0])
    ax2.set_title('Data without Outliers')

    plt.tight_layout()
    plt.show()

    return data, data_without_outliers, outlier_indices
