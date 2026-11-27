import pytest

from queen_attack import Queen


def _expect_value_error(action):
    with pytest.raises(ValueError) as excinfo:
        action()
    assert str(excinfo.value).strip() != "", "ValueError must include a message"


def test_queens_on_same_row_can_attack():
    assert Queen(2, 2).can_attack(Queen(2, 5)) is True


def test_queens_on_same_column_can_attack():
    assert Queen(0, 4).can_attack(Queen(7, 4)) is True


def test_queens_on_diagonal_can_attack():
    assert Queen(1, 1).can_attack(Queen(6, 6)) is True


def test_queens_on_anti_diagonal_can_attack():
    assert Queen(0, 7).can_attack(Queen(7, 0)) is True


def test_example_from_instructions_c5_f2_can_attack():
    # c5 is row 3, column 2; f2 is row 6, column 5; they share a diagonal.
    assert Queen(3, 2).can_attack(Queen(6, 5)) is True


def test_queens_not_sharing_row_column_or_diagonal_cannot_attack():
    # Row diff 1, column diff 3: no shared line.
    assert Queen(2, 4).can_attack(Queen(3, 1)) is False


def test_far_apart_queens_not_on_a_line_cannot_attack():
    # Row diff 7, column diff 1: no shared line.
    assert Queen(0, 0).can_attack(Queen(7, 1)) is False


def test_can_attack_is_symmetric():
    assert Queen(3, 2).can_attack(Queen(6, 5)) == Queen(6, 5).can_attack(Queen(3, 2))
    assert Queen(2, 4).can_attack(Queen(3, 1)) == Queen(3, 1).can_attack(Queen(2, 4))


def test_corner_to_opposite_corner_can_attack():
    assert Queen(0, 0).can_attack(Queen(7, 7)) is True


def test_board_edge_boundary_positions_are_valid():
    # Largest valid indices are 7; these must construct and share row 0.
    assert Queen(0, 0).can_attack(Queen(0, 7)) is True


def test_negative_row_raises_value_error():
    _expect_value_error(lambda: Queen(-1, 0))


def test_negative_column_raises_value_error():
    _expect_value_error(lambda: Queen(0, -1))


def test_row_off_board_raises_value_error():
    _expect_value_error(lambda: Queen(8, 0))


def test_column_off_board_raises_value_error():
    _expect_value_error(lambda: Queen(0, 8))


def test_both_queens_on_same_square_raises_value_error():
    queen = Queen(4, 4)
    _expect_value_error(lambda: queen.can_attack(Queen(4, 4)))
