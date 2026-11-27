import pytest

from minesweeper import annotate


def test_empty_board_returns_empty():
    assert annotate([]) == []


def test_board_without_mines_is_unchanged():
    assert annotate(["   ", "   "]) == ["   ", "   "]


def test_board_of_only_mines_is_unchanged():
    assert annotate(["**", "**"]) == ["**", "**"]


def test_single_empty_square_stays_empty():
    assert annotate([" "]) == [" "]


def test_single_mine_square_stays_mine():
    assert annotate(["*"]) == ["*"]


def test_single_row_counts_horizontal_neighbours():
    assert annotate([" * "]) == ["1*1"]


def test_single_column_counts_vertical_neighbours():
    assert annotate([" ", "*", " "]) == ["1", "*", "1"]


def test_corner_squares_count_diagonal_neighbours():
    assert annotate(["* ", "  "]) == ["*1", "11"]


def test_centre_mine_counts_all_eight_neighbours():
    assert annotate(["   ", " * ", "   "]) == ["111", "1*1", "111"]


def test_example_board_from_requirements():
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
    assert annotate(board) == expected


def test_rows_of_unequal_length_raise_value_error():
    with pytest.raises(ValueError) as excinfo:
        annotate(["  ", " "])
    assert str(excinfo.value)


def test_invalid_character_raises_value_error():
    with pytest.raises(ValueError) as excinfo:
        annotate(["x "])
    assert str(excinfo.value)
