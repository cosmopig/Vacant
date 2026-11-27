"""Acceptance tests for the Flower Field `annotate` function.

Each check function covers one property taken from the requirements text.
Inputs are lists of strings: one string per board row, ' ' for an empty
square and '*' for a flower. The function returns the annotated board in
the same shape.
"""

import pytest

from flower_field import annotate


def test_example_5x4_board_is_annotated_as_described():
    """REQ: "Which your code should transform into this:" (5 x 4 example from the text)."""
    garden = [
        " * * ",
        "  *  ",
        "  *  ",
        "     ",
    ]
    expected = [
        "1*3*1",
        "13*31",
        " 2*2 ",
        " 111 ",
    ]
    assert annotate(garden) == expected


def test_output_is_list_of_strings_with_same_dimensions():
    """REQ: "The garden itself is a rectangle board composed of squares that are either empty (' ') or a flower ('*')." """
    garden = [
        " * * ",
        "  *  ",
        "  *  ",
        "     ",
    ]
    result = annotate(garden)
    assert isinstance(result, list)
    assert all(isinstance(row, str) for row in result)
    assert len(result) == 4
    assert all(len(row) == 5 for row in result)


def test_empty_square_without_adjacent_flowers_stays_empty():
    """REQ: "If the empty square has no adjacent flowers, leave it empty." """
    garden = [
        "*  ",
        "   ",
        "   ",
    ]
    result = annotate(garden)
    # (0,1) is adjacent to the flower and becomes 1; (1,2) and (2,2) have no
    # adjacent flowers and must stay as spaces.
    assert result[1][2] == " "
    assert result[2][2] == " "
    assert result[2][0] == " "


def test_empty_square_with_adjacent_flower_is_replaced_by_count():
    """REQ: "Otherwise replace it with the count of adjacent flowers." """
    garden = [
        "*  ",
        "   ",
        "   ",
    ]
    result = annotate(garden)
    assert result[0][1] == "1"
    assert result[1][0] == "1"
    assert result[1][1] == "1"


def test_flowers_are_never_changed():
    """REQ: "For each empty square, count the number of flowers adjacent to it" (only empty squares are replaced)."""
    garden = [
        " * * ",
        "  *  ",
        "  *  ",
        "     ",
    ]
    result = annotate(garden)
    for r, row in enumerate(garden):
        for c, ch in enumerate(row):
            if ch == "*":
                assert result[r][c] == "*", f"flower at ({r},{c}) was changed"


def test_diagonal_neighbours_are_counted():
    """REQ: "count the number of flowers adjacent to it (horizontally, vertically, diagonally)." """
    garden = [
        "   ",
        " * ",
        "   ",
    ]
    expected = [
        "111",
        "1*1",
        "111",
    ]
    assert annotate(garden) == expected


def test_count_can_reach_eight():
    """REQ: "count the number of flowers adjacent to it" (an empty square has at most eight neighbours)."""
    garden = [
        "***",
        "* *",
        "***",
    ]
    expected = [
        "***",
        "*8*",
        "***",
    ]
    assert annotate(garden) == expected


def test_no_wraparound_at_board_edges():
    """REQ: "adjacent (horizontally, vertically, diagonally)" (adjacency is within the board, not wrapped around)."""
    garden = [
        "  *",
        "   ",
        "   ",
    ]
    expected = [
        " 1*",
        " 11",
        "   ",
    ]
    assert annotate(garden) == expected


def test_single_row_board():
    """REQ: "The garden itself is a rectangle board composed of squares" (a 1 x N rectangle is valid)."""
    garden = [" * "]
    assert annotate(garden) == ["1*1"]


def test_single_column_board():
    """REQ: "The garden itself is a rectangle board composed of squares" (an N x 1 rectangle is valid)."""
    garden = [" ", "*", " "]
    assert annotate(garden) == ["1", "*", "1"]


def test_single_square_board_is_unchanged():
    """REQ: "If the empty square has no adjacent flowers, leave it empty." (a lone square has no neighbours)."""
    assert annotate([" "]) == [" "]
    assert annotate(["*"]) == ["*"]


def test_board_without_flowers_is_unchanged():
    """REQ: "If the empty square has no adjacent flowers, leave it empty." (no flowers means no counts)."""
    garden = [
        "   ",
        "   ",
    ]
    assert annotate(garden) == ["   ", "   "]


def test_board_full_of_flowers_is_unchanged():
    """REQ: "For each empty square, count the number of flowers adjacent to it" (no empty squares means nothing to replace)."""
    garden = [
        "**",
        "**",
    ]
    assert annotate(garden) == ["**", "**"]


def test_output_contains_only_spaces_flowers_and_counts():
    """REQ: "Otherwise replace it with the count of adjacent flowers." (output squares are ' ', '*', or a count digit 1-8)."""
    garden = [
        " * * ",
        "  *  ",
        "  *  ",
        "     ",
    ]
    result = annotate(garden)
    allowed = set(" *12345678")
    for row in result:
        assert set(row) <= allowed, f"unexpected character in row {row!r}"


def test_malformed_ragged_rows_raise_value_error():
    """REQ: "This particular exercise requires that you use the raise statement to "throw" a ValueError when the board() function receives malformed input." (ragged rows are malformed; the text names board() but the stub provides annotate())."""
    garden = [
        "   ",
        "  ",
    ]
    with pytest.raises(ValueError):
        annotate(garden)


def test_invalid_square_character_raises_value_error():
    """REQ: "This particular exercise requires that you use the raise statement to "throw" a ValueError when the board() function receives malformed input." (squares must be ' ' or '*')."""
    garden = [
        " x ",
        "   ",
    ]
    with pytest.raises(ValueError):
        annotate(garden)


def test_value_error_includes_a_message():
    """REQ: "The tests will only pass if you both raise the exception and include a message with it." """
    garden = [
        "   ",
        "  ",
    ]
    with pytest.raises(ValueError) as excinfo:
        annotate(garden)
    assert str(excinfo.value).strip() != ""
