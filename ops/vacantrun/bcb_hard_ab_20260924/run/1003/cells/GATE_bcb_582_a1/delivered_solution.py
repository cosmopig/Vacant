import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

def task_func(size=1000):
    # Generate normally distributed random numbers
    mu, sigma = 0, 1
    data = np.random.normal(mu, sigma, size)

    # Create figure and axis
    fig, ax = plt.subplots()

    # Plot histogram
    # density=True makes the histogram area sum to 1, which is comparable with PDF
    ax.hist(data, bins=28, density=True, alpha=0.6, color='g', label='Histogram')

    # Calculate PDF
    x = np.linspace(min(data), max(data), 100)
    pdf = stats.norm.pdf(x, mu, sigma)

    # Plot PDF
    ax.plot(x, pdf, 'r-', lw=2, label='PDF')

    ax.set_title('Histogram and PDF of Normally Distributed Random Numbers')
    ax.set_xlabel('Value')
    ax.set_ylabel('Density')
    ax.legend()

    return fig
