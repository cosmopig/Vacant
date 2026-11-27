def _next_row(row):
    return [1] + [a + b for a, b in zip(row, row[1:])] + [1]


def rows(row_count):
    if row_count < 0:
        raise ValueError("number of rows is negative")
    result = []
    row = [1]
    for _ in range(row_count):
        result.append(row)
        row = _next_row(row)
    return result
