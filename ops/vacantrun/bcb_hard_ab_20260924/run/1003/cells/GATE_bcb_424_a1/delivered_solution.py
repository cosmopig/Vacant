import cv2
import numpy as np
import os
from sklearn.cluster import KMeans

def task_func(image_path='image.jpg', n_clusters=3, random_seed=42):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found at {image_path}")
    
    if not isinstance(n_clusters, int) or n_clusters <= 0:
        raise ValueError("n_clusters must be a positive integer")

    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        raise FileNotFoundError(f"Image file not found at {image_path}")
    
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w, c = img_rgb.shape
    pixels = img_rgb.reshape(-1, c)

    if n_clusters == 1:
        segmented_img = img_rgb.copy()
        region_img = np.zeros_like(img_rgb)
        region_img[:] = img_rgb[:]
        cv2.imwrite('cluster_1.jpg', cv2.cvtColor(region_img, cv2.COLOR_RGB2BGR))
        return img_rgb, segmented_img

    kmeans = KMeans(n_clusters=n_clusters, random_state=random_seed, n_init='auto').fit(pixels)
    centroids = kmeans.cluster_centers_
    labels = kmeans.labels_

    segmented_img = centroids[labels].reshape(h, w, c).astype(np.uint8)

    for i in range(n_clusters):
        region_img = np.zeros_like(img_rgb)
        mask = (labels == i)
        region_img[mask] = img_rgb[mask]
        cv2.imwrite(f'cluster_{i+1}.jpg', cv2.cvtColor(region_img, cv2.COLOR_RGB2BGR))

    return img_rgb, segmented_img
