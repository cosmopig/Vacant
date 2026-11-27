DIGITS = {
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
    lines = input_grid.split("\n")
    if len(lines) % 4 != 0:
        raise ValueError("Number of input lines is not a multiple of four")
    width = len(lines[0])
    if width % 3 != 0 or any(len(line) != width for line in lines):
        raise ValueError("Number of input columns is not a multiple of three")

    rows = [lines[i:i + 4] for i in range(0, len(lines), 4)]
    results = []
    for group in reversed(rows):
        digits = []
        for c in range(0, width, 3):
            key = tuple(line[c:c + 3] for line in group)
            digits.append(DIGITS.get(key, "?"))
        results.append("".join(digits))
    return ",".join(results)
