import pytest

from flower_field import annotate


def test_board_with_no_flowers_is_unchanged():
    assert annotate(["   ", "   "]) == ["   ", "   "]


def test_board_with_only_flowers_is_unchanged():
    assert annotate(["**", "**"]) == ["**", "**"]


def test_single_flower_on_single_square():
    assert annotate(["*"]) == ["*"]


def test_single_row_counts_adjacent_flowers():
    # Position 0 touches one flower, position 2 touches two, position 4 touches one.
    assert annotate([" * * "]) == ["1*2*1"]


def test_diagonal_neighbours_are_counted():
    # The flower at (0,0) touches (0,1), (1,0) and the diagonal (1,1).
    assert annotate(["* ", "  "]) == ["*1", "11"]


def test_single_flower_in_centre_of_3x3():
    board = ["   ", " * ", "   "]
    assert annotate(board) == ["111", "1*1", "111"]


def test_spec_example_board():
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


def test_empty_square_without_adjacent_flowers_stays_empty():
    board = ["*   ", "    ", "    "]
    result = annotate(board)
    assert result[2][3] == " "
    assert result[1][3] == " "


def test_rows_of_unequal_length_raise_value_error():
    with pytest.raises(ValueError):
        annotate(["   ", "  "])


def test_invalid_character_raises_value_error():
    with pytest.raises(ValueError):
        annotate([" x "])


def test_value_error_includes_a_message():
    with pytest.raises(ValueError) as excinfo:
        annotate(["  ", "   "])
    assert str(excinfo.value).strip() != ""
