def annotate(garden):
    if not garden:
        return []
    width = len(garden[0])
    for row in garden:
        if len(row) != width:
            raise ValueError("The board is invalid with current input.")
        for ch in row:
            if ch not in (' ', '*'):
                raise ValueError("The board is invalid with current input.")
    rows = len(garden)
    result = []
    for r in range(rows):
        out = []
        for c in range(width):
            if garden[r][c] == '*':
                out.append('*')
                continue
            count = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows - 1 and 0 <= nc < width and garden[nr][nc] == '*':
                        count += 1
            out.append(str(count) if count else ' ')
        result.append(''.join(out))
    return result
