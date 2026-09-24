from typing import List
import itertools

def maxRectangleArea(points: List[List[int]]) -> int:
    max_area = -1
    
    # Iterate through all combinations of 4 points
    for combo in itertools.combinations(points, 4):
        # Extract unique x and y coordinates from the 4 points
        xs = set()
        ys = set()
        for p in combo:
            xs.add(p[0])
            ys.add(p[1])
        
        # A rectangle must have exactly 2 distinct x-coordinates and 2 distinct y-coordinates
        if len(xs) == 2 and len(ys) == 2:
            x_coords = sorted(list(xs))
            y_coords = sorted(list(ys))
            x1, x2 = x_coords[0], x_coords[1]
            y1, y2 = y_coords[0], y_coords[1]
            
            # Check if the 4 points in combo are exactly the 4 corners of the rectangle
            expected_corners = {(x1, y1), (x1, y2), (x2, y1), (x2, y2)}
            actual_corners = set()
            for p in combo:
                actual_corners.add((p[0], p[1]))
            
            if actual_corners == expected_corners:
                # It's a valid axis-aligned rectangle. Now check if any other point is inside or on the border.
                is_valid = True
                for p in points:
                    if p not in combo:
                        px, py = p[0], p[1]
                        if x1 <= px <= x2 and y1 <= py <= y2:
                            is_valid = False
                            break
                
                if is_valid:
                    area = (x2 - x1) * (y2 - y1)
                    if area > max_area:
                        max_area = area
                        
    return max_area
