from typing import List

def maxRectangleArea(points: List[List[int]]) -> int:
    """
    Finds the maximum area of a rectangle formed by four points from the given list,
    such that no other point lies inside or on its border. Edges must be parallel to axes.
    Returns -1 if no such rectangle exists.
    """
    n = len(points)
    max_area = -1

    # Sort points to make it easier to identify unique x and y coordinates
    # However, with n <= 10, we can just iterate through all combinations of 4 points.
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                for l in range(k + 1, n):
                    p = [points[i], points[j], points[k], points[l]]
                    # Check if these 4 points form a rectangle with sides parallel to axes
                    # A set of 4 points forms such a rectangle if:
                    # There are exactly 2 unique x-coordinates and 2 unique y-coordinates.
                    xs = sorted(list(set(pt[0] for pt in p)))
                    ys = sorted(list(set(pt[1] for pt in p)))

                    if len(xs) == 2 and len(ys) == 2:
                        # Check if the points are actually the corners of this rectangle
                        # The expected corners are (x1, y1), (x1, y2), (x2, y1), (x2, y2)
                        expected_corners = {
                            (xs[0], ys[0]),
                            (xs[0], ys[1]),
                            (xs[1], ys[0]),
                            (xs[1], ys[1])
                        }
                        actual_corners = set((pt[0], pt[1]) for pt in p)

                        if actual_corners == expected_corners:
                            area = (xs[1] - xs[0]) * (ys[1] - ys[0])

                            # Check if any other point is inside or on the border
                            is_valid = True
                            for m in range(n):
                                if m in [i, j, k, l]:
                                    continue
                                pm = points[m]
                                # Point is inside or on border if:
                                # xs[0] <= px <= xs[1] AND ys[0] <= py <= ys[1]
                                if xs[0] <= pm[0] <= xs[1] and ys[0] <= pm[1] <= ys[1]:
                                    is_valid = False
                                    break

                            if is_valid:
                                max_area = max(max_area, area)

    return max_area

