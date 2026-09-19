from typing import List

def maxRectangleArea(points: List[List[int]]) -> int:
    n = len(points)
    max_area = -1
    
    # Group points by x-coordinate to easily find pairs with same x
    x_map = {}
    for x, y in points:
        if x not in x_map:
            x_map[x] = []
        x_map[x].append(y)
    
    # Sort the unique x-coordinates
    sorted_x = sorted(x_map.keys())
    
    # Iterate through all pairs of points to find potential rectangles
    # A rectangle is defined by two points (x1, y1) and (x2, y2) 
    # where x1 != x2 and y1 != y2 as diagonal corners.
    for i in range(n):
        x1, y1 = points[i]
        for j in range(i + 1, n):
            x2, y2 = points[j]
            
            # Check if they can be opposite corners of an axis-aligned rectangle
            if x1 != x2 and y1 != y2:
                # The other two corners must be (x1, y2) and (x2, y1)
                p3 = [x1, y2]
                p4 = [x2, y1]
                
                # Check if these points exist in the input set
                if p3 in points and p4 in points:
                    # We found a rectangle. Now check if any other point is inside or on its border.
                    area = abs(x1 - x2) * abs(y1 - y2)
                    is_valid = True
                    
                    min_x, max_x = min(x1, x2), max(x1, x2)
                    min_y, max_y = min(y1, y2), max(y1, y2)
                    
                    for k in range(n):
                        px, py = points[k]
                        # If the point is one of the 4 corners, skip it
                        if (px == x1 and py == y1) or \
                           (px == x2 and py == y2) or \
                           (px == x1 and py == y2) or \
                           (px == x2 and py == y1):
                            continue
                        
                        # Check if point is inside or on the border
                        if min_x <= px <= max_x and min_y <= py <= max_y:
                            is_valid = False
                            break
                    
                    if is_valid:
                        max_area = max(max_area, area)
                        
    return max_area
