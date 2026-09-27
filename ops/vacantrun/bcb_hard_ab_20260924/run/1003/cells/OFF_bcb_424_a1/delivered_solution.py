import cv2
import numpy as np
import os
from sklearn.cluster import KMeans

def task_func(image_path='image.jpg', n_clusters=3, random_seed=42):
    if not isinstance(n_clusters, int) or n_clusters <= 0:
        raise ValueError("n_clusters must be a positive integer")
    
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found at {image_path}")

    img = cv2.imread(image_path)
    if img is None:
        # If the file exists but is not a valid image, cv2.imread returns None.
        # The goal only specifies FileNotFoundError for non-existent files.
        raise FileNotFoundError(f"Could not read image at {image_path}")

    if n_clusters == 1:
        cv2.imwrite('region_0.jpg', img)
        return (img, img)

    h, w, c = img.shape
    data = img.reshape(-1, c)
    
    kmeans = KMeans(n_clusters=n_clusters, random_state=random_seed, n_init=10)
    labels = kmeans.fit_predict(data)
    centroids = kmeans.cluster_centers_

    segmented_img = np.zeros((h, w, c), dtype=np.uint8)
    for i in range(n_clusters):
        region_img = np.zeros((h, w, c), dtype=np.uint8)
        region_img[labels == i] = centroids[i].astype(np.uint8)
        cv2.imwrite(f'region_{i}.jpg', region_img)
        segmented_img[labels == i] = centroids[i].astype(np.uint8)

    return (img, segmented_img)
