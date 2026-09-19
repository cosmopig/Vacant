from typing import List

def maxRectangleArea(points: List[List[int]]) -> int:
    max_area = -1
    n = len(points)
    
    # Group points by x-coordinate to easily find vertical segments
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
            
            # Find common y-coordinates for these two x-coordinates
            y1s = sorted(x_map[x1])
            y2s = sorted(x_map[x2])
            common_ys = [y for y in y1s if y in y2s]
            
            # If we have at least two common y-coordinates, they can form a rectangle
            if len(common_ys) >= 2:
                for k in range(len(common_ys)):
                    for l in range(k + 1, len(common_ys)):
                        y_low = common_ys[k]
                        y_high = common_ys[l]
                        
                        # Check if any other point is inside or on the border of this rectangle
                        is_valid = True
                        for px, py in points:
                            if (x1 < px < x2) and (y_low <= py <= y_high):
                                is_valid = False
                                break
                            if (px == x1 or px == x2) and (y_low < py < y_high):
                                is_valid = False
                                break
                        
                        # The condition "Does not contain any other point inside or on its border" 
                        # means we must check all points.
                        # Actually, the logic above covers:
                        # - Points strictly inside (x1 < px < x2 and y_low < py < y_high)
                        # - Points on horizontal edges (px == x1 or px == x2 is handled by checking if it's between y_low and y_high, but we need to be careful about the corners)
                        # Wait, the condition says "Does not contain any other point inside OR ON ITS BORDER".
                        # The 4 corners are part of the border. They should NOT count as "other" points.
                        
                        # Let's re-evaluate:
                        is_valid = True
                        for px, py in points:
                            # If it's one of the 4 corners, skip it
                            if (px == x1 and py == y_low) or \
                               (px == x1 and py == y_high) or \
                               (px == x2 and py == y_low) or \
                               (px == x2 and py == y_high):
                                continue
                            
                            # If it's on the border or inside, it's invalid
                            if x1 <= px <= x2 and y_low <= py <= y_high:
                                is_valid = False
                                break
                        
                        if is_valid:
                            area = (x2 - x1) * (y_high - y_low)
                            max_area = max(max_area, area)
                            
    return max_area
