import pytest

from minesweeper import annotate


def test_example_board_from_requirements_is_annotated():
    board = [
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
    # SRC: "For each empty square, count the number of mines adjacent to it (horizontally, vertically, diagonally)."
    assert annotate(board) == expected


def test_empty_square_without_adjacent_mines_stays_empty():
    board = [
        "   ",
        "   ",
    ]
    expected = [
        "   ",
        "   ",
    ]
    # SRC: "If the empty square has no adjacent mines, leave it empty."
    assert annotate(board) == expected


def test_empty_square_next_to_one_mine_shows_count_one():
    board = [
        "*",
        " ",
    ]
    expected = [
        "*",
        "1",
    ]
    # SRC: "Otherwise replace it with the adjacent mines count."
    assert annotate(board) == expected


def test_mines_are_counted_diagonally():
    board = [
        "* ",
        "  ",
    ]
    expected = [
        "*1",
        "11",
    ]
    # SRC: "count the number of mines adjacent to it (horizontally, vertically, diagonally)."
    assert annotate(board) == expected


def test_empty_centre_surrounded_by_eight_mines_shows_eight():
    board = [
        "***",
        "* *",
        "***",
    ]
    expected = [
        "***",
        "*8*",
        "***",
    ]
    # SRC: "Otherwise replace it with the adjacent mines count."
    assert annotate(board) == expected


def test_mine_squares_are_not_replaced_by_counts():
    board = [
        "**",
        "**",
    ]
    expected = [
        "**",
        "**",
    ]
    # SRC: "For each empty square"
    assert annotate(board) == expected


def test_non_rectangular_board_raises_value_error():
    board = [
        "   ",
        "  ",
    ]
    # SRC: "The board itself is a rectangle"
    with pytest.raises(ValueError) as exc_info:
        annotate(board)
    # SRC: "The tests will only pass if you both `raise` the `exception` and include a message with it."
    assert str(exc_info.value).strip() != ""


def test_square_that_is_neither_empty_nor_mine_raises_value_error():
    board = [
        "*x",
    ]
    # SRC: "The board itself is a rectangle composed of squares that are either empty (`' '`) or a mine (`'*'`)."
    with pytest.raises(ValueError):
        annotate(board)
