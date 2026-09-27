from typing import List

def maxRectangleArea(points: List[List[int]]) -> int:
    n = len(points)
    if n < 4:
        return -1
    
    max_area = -1
    
    # Iterate through all combinations of 4 points
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                for l in range(k + 1, n):
                    p = [points[i], points[j], points[k], points[l]]
                    
                    # Extract unique x and y coordinates
                    xs = sorted(list(set(pt[0] for pt in p)))
                    ys = sorted(list(set(pt[1] for pt in p)))
                    
                    # Must have exactly 2 unique x and 2 unique y coordinates
                    if len(xs) == 2 and len(ys) == 2:
                        x_min, x_max = xs[0], xs[1]
                        y_min, y_max = ys[0], ys[1]
                        
                        # Check if the 4 points are the corners of the rectangle
                        corners = {
                            (x_min, y_min),
                            (x_min, y_max),
                            (x_max, y_min),
                            (x_max, y_max)
                        }
                        
                        is_rectangle = True
                        for pt in p:
                            if tuple(pt) not in corners:
                                is_rectangle = False
                                break
                        
                        if is_rectangle:
                            # Check if any other point is inside or on the border
                            valid = True
                            for m in range(n):
                                pm = points[m]
                                # If it's one of the corners, skip it
                                if tuple(pm) in corners:
                                    continue
                                
                                # Check if it's inside or on the border
                                if x_min <= pm[0] <= x_max and y_min <= pm[1] <= y_max:
                                    valid = False
                                    break
                            
                            if valid:
                                area = (x_max - x_min) * (y_max - y_min)
                                if area > max_area:
                                    max_area = area
                                    
    return max_area
