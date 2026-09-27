def sortMatrix(grid):
    n = len(grid)
    # A diagonal is defined by k = i - j, where i is row index and j is column index.
    # k ranges from -(n-1) to (n-1).
    
    # We can use a dictionary to store the elements of each diagonal.
    diagonals = {}
    for i in range(n):
        for j in range(n):
            k = i - j
            if k not in diagonals:
                diagonals[k] = []
            diagonals[k].append((i, j))
            
    # Sort each diagonal and put the values back.
    for k, coords in diagonals.items():
        values = [grid[i][j] for i, j in coords]
        if k >= 0:
            # Non-increasing order (descending)
            values.sort(reverse=True)
        else:
            # Non-decreasing order (ascending)
            values.sort()
            
        # Put the sorted values back into the grid
        for idx, (i, j) in enumerate(coords):
            grid[i][j] = values[idx]
            
    return grid
