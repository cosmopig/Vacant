from typing import List

def maxRectangleArea(points: List[List[int]]) -> int:
    n = len(points)
    max_area = -1
    
    # Group points by x-coordinate to easily find vertical segments
    x_coords = sorted(list(set(p[0] for p in points)))
    points_by_x = {}
    for p in points:
        if p[0] not in points_by_x:
            points_by_x[p[0]] = []
        points_by_x[p[0]].append(p[1])
    
    # Sort y-coordinates for each x to make it easier to find segments
    for x in points_by_x:
        points_by_x[x].sort()

    # Iterate through all pairs of x-coordinates
    for i in range(len(x_coords)):
        x1 = x_coords[i]
        for j in range(i + 1, len(x_coords)):
            x2 = x_coords[j]
            width = x2 - x1
            
            # Find common y-coordinates for these two x-coordinates
            y1s = points_by_x[x1]
            y2s = points_by_x[x2]
            common_ys = sorted(list(set(y1s) & set(y2s)))
            
            # For every pair of common y-coordinates, we have a potential rectangle
            for k in range(len(common_ys)):
                for l in range(k + 1, len(common_ys)):
                    y_low = common_ys[k]
                    y_high = common_ys[l]
                    height = y_high - y_low
                    area = width * height
                    
                    # Check if any other point is inside or on the border of this rectangle
                    is_valid = True
                    for p in points:
                        px, py = p
                        # If point is strictly inside or on the boundary
                        if x1 <= px <= x2 and y_low <= py <= y_high:
                            # Check if it's one of the 4 corners
                            is_corner = (
                                (px == x1 and py == y_low) or
                                (px == x1 and py == y_high) or
                                (px == x2 and py == y_low) or
                                (px == x2 and py == y_high)
                            )
                            if not is_corner:
                                is_valid = False
                                break
                    
                    if is_valid:
                        if area > max_area:
                            max_area = area
                            
    return max_area
