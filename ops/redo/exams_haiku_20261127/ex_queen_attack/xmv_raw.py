import pytest

from queen_attack import Queen


def test_queens_on_same_row_can_attack():
    # SRC: "In the game of chess, a queen can attack pieces which are on the same row, column, or diagonal."
    assert Queen(2, 2).can_attack(Queen(2, 6)) is True


def test_queens_on_same_column_can_attack():
    # SRC: "In the game of chess, a queen can attack pieces which are on the same row, column, or diagonal."
    assert Queen(0, 4).can_attack(Queen(7, 4)) is True


def test_queens_on_same_diagonal_can_attack():
    # SRC: "because both pieces share a diagonal."
    assert Queen(3, 2).can_attack(Queen(6, 5)) is True


def test_queens_on_same_anti_diagonal_can_attack():
    # SRC: "In the game of chess, a queen can attack pieces which are on the same row, column, or diagonal."
    assert Queen(0, 7).can_attack(Queen(7, 0)) is True


def test_queens_not_on_same_row_column_or_diagonal_cannot_attack():
    # SRC: "In the game of chess, a queen can attack pieces which are on the same row, column, or diagonal."
    assert Queen(2, 4).can_attack(Queen(6, 6)) is False


def test_queens_with_knight_offset_cannot_attack():
    # SRC: "In the game of chess, a queen can attack pieces which are on the same row, column, or diagonal."
    assert Queen(0, 0).can_attack(Queen(1, 2)) is False


def test_attack_is_symmetric_between_queens():
    # SRC: "You are also able to answer whether the queens can attack each other."
    assert Queen(6, 5).can_attack(Queen(3, 2)) is True


def test_board_corners_on_main_diagonal_can_attack():
    # SRC: "A chessboard can be represented by an 8 by 8 array."
    assert Queen(0, 0).can_attack(Queen(7, 7)) is True


def test_queens_on_opposite_edges_of_same_column_can_attack():
    # SRC: "A chessboard can be represented by an 8 by 8 array."
    assert Queen(7, 0).can_attack(Queen(0, 0)) is True


def test_negative_row_raises_value_error():
    # SRC: "# if the row parameter is negative"
    with pytest.raises(ValueError, match="row not positive"):
        Queen(-1, 0)


def test_negative_column_raises_value_error():
    # SRC: "# if the column parameter is negative"
    with pytest.raises(ValueError, match="column not positive"):
        Queen(0, -1)


def test_row_off_board_raises_value_error():
    # SRC: "raise ValueError("row not on board")"
    with pytest.raises(ValueError, match="row not on board"):
        Queen(8, 0)


def test_column_off_board_raises_value_error():
    # SRC: "raise ValueError("column not on board")"
    with pytest.raises(ValueError, match="column not on board"):
        Queen(0, 8)


def test_same_square_raises_value_error():
    # SRC: "You also should `raise` a `ValueError` if both the queens passed to the `can_attack()` method are on the same location."
    with pytest.raises(ValueError, match="Invalid queen position: both queens in the same square"):
        Queen(4, 4).can_attack(Queen(4, 4))
