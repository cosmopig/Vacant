def rows(row_count):
    if row_count < 0:
        raise ValueError("number of rows is negative")
    if row_count == 0:
        return []
    return _build_rows(row_count)


def _build_rows(n):
    if n == 1:
        return [[1]]
    triangle = _build_rows(n - 1)
    last = triangle[-1]
    padded = [0, *last, 0]
    new_row = [padded[i] + padded[i + 1] for i in range(len(padded) - 1)]
    triangle.append(tuple(new_row))
    return triangle
