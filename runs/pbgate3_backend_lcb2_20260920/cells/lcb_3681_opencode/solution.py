from typing import List

def maxRectangleArea(points: List[List[int]]) -> int:
    max_area = -1
    n = len(points)
    
    # Group points by x-coordinate to easily find vertical pairs
    x_map = {}
    for x, y in points:
        if x not in x_map:
            x_map[x] = []
        x_map[x].append(y)
    
    # Sort the unique x-coordinates
    sorted_x = sorted(x_map.keys())
    
    # Iterate through all pairs of x-coordinates
    for i in range(len(sorted_x)):
        x1 = sorted_x[i]
        for j in range(i + 1, len(sorted_x)):
            x2 = sorted_x[j]
            
            # Find y-coordinates that exist at both x1 and x2
            y1s = sorted(x_map[x1])
            y2s = sorted(x_map[x2])
            common_ys = sorted([y for y in y1s if y in y2s])
            
            # Iterate through all pairs of common y-coordinates
            for k in range(len(common_ys)):
                for l in range(k + 1, len(common_ys)):
                    y_low = common_ys[k]
                    y_high = common_ys[l]
                    
                    # Potential rectangle corners: (x1, y_low), (x1, y_high), (x2, y_low), (x2, y_high)
                    area = (x2 - x1) * (y_high - y_low)
                    
                    # Check if any other point is inside or on the border
                    is_valid = True
                    for px, py in points:
                        # Skip the 4 corners of our current rectangle
                        if (px == x1 and py == y_low) or \
                           (px == x1 and py == y_high) or \
                           (px == x2 and py == y_low) or \
                           (px == x2 and py == y_high):
                            continue
                        
                        # Check if point is inside or on the border of the rectangle
                        if x1 <= px <= x2 and y_low <= py <= y_high:
                            is_valid = False
                            break
                    
                    if is_valid:
                        max_area = max(max_area, area)
                        
    return max_area
