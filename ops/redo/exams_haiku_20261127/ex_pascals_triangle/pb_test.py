import pytest

from pascals_triangle import rows


def test_output_is_list_of_lists_of_ints():
    """REQ: "Your task is to output the first N rows of Pascal's triangle."

    The result is a list whose elements are rows, and each row is a list of ints.
    """
    result = rows(4)
    assert isinstance(result, list)
    for row in result:
        assert isinstance(row, list)
        for value in row:
            assert isinstance(value, int) and not isinstance(value, bool)


def test_zero_rows_gives_empty_list():
    """REQ: "Your task is to output the first N rows of Pascal's triangle."

    With N = 0 there are no rows to output, so the result is an empty list.
    """
    assert rows(0) == []


def test_first_row_is_single_one():
    """REQ: "The first (topmost) row has a single value: `1`."

    The topmost row is [1].
    """
    assert rows(1) == [[1]]


def test_number_of_rows_equals_n():
    """REQ: "Your task is to output the first N rows of Pascal's triangle."

    rows(N) returns exactly N rows.
    """
    for n in (1, 2, 3, 7, 10):
        assert len(rows(n)) == n


def test_row_k_has_k_values():
    """REQ: "In Pascal's triangle, the number of values in a row is equal to its row number (which starts at one)."

    Row number k (starting at one) contains exactly k values.
    """
    result = rows(8)
    for k in range(1, 9):
        assert len(result[k - 1]) == k


def test_leftmost_and_rightmost_values_are_one():
    """REQ: "The leftmost and rightmost values have only one preceding position to consider ... all the leftmost and rightmost values are also `1`."

    Every row starts and ends with 1.
    """
    result = rows(8)
    for row in result:
        assert row[0] == 1
        assert row[-1] == 1


def test_interior_value_is_sum_of_two_above():
    """REQ: "Subsequent rows' values are computed by adding the numbers directly to the right and left of the current position in the previous row."

    Each interior value equals the sum of the two values directly above it.
    """
    result = rows(10)
    for k in range(1, len(result)):
        prev = result[k - 1]
        cur = result[k]
        for j in range(1, len(cur) - 1):
            assert cur[j] == prev[j - 1] + prev[j]


def test_missing_neighbour_is_treated_as_zero_at_edges():
    """REQ: "If the previous row does not have a value to the left or right of the current position (which only happens for the leftmost and rightmost positions), treat that position's value as zero"

    At the edges the missing neighbour contributes zero, so the edge value equals the previous row's edge value.
    """
    result = rows(9)
    for k in range(1, len(result)):
        assert result[k][0] == result[k - 1][0]
        assert result[k][-1] == result[k - 1][-1]


def test_rows_are_symmetric():
    """REQ: "Subsequent rows' values are computed by adding the numbers directly to the right and left of the current position in the previous row."

    The addition rule is symmetric left-to-right, so each row reads the same reversed.
    """
    for row in rows(9):
        assert row == row[::-1]


def test_values_are_positive_integers():
    """REQ: "[Pascal's triangle][wikipedia] is a triangular array of positive integers."

    Every value in the output is a positive integer.
    """
    for row in rows(9):
        for value in row:
            assert isinstance(value, int)
            assert value > 0


def test_smaller_output_is_prefix_of_larger_output():
    """REQ: "Your task is to output the first N rows of Pascal's triangle."

    The first N rows do not depend on how many rows are requested overall.
    """
    assert rows(3) == rows(6)[:3]
    assert rows(1) == rows(9)[:1]


def test_example_first_five_rows():
    """REQ: "Let's look at the first 5 rows of Pascal's Triangle:"

    The first five rows are [1], [1,1], [1,2,1], [1,3,3,1], [1,4,6,4,1].
    """
    assert rows(5) == [[1], [1, 1], [1, 2, 1], [1, 3, 3, 1], [1, 4, 6, 4, 1]]


def test_fifth_row_middle_value_is_six():
    """REQ: "the fifth row's (`1 4 6 4 1`) middle value is `6`, as the values to its left and right in the preceding row are `3` and `3`"

    The middle value of the fifth row is 6.
    """
    assert rows(5)[4][2] == 6


def test_sixth_row_matches_computed_values():
    """REQ: "Subsequent rows' values are computed by adding the numbers directly to the right and left of the current position in the previous row."

    Applying the addition rule to the fifth row [1,4,6,4,1] gives the sixth row [1,5,10,10,5,1].
    """
    assert rows(6)[5] == [1, 5, 10, 10, 5, 1]


def test_negative_row_count_raises_value_error():
    """REQ: "This particular exercise requires that you use the raise statement to \"throw\" multiple `ValueErrors` if the `rows()` function is passed a negative number."

    Passing a negative number raises ValueError.
    """
    for n in (-1, -5):
        with pytest.raises(ValueError):
            rows(n)


def test_negative_row_count_error_has_message():
    """REQ: "The tests will only pass if you both `raise` the `exception` and include a message with it."

    The ValueError raised for a negative row count carries a non-empty message.
    """
    with pytest.raises(ValueError) as excinfo:
        rows(-3)
    assert str(excinfo.value).strip() != ""
