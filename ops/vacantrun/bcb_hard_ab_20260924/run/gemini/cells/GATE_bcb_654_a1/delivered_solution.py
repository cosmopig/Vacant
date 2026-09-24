import matplotlib.pyplot as plt
import scipy.optimize as optimize
import numpy as np

def task_func(array, target_value):
    # Convert target_value to string to ensure comparison works if array contains strings
    target_val_str = str(target_value)
    
    # Find indices where the first column matches target_value
    # array[:, 0] gets the first column
    mask = (array[:, 0] == target_val_str)
    indices = np.where(mask)[0]
    
    if len(indices) < 3:
        raise ValueError("Not enough points to fit an exponential decay function with 3 parameters.")
    
    # Extract y values from the second column (index 1)
    try:
        y = array[indices, 1].astype(float)
    except (ValueError, IndexError) as e:
        raise ValueError(f"Failed to extract y values: {e}")
    
    x = indices.astype(float)
    
    # Define the exponential decay function: y = a * exp(-b * x) + c
    def func(x, a, b, c):
        return a * np.exp(-b * x) + c
    
    # Initial guess for the parameters (a, b, c)
    # a: amplitude, b: decay rate, c: offset
    # Using heuristics based on the first and last points
    # For a decay function, y(0) = a + c, and y(inf) = c
    # So a = y(0) - c, and c is approximately the value at the last index
    a_guess = y[0] - y[-1]
    b_guess = 0.1
    c_guess = y[-1]
    p0 = [a_guess, b_guess, c_guess]
    
    try:
        popt, pcov = optimize.curve_fit(func, x, y, p0=p0, maxfev=5000)
    except Exception as e:
        raise ValueError(f"Optimization failed: {e}")
        
    # Prepare the plot
    fig, ax = plt.subplots()
    ax.scatter(x, y, color='blue', label='Data points')
    
    # Generate points for the fitted curve
    x_fit = np.linspace(np.min(x), np.max(x), 100)
    y_fit = func(x_fit, *popt)
    ax.plot(x_fit, y_fit, color='red', label='Fitted curve')
    ax.set_xlabel('Index')
    ax.set_ylabel('Value')
    ax.legend()
    
    return popt, ax
