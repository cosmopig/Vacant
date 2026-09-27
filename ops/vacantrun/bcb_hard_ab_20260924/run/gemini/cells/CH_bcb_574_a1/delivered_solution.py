from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
import numpy as np

def task_func(array_length=100, noise_level=0.2):
    x = np.linspace(0, 2 * np.pi, array_length)
    y_pure = np.sin(x)
    noise = noise_level * np.random.randn(array_length)
    y_noisy = y_pure + noise

    def sine_func(x, a, b, c):
        return a * np.sin(b * x + c)

    # Initial guess for curve_fit
    popt, _ = curve_fit(sine_func, x, y_noisy, p0=[1, 1, 0])

    fig, ax = plt.subplots()
    ax.plot(x, y_noisy, label='Noisy Sine Wave')
    ax.plot(x, sine_func(x, *popt), label='Fitted Curve')
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.legend()

    return ax
