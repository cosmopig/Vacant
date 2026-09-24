import cv2
import numpy as np
import os
from sklearn.cluster import KMeans

def task_func(image_path='image.jpg', n_clusters=3, random_seed=42):
    if not isinstance(n_clusters, int) or n_clusters <= 0:
        raise ValueError("n_clusters must be a positive integer.")
    
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found at {image_path}")

    # Read the image
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not read image file at {image_path}")

    # cv2.imread reads as BGR by default. 
    # The goal says "assumes the input image is in RGB format".
    # This usually means we should treat it as RGB if it's already in that order, 
    # but since cv2.imread swaps them, we might need to convert or just use what it gives us.
    # Let's assume "input image is in RGB format" refers to the content of the file.
    # If I use cv2.imread, I get BGR. To get RGB from a file that is "in RGB", 
    # I should convert BGR to RGB.
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Prepare data for K-means clustering
    h, w, c = img_rgb.shape
    pixels = img_rgb.reshape((-1, 3))

    # Apply K-means clustering
    kmeans = KMeans(n_clusters=n_clusters, random_state=random_seed, n_init='auto').fit(pixels)
    
    # Get the labels and centroids
    labels = kmeans.labels_
    centroids = kmeans.cluster_centers_

    # Create segmented image
    segmented_img = centroids[labels].reshape((h, w, 3)).astype(np.uint8)

    return img_rgb, segmented_img
