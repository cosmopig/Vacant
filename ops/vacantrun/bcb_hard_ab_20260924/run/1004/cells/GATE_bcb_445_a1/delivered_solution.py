import numpy as np
from scipy.spatial import Voronoi, voronoi_plot_2d
import matplotlib.pyplot as plt

def task_func(points, seed=0):
    """
    Calculate the Voronoi diagram for a number of points in 2D and plot it.
    Jittering is applied prior to plotting.
    
    Args:
        points (np.ndarray): An array of shape (N, 2) representing the points.
        seed (int): Seed for jittering.

    Returns:
        tuple: A tuple containing (vor, ax).
    """
    # Validate input
    if not isinstance(points, np.ndarray):
        raise TypeError("Input 'points' must be a numpy array.")
    
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("Input 'points' must have shape (N, 2).")

    # Create a copy to avoid modifying the original input
    pts = points.astype(np.float64).copy()

    # Apply jittering for plotting purposes only if needed or as part of requirements
    # The goal says "Jittering is applied prior to plotting". 
    # Usually, this means we should use a slightly perturbed version for the plot 
    # but maybe keep the original for the Voronoi calculation? 
    # However, usually it implies jittering the points used for both.
    # Let's apply a small amount of noise based on the seed.
    rng = np.random.default_rng(seed)
    jittered_pts = pts + rng.normal(0, 0.01, size=pts.shape)

    # Calculate Voronoi diagram using original points (or jittered? 
    # Usually "Calculate the Voronoi diagram... and plot it" with "Jittering is applied prior to plotting"
    # suggests we calculate on original but plot jittered, OR just use jittered for both.
    # Given standard behavior in these tasks, let's use jittered points for both 
    # to ensure the plot matches the Voronoi object returned.
    vor = Voronoi(jittered_pts)

    # Plotting
    fig, ax = plt.subplots()
    voronoi_plot_2d(vor, ax=ax)
    ax.set_title("Voronoi Diagram")
    plt.tight_layout()

    return vor, ax
