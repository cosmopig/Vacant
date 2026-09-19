from typing import List

def maxRectangleArea(points: List[List[int]]) -> int:
    """
    Finds the maximum area of a rectangle formed by four points from the given list,
    where edges are parallel to the axes and no other point lies inside or on its border.
    Returns -1 if no such rectangle is possible.
    """
    n = len(points)
    max_area = -1
    point_set = set(tuple(p) for p in points)

    # Iterate through all pairs of points to find potential top-left and bottom-right corners
    for i in range(n):
        x1, y1 = points[i]
        for j in range(n):
            if i == j:
                continue
            x2, y2 = points[j]

            # We look for a rectangle where (x1, y1) is top-left and (x2, y2) is bottom-right
            # This means x1 < x2 and y1 > y2.
            # However, to simplify logic and cover all orientations, we can just ensure:
            if x1 != x2 and y1 != y2:
                # Let's define the bounding box by min/max of current pair
                min_x, max_x = min(x1, x2), max(x1, x2)
                min_y, max_y = min(y1, y2), max(y1, y2)

                # Check if the other two corners exist in our set
                p1 = (min_x, min_y)
                p2 = (min_x, max_y)
                p3 = (max_x, min_y)
                p4 = (max_x, max_y)

                # The four corners of the potential rectangle are p1, p2, p3, p4.
                # We need to ensure these 4 points are in our input set and distinct.
                corners = {p1, p2, p3, p4}
                if len(corners) == 4 and corners.issubset(point_set):
                    # Now check if any other point from the input is inside or on the border.
                    is_valid = True
                    for px, py in points:
                        p_tuple = (px, py)
                        if p_tuple not in corners:
                            # Check if it's inside or on the boundary of the rectangle
                            if min_x <= px <= max_x and min_y <= py <= max_y:
                                is_valid = False
                                break

                    if is_valid:
                        area = (max_x - min_x) * (max_y - min_y)
                        if area > max_area:
                            max_area = area

    return max_area
