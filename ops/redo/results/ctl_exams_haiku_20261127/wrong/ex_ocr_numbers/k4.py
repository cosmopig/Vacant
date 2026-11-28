DIGITS = {
    " _ | ||_|": "0",
    "     |  |": "1",
    " _  _||_ ": "2",
    " _  _| _|": "3",
    "   |_|  |": "4",
    " _ |_  _|": "5",
    " _ |_ |_|": "6",
    " _   |  |": "7",
    " _ |_||_|": "8",
    " _ |_| _|": "9",
}


def convert(input_grid):
    lines = input_grid.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]

    if len(lines) % 4 != 0:
        raise ValueError("Number of input lines is not a multiple of four")

    for line in lines:
        if len(line) % 3 != 0:
            raise ValueError("Number of input columns is not a multiple of three")

    results = []
    for r in range(0, len(lines), 4):
        group = lines[r:r + 4]
        width = len(group[0])
        row_digits = []
        for c in range(0, width, 3):
            cell = "".join(line[c:c + 3] for line in group[:3])
            if cell.strip() == "":
                continue
            row_digits.append(DIGITS.get(cell, "?"))
        results.append("".join(row_digits))

    return ",".join(results)
