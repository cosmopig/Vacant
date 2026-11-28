"""Acceptance tests for the OCR numbers exercise (module: ocr_numbers).

Each test_ function checks one property derived from the requirements text.
"""

import pytest

from ocr_numbers import convert


# Glyph table: each digit is drawn as 4 lines of 3 characters (3x4 cell).
# Derived from the example grids in the requirements text.
_GLYPHS = {
    "0": (" _ ", "| |", "|_|", "   "),
    "1": ("   ", "  |", "  |", "   "),
    "2": (" _ ", " _|", "|_ ", "   "),
    "3": (" _ ", " _|", " _|", "   "),
    "4": ("   ", "|_|", "  |", "   "),
    "5": (" _ ", "|_ ", " _|", "   "),
    "6": (" _ ", "|_ ", "|_|", "   "),
    "7": (" _ ", "  |", "  |", "   "),
    "8": (" _ ", "|_|", "|_|", "   "),
    "9": (" _ ", "|_|", " _|", "   "),
}

# A 3x4 cell that is not a digit glyph.
_UNKNOWN_CELL = ("   ", "| |", "| |", "   ")


def _block(digits):
    """Return the 4 text lines for a row of digits, joined by newlines."""
    lines = []
    for line_index in range(4):
        lines.append("".join(_GLYPHS[ch][line_index] for ch in digits))
    return "\n".join(lines)


def _multi_row(*rows):
    """Return a full grid string for several rows of digits."""
    return "\n".join(_block(row).split("\n") and _block(row) for row in rows)


def _grid_from_row_blocks(*rows):
    """Stack row blocks into a single grid string, one 4-line block per row."""
    all_lines = []
    for row in rows:
        all_lines.extend(_block(row).split("\n"))
    return "\n".join(all_lines)


def test_returns_string_for_valid_grid():
    """REQ: "Given a grid of characters representing some digits, convert the grid to a string of digits."

    Property: a valid grid input produces a str output.
    """
    result = convert(_block("0"))
    assert isinstance(result, str)


def test_single_row_example_converts_to_expected_digits():
    """REQ: "The following input (without the comments) is converted to \"1234567890\"."

    Property: the single-row example grid converts to "1234567890".
    """
    grid = _grid_from_row_blocks("1234567890")
    assert convert(grid) == "1234567890"


def test_multi_row_example_separates_rows_with_comma():
    """REQ: "The following input is converted to \"123,456,789\"."

    Property: the three-row example converts to "123,456,789", with rows separated by ",".
    """
    grid = _grid_from_row_blocks("123", "456", "789")
    assert convert(grid) == "123,456,789"


def test_two_rows_are_separated_by_single_comma():
    """REQ: "If the grid has multiple rows of cells, the rows should be separated in the output with a `\",\"`."

    Property: two rows of identical digits produce exactly one comma between them.
    """
    grid = _grid_from_row_blocks("000", "111")
    assert convert(grid) == "000,111"


def test_each_digit_zero_to_nine_is_recognized():
    """REQ: "Each cell is three columns wide and four rows high (3x4) and represents one digit."

    Property: each of the ten digit glyphs, drawn as a single cell, converts to its own digit.
    """
    for digit in "0123456789":
        assert convert(_block(digit)) == digit


def test_unrecognizable_cell_outputs_question_mark():
    """REQ: "If the input is the correct size, but a cell is not recognizable, your program should output a `\"?\"` for that character."

    Property: a blank 3x4 cell (correct size, not a digit) converts to "?".
    """
    blank_cell = ["   ", "   ", "   ", "   "]
    grid = "\n".join(blank_cell)
    assert convert(grid) == "?"


def test_unrecognizable_cell_inside_row_outputs_question_mark_in_place():
    """REQ: "If the input is the correct size, but a cell is not recognizable, your program should output a `\"?\"` for that character."

    Property: an unrecognizable cell between valid digits yields "?" at that position only.
    """
    rows = []
    for cell in (_GLYPHS["1"], _UNKNOWN_CELL, _GLYPHS["2"]):
        rows.append(cell)
    grid_lines = []
    for line_index in range(4):
        grid_lines.append("".join(cell[line_index] for cell in rows))
    grid = "\n".join(grid_lines)
    assert convert(grid) == "1?2"


def test_invalid_row_count_raises_value_error_with_message():
    """REQ: "If the input is not a valid size, your program should indicate there is an error."

    Property: a grid whose number of lines is not a multiple of four raises ValueError with a message.
    """
    grid = "\n".join(["   ", "   ", "   "])
    with pytest.raises(ValueError) as excinfo:
        convert(grid)
    assert str(excinfo.value).strip() != ""


def test_invalid_column_count_raises_value_error_with_message():
    """REQ: "This particular exercise requires that you use the raise statement to \"throw\" a `ValueError` when the `convert()` function receives a string that isn't a valid OCR number."

    Property: a grid whose line width is not a multiple of three raises ValueError with a message.
    """
    grid = "\n".join(["    ", "    ", "    ", "    "])
    with pytest.raises(ValueError) as excinfo:
        convert(grid)
    assert str(excinfo.value).strip() != ""


def test_output_contains_only_digits_question_marks_and_commas():
    """REQ: "Given a grid of characters representing some digits, convert the grid to a string of digits."

    Property: for a mixed grid of valid digits, unrecognizable cells, and multiple rows,
    the output contains only digits, "?", and ",".
    """
    rows = [
        [_GLYPHS["4"], _UNKNOWN_CELL, _GLYPHS["7"]],
        [_GLYPHS["0"], _GLYPHS["9"], _UNKNOWN_CELL],
    ]
    grid_lines = []
    for row in rows:
        for line_index in range(4):
            grid_lines.append("".join(cell[line_index] for cell in row))
    result = convert("\n".join(grid_lines))
    assert result == "4?7,09?"
    assert set(result) <= set("0123456789?,")
