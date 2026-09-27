import numpy as np
from scipy.spatial import Voronoi, voronoi_plot_2d
import matplotlib.pyplot as plt

def task_func(points, seed=0):
    """
    Calculate the Voronoi diagram for a number of points in 2D and plot it.
    Jittering is applied prior to plotting.
    
    Args:
        points (np.ndarray): An array of shape (N, 2) representing the points.
        seed (int): Random seed for jittering.

    Returns:
        tuple: A tuple containing (vor, ax), where vor is a Voronoi object 
               and ax is the axes of the plotted Voronoi diagram.
    """
    # Validate input
    if not isinstance(points, np.ndarray):
        points = np.array(points)
    
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("Input points must be a 2D array of shape (N, 2).")

    # Create a copy to avoid modifying the original input
    pts = points.astype(float).copy()

    # Apply jittering for plotting purposes
    # We use a small amount of noise so it doesn't significantly change the Voronoi structure
    # but helps in visualization if points are perfectly aligned or coincident.
    rng = np.random.default_rng(seed)
    jitter = rng.standard_normal(pts.shape) * 0.01
    pts_jittered = pts + jitter

    # Calculate Voronoi diagram using the original points (as per standard behavior, 
    # but usually jittering is applied to avoid issues with degenerate cases).
    # The goal says "Jittering is applied prior to plotting". 
    # Let's use the jittered points for both calculation and plotting to ensure stability.
    vor = Voronoi(pts_jittered)

    # Plotting
    fig, ax = plt.subplots()
    voronoi_plot_2d(vor, ax=ax)
    
    # Optional: plot the original points for reference (not strictly required but good practice)
    # ax.scatter(pts[:, 0], pts[:, 1], color='red', s=10)

    return vor, ax
