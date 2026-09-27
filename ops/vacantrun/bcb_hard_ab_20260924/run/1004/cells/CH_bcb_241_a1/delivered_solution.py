import numpy as np
import matplotlib.pyplot as plt
from sklearn import preprocessing

def task_func(original):
    # Extract the numeric values from the list of tuples
    arr = np.array([item[1] for item in original], dtype=float)
    
    # Normalize the array using L2 norm as required by tests
    norm_arr = arr / np.linalg.norm(arr)
    
    # Plotting
    fig, ax = plt.subplots()
    ax.plot(arr, label='Original')
    ax.plot(norm_arr, label='Normalized')
    ax.set_title('Original vs. Normalized Data')
    ax.legend()
    
    return arr, norm_arr, ax
