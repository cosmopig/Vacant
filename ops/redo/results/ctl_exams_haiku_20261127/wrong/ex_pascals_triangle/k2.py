def rows(row_count):
    if row_count < 0:
        raise ValueError("number of rows is negative")
    if row_count == 0:
        return []
    return _build(row_count)


def _build(row_number):
    if row_number == 1:
        return [[1]]

    previous_rows = _build(row_number - 1)
    previous = previous_rows[-1]

    new_row = []
    for position in range(len(previous) + 1):
        left = previous[position - 1]
        right = previous[position] if position < len(previous) else 0
        new_row.append(left + right)

    return previous_rows + [new_row]
