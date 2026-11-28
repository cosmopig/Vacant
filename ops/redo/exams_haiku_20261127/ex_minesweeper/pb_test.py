import pytest

from minesweeper import annotate


def test_return_type_is_list_of_str_with_same_row_count():
    """REQ: "For each empty square, count the number of mines adjacent to it (horizontally, vertically, diagonally)." """
    board = [" * * ", "  *  ", "  *  ", "     "]
    result = annotate(board)
    assert isinstance(result, list)
    assert len(result) == len(board)
    for row in result:
        assert isinstance(row, str)


def test_output_rows_keep_input_dimensions():
    """REQ: "The board itself is a rectangle composed of squares that are either empty (`' '`) or a mine (`'*'`)." """
    board = [" * * ", "  *  ", "  *  ", "     "]
    result = annotate(board)
    assert len(result) == 4
    assert all(len(row) == 5 for row in result)


def test_empty_board_returns_empty_list():
    """REQ: "The board itself is a rectangle composed of squares that are either empty (`' '`) or a mine (`'*'`)." """
    assert annotate([]) == []


def test_single_empty_square_stays_empty():
    """REQ: "If the empty square has no adjacent mines, leave it empty." """
    assert annotate([" "]) == [" "]


def test_single_mine_square_stays_a_mine():
    """REQ: "The board itself is a rectangle composed of squares that are either empty (`' '`) or a mine (`'*'`)." """
    assert annotate(["*"]) == ["*"]


def test_board_without_mines_is_unchanged():
    """REQ: "If the empty square has no adjacent mines, leave it empty." """
    board = ["   ", "   ", "   "]
    assert annotate(board) == ["   ", "   ", "   "]


def test_board_of_only_mines_is_unchanged():
    """REQ: "For each empty square, count the number of mines adjacent to it (horizontally, vertically, diagonally)." """
    board = ["**", "**"]
    assert annotate(board) == ["**", "**"]


def test_mine_squares_are_never_replaced_by_counts():
    """REQ: "For each empty square, count the number of mines adjacent to it (horizontally, vertically, diagonally)." """
    board = [" * * ", "  *  ", "  *  ", "     "]
    result = annotate(board)
    for r, row in enumerate(board):
        for c, ch in enumerate(row):
            if ch == "*":
                assert result[r][c] == "*"


def test_example_board_is_transformed_correctly():
    """REQ: "For example, you may receive a 5 x 4 board like this" """
    board = [" * * ", "  *  ", "  *  ", "     "]
    expected = ["1*3*1", "13*31", " 2*2 ", " 111 "]
    assert annotate(board) == expected


def test_empty_square_with_no_adjacent_mines_remains_space_in_example():
    """REQ: "If the empty square has no adjacent mines, leave it empty." """
    board = [" * * ", "  *  ", "  *  ", "     "]
    result = annotate(board)
    assert result[2][0] == " "
    assert result[3][0] == " "
    assert result[2][4] == " "


def test_diagonal_neighbours_are_counted():
    """REQ: "For each empty square, count the number of mines adjacent to it (horizontally, vertically, diagonally)." """
    board = ["*  ", "   ", "   "]
    expected = ["*1 ", "11 ", "   "]
    assert annotate(board) == expected


def test_full_surrounding_gives_count_of_eight():
    """REQ: "Otherwise replace it with the adjacent mines count." """
    board = ["***", "* *", "***"]
    assert annotate(board) == ["***", "*8*", "***"]


def test_corner_square_counts_only_existing_neighbours():
    """REQ: "For each empty square, count the number of mines adjacent to it (horizontally, vertically, diagonally)." """
    board = ["**", "* "]
    assert annotate(board) == ["**", "*3"]


def test_no_wrap_around_at_board_edges():
    """REQ: "For each empty square, count the number of mines adjacent to it (horizontally, vertically, diagonally)." """
    board = ["  *"]
    assert annotate(board) == [" 1*"]


def test_ragged_board_raises_value_error_with_message():
    """REQ: "This particular exercise requires that you use the raise statement to "throw" a `ValueError` when the `board()` function receives malformed input." """
    with pytest.raises(ValueError) as excinfo:
        annotate(["   ", "  "])
    assert str(excinfo.value) != ""


def test_invalid_character_raises_value_error_with_message():
    """REQ: "This particular exercise requires that you use the raise statement to "throw" a `ValueError` when the `board()` function receives malformed input." """
    with pytest.raises(ValueError) as excinfo:
        annotate([" x "])
    assert str(excinfo.value) != ""
