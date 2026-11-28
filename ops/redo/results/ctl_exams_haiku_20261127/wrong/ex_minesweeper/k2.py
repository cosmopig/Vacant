def annotate(minefield):
    if not minefield:
        return []
    width = len(minefield[0])
    for row in minefield:
        if len(row) != width:
            raise ValueError("The board is invalid with current input.")
        for ch in row:
            if ch not in (" ", "*"):
                raise ValueError("The board is invalid with current input.")
    height = len(minefield)
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    result = []
    for r in range(height):
        out = []
        for c in range(width):
            if minefield[r][c] == "*":
                out.append("*")
                continue
            count = 0
            for dr, dc in directions:
                nr, nc = r + dr, c + dc
                if 0 <= nr < height and 0 <= nc < width and minefield[nr][nc] == "*":
                    count += 1
            out.append(str(count) if count else " ")
        result.append("".join(out))
    return result
