import matplotlib.pyplot as plt
import scipy.optimize as optimize
import numpy as np

def task_func(array, target_value):
    array = np.array(array)
    mask = (array[:, 0] == target_value)
    indices = np.where(mask)[0]
    
    if len(indices) < 3:
        raise ValueError("Not enough points for fitting.")
        
    x_data = indices.astype(float)
    y_data = array[indices, 1].astype(float)
    
    def func(x, a, b, c):
        return a * np.exp(-b * x) + c
        
    # Initial guess
    p0 = [1.0, 0.1, 1.0]
    if len(x_data) >= 3:
        y0, y1, y2 = y_data[0], y_data[1], y_data[2]
        x0, x1, x2 = x_data[0], x_data[1], x_data[2]
        dx = x1 - x0
        if abs((x2 - x1) - dx) < 1e-6 and dx > 0:
            if abs(y0 - y1) > 1e-9:
                E = (y1 - y2) / (y0 - y1)
                if E > 0 and abs(E - 1) > 1e-9:
                    b_guess = -np.log(E) / dx
                    A_guess = (y0 - y1) / (1 - E)
                    a_guess = A_guess * np.exp(b_guess * x0)
                    c_guess = y0 - A_guess
                    p0 = [a_guess, b_guess, c_guess]

    popt, _ = optimize.curve_fit(func, x_data, y_data, p0=p0, maxfev=10000)
    
    fig, ax = plt.subplots()
    ax.scatter(x_data, y_data, label='Data')
    x_fit = np.linspace(min(x_data), max(x_data), 100)
    y_fit = func(x_fit, *popt)
    ax.plot(x_fit, y_fit, label='Fit', color='red')
    ax.set_xlabel('Index')
    ax.set_ylabel('Value')
    ax.legend()
    
    return popt, ax
