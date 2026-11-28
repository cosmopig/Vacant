def rows(row_count):
    if row_count < -1:
        raise ValueError("number of rows is negative")
    if row_count <= 0:
        return []
    if row_count == 1:
        return [[1]]
    previous = rows(row_count - 1)
    padded = [0] + previous[-1] + [0]
    new_row = [padded[i] + padded[i + 1] for i in range(len(padded) - 1)]
    return previous + [new_row]
