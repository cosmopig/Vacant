import pytest

from queen_attack import Queen


def test_example_c5_f2_share_diagonal_can_attack():
    """REQ: "In this case, that answer would be yes, they can, because both pieces share a diagonal."

    Example: white queen at c5 (row 3, column 2), black queen at f2 (row 6, column 5).
    Row difference 3 and column difference 3 give a shared diagonal, so they attack.
    """
    white = Queen(3, 2)
    black = Queen(6, 5)
    assert white.can_attack(black) is True


def test_can_attack_returns_bool():
    """REQ: "Given the position of two queens on a chess board, indicate whether or not they are positioned so that they can attack each other."

    The answer is a yes/no indication, so the return value must be a bool, both when they attack and when they do not.
    """
    assert isinstance(Queen(3, 2).can_attack(Queen(6, 5)), bool)
    assert isinstance(Queen(2, 4).can_attack(Queen(6, 6)), bool)


def test_queens_on_same_row_can_attack():
    """REQ: "In the game of chess, a queen can attack pieces which are on the same row, column, or diagonal."

    Two queens on row 2 at columns 0 and 7 share a row, so they attack.
    """
    assert Queen(2, 0).can_attack(Queen(2, 7)) is True


def test_queens_on_same_column_can_attack():
    """REQ: "In the game of chess, a queen can attack pieces which are on the same row, column, or diagonal."

    Two queens on column 4 at rows 0 and 7 share a column, so they attack.
    """
    assert Queen(0, 4).can_attack(Queen(7, 4)) is True


def test_queens_on_main_diagonal_corners_can_attack():
    """REQ: "In the game of chess, a queen can attack pieces which are on the same row, column, or diagonal."

    Queens at (0, 0) and (7, 7) lie on the same main diagonal, so they attack.
    """
    assert Queen(0, 0).can_attack(Queen(7, 7)) is True


def test_queens_on_anti_diagonal_corners_can_attack():
    """REQ: "In the game of chess, a queen can attack pieces which are on the same row, column, or diagonal."

    Queens at (0, 7) and (7, 0) lie on the same anti-diagonal, so they attack.
    """
    assert Queen(0, 7).can_attack(Queen(7, 0)) is True


def test_queens_on_inner_diagonal_can_attack():
    """REQ: "In the game of chess, a queen can attack pieces which are on the same row, column, or diagonal."

    Queens at (1, 1) and (4, 4) are on the same diagonal with squares between them, so they attack.
    """
    assert Queen(1, 1).can_attack(Queen(4, 4)) is True


def test_knight_move_apart_cannot_attack():
    """REQ: "In the game of chess, a queen can attack pieces which are on the same row, column, or diagonal."

    Queens at (0, 0) and (1, 2) differ in both row and column and are not on a common diagonal, so they cannot attack.
    """
    assert Queen(0, 0).can_attack(Queen(1, 2)) is False


def test_unrelated_positions_cannot_attack():
    """REQ: "Given the position of two queens on a chess board, indicate whether or not they are positioned so that they can attack each other."

    Queens at (2, 4) and (6, 6) share no row, column, or diagonal (row difference 4, column difference 2), so they cannot attack.
    """
    assert Queen(2, 4).can_attack(Queen(6, 6)) is False


def test_attack_relation_is_symmetric():
    """REQ: "In the game of chess, a queen can attack pieces which are on the same row, column, or diagonal."

    Whether queen A attacks queen B must be the same as whether B attacks A.
    """
    cases = [
        ((0, 0), (1, 2), False),
        ((2, 4), (6, 6), False),
        ((3, 2), (6, 5), True),
        ((0, 3), (5, 3), True),
        ((1, 6), (4, 3), True),
        ((2, 0), (2, 7), True),
    ]
    for (r1, c1), (r2, c2), expected in cases:
        a = Queen(r1, c1)
        b = Queen(r2, c2)
        assert a.can_attack(b) is expected
        assert b.can_attack(a) is expected


def test_board_corners_are_valid_positions():
    """REQ: "A chessboard can be represented by an 8 by 8 array."

    Rows and columns run from 0 to 7, so all four corners must construct without error and can be used in can_attack.
    """
    corners = [Queen(0, 0), Queen(0, 7), Queen(7, 0), Queen(7, 7)]
    for queen in corners:
        assert isinstance(queen, Queen)
    assert corners[0].can_attack(corners[3]) is True
    assert corners[1].can_attack(corners[2]) is True


def test_negative_row_raises_value_error():
    """REQ: "This particular exercise requires that you use the raise statement to throw ValueErrors if the Queen constructor is passed numbers that are negative, or numbers that are not a valid row or column."

    A negative row must raise ValueError with the message "row not positive".
    """
    with pytest.raises(ValueError) as excinfo:
        Queen(-1, 0)
    assert str(excinfo.value) == "row not positive"


def test_negative_column_raises_value_error():
    """REQ: "This particular exercise requires that you use the raise statement to throw ValueErrors if the Queen constructor is passed numbers that are negative, or numbers that are not a valid row or column."

    A negative column must raise ValueError with the message "column not positive".
    """
    with pytest.raises(ValueError) as excinfo:
        Queen(0, -1)
    assert str(excinfo.value) == "column not positive"


def test_row_off_board_raises_value_error():
    """REQ: "This particular exercise requires that you use the raise statement to throw ValueErrors if the Queen constructor is passed numbers that are negative, or numbers that are not a valid row or column."

    A row of 8 is outside the 8 by 8 board and must raise ValueError with the message "row not on board".
    """
    with pytest.raises(ValueError) as excinfo:
        Queen(8, 0)
    assert str(excinfo.value) == "row not on board"


def test_column_off_board_raises_value_error():
    """REQ: "This particular exercise requires that you use the raise statement to throw ValueErrors if the Queen constructor is passed numbers that are negative, or numbers that are not a valid row or column."

    A column of 8 is outside the 8 by 8 board and must raise ValueError with the message "column not on board".
    """
    with pytest.raises(ValueError) as excinfo:
        Queen(0, 8)
    assert str(excinfo.value) == "column not on board"


def test_same_square_raises_value_error():
    """REQ: "You also should raise a ValueError if both the queens passed to the can_attack() method are on the same location."

    Calling can_attack with two queens on the same square must raise ValueError with the message "Invalid queen position: both queens in the same square".
    """
    first = Queen(4, 4)
    second = Queen(4, 4)
    with pytest.raises(ValueError) as excinfo:
        first.can_attack(second)
    assert str(excinfo.value) == "Invalid queen position: both queens in the same square"


def test_invalid_input_errors_have_nonempty_messages():
    """REQ: "When you do this, you should always include a meaningful error message to indicate what the source of the error is."

    Every ValueError raised for invalid constructor input must carry a non-empty message.
    """
    invalid_inputs = [(-1, 0), (0, -1), (8, 0), (0, 8)]
    for row, column in invalid_inputs:
        with pytest.raises(ValueError) as excinfo:
            Queen(row, column)
        assert str(excinfo.value).strip() != ""
