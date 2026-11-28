def annotate(garden):
    if not garden:
        return []

    width = len(garden[0])
    for row in garden:
        if len(row) != width:
            raise ValueError("The board has uneven row lengths.")
        for ch in row:
            if ch not in (" ", "*"):
                raise ValueError("The board contains invalid characters.")

    height = len(garden)
    deltas = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, 0)]
    result = []

    for r in range(height):
        out_row = []
        for c in range(width):
            if garden[r][c] == "*":
                out_row.append("*")
                continue

            count = 0
            for dr, dc in deltas:
                nr, nc = r + dr, c + dc
                if 0 <= nr < height and 0 <= nc < width and garden[nr][nc] == "*":
                    count += 1

            out_row.append(str(count) if count else " ")
        result.append("".join(out_row))

    return result
