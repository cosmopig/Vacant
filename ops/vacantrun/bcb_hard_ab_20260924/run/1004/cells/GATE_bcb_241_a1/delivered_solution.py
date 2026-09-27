import numpy as np
import matplotlib.pyplot as plt
from sklearn import preprocessing

def task_func(original):
    # Extract the numeric values from the list of tuples
    arr = np.array([item[1] for item in original], dtype=float)
    
    # Normalize the array
    # Based on test_case_2, normalization is arr / np.linalg.norm(arr)
    norm_arr = arr / np.linalg.norm(arr)
    
    # Plotting the original and normalized arrays
    fig, ax = plt.subplots()
    ax.plot(arr, label='Original')
    ax.plot(norm_arr, label='Normalized')
    ax.set_title('Original vs. Normalized Data')
    ax.legend()
    
    return arr, norm_arr, ax
