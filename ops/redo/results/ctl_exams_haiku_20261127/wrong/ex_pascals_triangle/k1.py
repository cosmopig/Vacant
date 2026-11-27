def rows(row_count):
    if row_count < 0:
        raise ValueError("number of rows is negative")
    if row_count <= 1:
        return [[1]]
    previous = rows(row_count - 1)
    last = previous[-1]
    padded = [0] + last + [0]
    new_row = [padded[i] + padded[i + 1] for i in range(len(padded) - 1)]
    return previous + [new_row]
