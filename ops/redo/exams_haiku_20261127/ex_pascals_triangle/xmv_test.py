import pytest

from pascals_triangle import rows


def test_first_row_is_single_one():
    # SRC: "The first (topmost) row has a single value: `1`."
    assert rows(1) == [[1]]


def test_second_row_has_two_ones():
    # SRC: "Subsequent rows' values are computed by adding the numbers directly to the right and left of the current position in the previous row."
    assert rows(2) == [[1], [1, 1]]


def test_first_three_rows():
    # SRC: "Let's look at the first 5 rows of Pascal's Triangle:"
    assert rows(3) == [[1], [1, 1], [1, 2, 1]]


def test_first_four_rows():
    # SRC: "Let's look at the first 5 rows of Pascal's Triangle:"
    assert rows(4) == [[1], [1, 1], [1, 2, 1], [1, 3, 3, 1]]


def test_first_five_rows_match_example():
    # SRC: "Let's look at the first 5 rows of Pascal's Triangle:"
    assert rows(5) == [
        [1],
        [1, 1],
        [1, 2, 1],
        [1, 3, 3, 1],
        [1, 4, 6, 4, 1],
    ]


def test_sixth_row_is_correct():
    # SRC: "Subsequent rows' values are computed by adding the numbers directly to the right and left of the current position in the previous row."
    assert rows(6)[5] == [1, 5, 10, 10, 5, 1]


def test_row_length_equals_row_number():
    # SRC: "In Pascal's triangle, the number of values in a row is equal to its row number (which starts at one)."
    assert len(rows(5)[4]) == 5


def test_edge_values_are_one():
    # SRC: "With the topmost value being `1`, it follows from this that all the leftmost and rightmost values are also `1`."
    assert all(row[0] == 1 and row[-1] == 1 for row in rows(6))


def test_middle_value_is_sum_of_two_above():
    # SRC: "For example, the fifth row's (`1 4 6 4 1`) middle value is `6`, as the values to its left and right in the preceding row are `3` and `3`:"
    assert rows(5)[4][2] == 6


def test_negative_row_count_raises_value_error():
    # SRC: "if the `rows()` function is passed a negative number."
    with pytest.raises(ValueError) as excinfo:
        rows(-1)
    # SRC: "include a message with it."
    assert str(excinfo.value).strip() != ""
