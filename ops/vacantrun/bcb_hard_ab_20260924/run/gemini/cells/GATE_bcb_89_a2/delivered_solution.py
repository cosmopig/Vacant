import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
from sklearn.preprocessing import StandardScaler

def task_func(data, column, outlier_z_score):
    """
    Identifies and removes outliers from a specified column of a dataset based on the Z-score.
    It standardizes the column, calculates Z-scores, and removes data points where the Z-score 
    exceeds a threshold. The function also visualizes the data before and after outlier removal.

    Args:
        data (numpy.ndarray): The input dataset.
        column (int): The index of the column to identify outliers from.
        outlier_z_score (float): The Z-score threshold for outlier removal.

    Returns:
        tuple: A tuple containing (original_data, data_without_outliers, outlier_indices).
    """
    # Extract the specified column
    col_values = data[:, column]
    
    # Standardize the column using StandardScaler
    # StandardScaler expects a 2D array
    scaler = StandardScaler()
    standardized_values = scaler.fit_transform(col_values.reshape(-1, 1)).flatten()
    
    # Identify outlier indices where the absolute Z-score exceeds the threshold
    outlier_indices = np.where(np.abs(standardized_values) > outlier_z_score)[0]
    
    # Create the data without outliers
    data_without_outliers = np.delete(data, outlier_indices, axis=0)
    
    # Visualization
    plt.figure(figsize=(12, 5))
    
    # First scatter plot: Data with Outliers
    plt.subplot(1, 2, 1)
    plt.scatter(np.arange(len(data)), col_values)
    plt.title('Data with Outliers')
    plt.xlabel('Index')
    plt.ylabel('Value')
    
    # Second scatter plot: Data without Outliers
    plt.subplot(1, 2, 2)
    plt.scatter(np.arange(len(data_without_outliers)), data_without_outliers[:, column])
    plt.title('Data without Outliers')
    plt.xlabel('Index')
    plt.ylabel('Value')
    
    plt.tight_layout()
    plt.show()
    
    return data, data_without_outliers, outlier_indices
