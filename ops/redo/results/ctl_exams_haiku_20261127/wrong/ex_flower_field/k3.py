def annotate(garden):
    if not garden:
        return []
    width = len(garden[0])
    for row in garden:
        if len(row) != width:
            raise ValueError("The board has inconsistent row lengths.")
        for ch in row:
            if ch not in (" ", "*"):
                raise ValueError("The board contains invalid characters.")
    height = len(garden)
    result = []
    for r in range(height):
        out = []
        for c in range(width):
            if garden[r][c] == "*":
                out.append("*")
                continue
            count = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < height and 0 <= nc < width and garden[nr][nc] == "*":
                        count += 1
            out.append(str(count) if count else " ")
        result.append(out)
    return result
