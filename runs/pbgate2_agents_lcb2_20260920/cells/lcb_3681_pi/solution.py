from typing import List

def maxRectangleArea(points: List[List[int]]) -> int:
    max_area = -1
    n = len(points)
    
    # Iterate through all combinations of 4 points
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                for l in range(k + 1, n):
                    p_indices = [i, j, k, l]
                    pts = [points[idx] for idx in p_indices]
                    
                    # Check if these 4 points form an axis-aligned rectangle
                    xs = sorted(list(set(p[0] for p in pts)))
                    ys = sorted(list(set(p[1] for p in pts)))
                    
                    if len(xs) == 2 and len(ys) == 2:
                        # Check if the 4 points are exactly (x1, y1), (x1, y2), (x2, y1), (x2, y2)
                        expected_pts = {
                            (xs[0], ys[0]),
                            (xs[0], ys[1]),
                            (xs[1], ys[0]),
                            (xs[1], ys[1])
                        }
                        actual_pts = set()
                        for p in pts:
                            actual_pts.add((p[0], p[1]))
                        
                        if actual_pts == expected_pts:
                            # It's a rectangle. Now check if any other point is inside or on the border.
                            x_min, x_max = xs[0], xs[1]
                            y_min, y_max = ys[0], ys[1]
                            
                            is_valid = True
                            for m in range(n):
                                if m not in p_indices:
                                    pm = points[m]
                                    if x_min <= pm[0] <= x_max and y_min <= pm[1] <= y_max:
                                        is_valid = False
                                        break
                            
                            if is_valid:
                                area = (x_max - x_min) * (y_max - y_min)
                                if area > max_area:
                                    max_area = area
                                    
    return max_area
