import pytest

from ocr_numbers import convert


def _block(top, mid, bottom):
    """Build the four text lines of one row of cells (last line is always blank)."""
    return [
        "".join(top),
        "".join(mid),
        "".join(bottom),
        " " * (3 * len(top)),
    ]


def _grid(*blocks):
    """Join row-blocks into one multi-line input string."""
    lines = []
    for block in blocks:
        lines.extend(block)
    return "\n".join(lines)


# Cell shapes for the digits 1234567890, in order, as in the requirements example.
ALL_TOP = ["   ", " _ ", " _ ", "   ", " _ ", " _ ", " _ ", " _ ", " _ ", " _ "]
ALL_MID = ["  |", " _|", " _|", "|_|", "|_ ", "|_ ", "  |", "|_|", "|_|", "| |"]
ALL_BOT = ["  |", "|_ ", " _|", "  |", " _|", "|_|", "  |", "|_|", " _|", "|_|"]


def test_recognizes_zero():
    assert convert(_grid(_block([" _ "], ["| |"], ["|_|"]))) == "0"


def test_recognizes_one():
    assert convert(_grid(_block(["   "], ["  |"], ["  |"]))) == "1"


def test_recognizes_all_digits_in_one_row():
    assert convert(_grid(_block(ALL_TOP, ALL_MID, ALL_BOT))) == "1234567890"


def test_multiple_rows_are_separated_by_commas():
    block_1 = _block(
        ["   ", " _ ", " _ "],
        ["  |", " _|", " _|"],
        ["  |", "|_ ", " _|"],
    )
    block_2 = _block(
        ["   ", " _ ", " _ "],
        ["|_|", "|_ ", "|_ "],
        ["  |", " _|", "|_|"],
    )
    block_3 = _block(
        [" _ ", " _ ", " _ "],
        ["  |", "|_|", "|_|"],
        ["  |", "|_|", " _|"],
    )
    assert convert(_grid(block_1, block_2, block_3)) == "123,456,789"


def test_two_rows_of_single_digits():
    one = _block(["   "], ["  |"], ["  |"])
    assert convert(_grid(one, one)) == "1,1"


def test_unrecognized_cell_becomes_question_mark():
    # Cell 1 is a "1"; cell 2 is three underscores in every line, which is not a digit.
    block = _block(
        ["   ", "___"],
        ["  |", "___"],
        ["  |", "___"],
    )
    assert convert(_grid(block)) == "1?"


def test_only_unrecognized_cell_becomes_question_mark():
    block = _block(["___"], ["___"], ["___"])
    assert convert(_grid(block)) == "?"


def test_line_count_not_multiple_of_four_raises_value_error():
    # Three lines instead of four.
    with pytest.raises(ValueError):
        convert("   \n  |\n  |")


def test_five_lines_raises_value_error():
    with pytest.raises(ValueError):
        convert("   \n  |\n  |\n   \n   ")


def test_column_count_not_multiple_of_three_raises_value_error():
    # Two columns per line instead of three.
    with pytest.raises(ValueError):
        convert("  \n |\n |\n  ")


def test_four_columns_per_line_raises_value_error():
    with pytest.raises(ValueError):
        convert("    \n   |\n   |\n    ")


def test_error_includes_a_meaningful_message():
    with pytest.raises(ValueError) as excinfo:
        convert("   \n  |\n  |")
    assert str(excinfo.value).strip() != ""
