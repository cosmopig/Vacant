def annotate(minefield):
    width = len(minefield[0])
    for row in minefield:
        if len(row) != width or any(ch not in " *" for ch in row):
            raise ValueError("The board is invalid with current input.")

    rows = len(minefield)
    result = []
    for r in range(rows):
        line = []
        for c in range(width):
            if minefield[r][c] == "*":
                line.append("*")
                continue
            count = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < width and minefield[nr][nc] == "*":
                        count += 1
            line.append(str(count) if count else " ")
        result.append("".join(line))
    return result
