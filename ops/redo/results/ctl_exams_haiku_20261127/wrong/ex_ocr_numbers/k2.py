DIGIT_PATTERNS = {
    (" _ ", "| |", "|_|", "   "): "0",
    ("   ", "  |", "  |", "   "): "1",
    (" _ ", " _|", "|_ ", "   "): "2",
    (" _ ", " _|", " _|", "   "): "3",
    ("   ", "|_|", "  |", "   "): "4",
    (" _ ", "|_ ", " _|", "   "): "5",
    (" _ ", "|_ ", "|_|", "   "): "6",
    (" _ ", "  |", "  |", "   "): "7",
    (" _ ", "|_|", "|_|", "   "): "8",
    (" _ ", "|_|", " _|", "   "): "9",
}


def convert(input_grid):
    if input_grid.endswith("\n"):
        input_grid = input_grid[:-1]

    lines = [line.rstrip() for line in input_grid.split("\n")]

    if len(lines) % 4 != 0:
        raise ValueError("Number of input lines is not a multiple of four")

    for line in lines:
        if len(line) % 3 != 0:
            raise ValueError("Number of input columns is not a multiple of three")

    rows = []
    for top in range(0, len(lines), 4):
        group = lines[top:top + 4]
        width = len(group[0])
        digits = []
        for col in range(0, width, 3):
            key = tuple(line[col:col + 3].ljust(3) for line in group)
            digits.append(DIGIT_PATTERNS.get(key, "?"))
        rows.append("".join(digits))

    return ",".join(rows)
