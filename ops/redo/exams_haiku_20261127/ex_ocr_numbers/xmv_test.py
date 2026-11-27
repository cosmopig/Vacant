import pytest

from ocr_numbers import convert

# Each digit is a 3-column by 4-row glyph. Row 4 is always blank.
GLYPHS = {
    0: [" _ ", "| |", "|_|", "   "],
    1: ["   ", "  |", "  |", "   "],
    2: [" _ ", " _|", "|_ ", "   "],
    3: [" _ ", " _|", " _|", "   "],
    4: ["   ", "|_|", "  |", "   "],
    5: [" _ ", "|_ ", " _|", "   "],
    6: [" _ ", "|_ ", "|_|", "   "],
    7: [" _ ", "  |", "  |", "   "],
    8: [" _ ", "|_|", "|_|", "   "],
    9: [" _ ", "|_|", " _|", "   "],
    # Not a digit glyph, used to produce an unrecognisable cell.
    "X": [" _ ", "| |", "| |", "   "],
}


def make_grid(*rows):
    """Build a grid string. Each row is a list of digit keys (0-9 or "X")."""
    lines = []
    for row in rows:
        for r in range(4):
            lines.append("".join(GLYPHS[cell][r] for cell in row))
    return "\n".join(lines)


def test_recognises_each_digit_alone():
    for digit in range(10):
        # SRC: "Given a grid of characters representing some digits, convert the grid to a string of digits."
        assert convert(make_grid([digit])) == str(digit)


def test_all_digits_in_one_row():
    # SRC: "The following input (without the comments) is converted to"
    assert convert(make_grid([1, 2, 3, 4, 5, 6, 7, 8, 9, 0])) == "1234567890"


def test_three_digits_in_one_row():
    # SRC: "Each cell is three columns wide and four rows high (3x4) and represents one digit."
    assert convert(make_grid([1, 2, 3])) == "123"


def test_multiple_rows_are_separated_by_comma():
    # SRC: "If the grid has multiple rows of cells, the rows should be separated in the output with a"
    assert convert(make_grid([1, 2, 3], [4, 5, 6], [7, 8, 9])) == "123,456,789"


def test_two_rows_of_two_digits():
    # SRC: "If the grid has multiple rows of cells, the rows should be separated in the output with a"
    assert convert(make_grid([1, 0], [0, 1])) == "10,01"


def test_unrecognised_cell_becomes_question_mark():
    # SRC: "but a cell is not recognizable, your program should output a"
    assert convert(make_grid([1, "X", 2])) == "1?2"


def test_single_unrecognised_cell():
    # SRC: "but a cell is not recognizable, your program should output a"
    assert convert(make_grid(["X"])) == "?"


def test_row_count_not_multiple_of_four_raises_value_error():
    # Three lines of a 4-line cell is an invalid size.
    bad_grid = "\n".join(make_grid([1]).split("\n")[:3])
    # SRC: "If the input is not a valid size, your program should indicate there is an error."
    with pytest.raises(ValueError) as excinfo:
        convert(bad_grid)
    # SRC: "include a message with it."
    assert str(excinfo.value) != ""


def test_column_count_not_multiple_of_three_raises_value_error():
    # Four rows of four columns each is an invalid size.
    bad_grid = "\n".join(["    "] * 4)
    # SRC: "If the input is not a valid size, your program should indicate there is an error."
    with pytest.raises(ValueError):
        convert(bad_grid)
