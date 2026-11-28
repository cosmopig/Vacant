DIGITS = {
    " _ | ||_|   ": "0",
    "     |  |   ": "1",
    " _  _||_    ": "2",
    " _  _| _|   ": "3",
    "   |_|  |   ": "4",
    " _ |_  _|   ": "5",
    " _ |_ |_|   ": "6",
    " _   |  |   ": "7",
    " _ |_||_|   ": "8",
    " _ |_| _|   ": "9",
}


def convert(input_grid):
    lines = input_grid.split("\n")
    if len(lines) % 4 != 0:
        raise ValueError("Number of input lines is not a multiple of four")
    if len(lines[0]) % 3 != 0:
        raise ValueError("Number of input columns is not a multiple of three")

    rows = []
    for r in range(0, len(lines), 4):
        group = lines[r:r + 4]
        width = len(group[0])
        digits = []
        for c in range(0, width, 3):
            key = "".join(line[c:c + 3] for line in group)
            digits.append(DIGITS.get(key, "?"))
        rows.append("".join(digits))
    return ",".join(rows)
