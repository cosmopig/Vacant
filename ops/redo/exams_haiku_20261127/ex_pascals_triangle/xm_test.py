import pytest

from pascals_triangle import rows


def test_zero_rows_returns_empty_list():
    assert rows(0) == []


def test_single_row():
    assert rows(1) == [[1]]


def test_two_rows():
    assert rows(2) == [[1], [1, 1]]


def test_three_rows():
    assert rows(3) == [[1], [1, 1], [1, 2, 1]]


def test_five_rows_matches_example():
    assert rows(5) == [
        [1],
        [1, 1],
        [1, 2, 1],
        [1, 3, 3, 1],
        [1, 4, 6, 4, 1],
    ]


def test_row_lengths_equal_row_numbers():
    result = rows(10)
    assert len(result) == 10
    for index, row in enumerate(result):
        assert len(row) == index + 1


def test_edges_of_each_row_are_one():
    for row in rows(8):
        assert row[0] == 1
        assert row[-1] == 1


def test_sixth_row_interior_values():
    assert rows(6)[5] == [1, 5, 10, 10, 5, 1]


def test_tenth_row_values():
    assert rows(10)[9] == [1, 9, 36, 84, 126, 126, 84, 36, 9, 1]


def test_each_interior_value_is_sum_of_two_above():
    result = rows(9)
    for r in range(2, len(result)):
        for c in range(1, len(result[r]) - 1):
            assert result[r][c] == result[r - 1][c - 1] + result[r - 1][c]


def test_negative_row_count_raises_value_error_with_message():
    with pytest.raises(ValueError) as excinfo:
        rows(-1)
    assert str(excinfo.value).strip() != ""


def test_large_negative_row_count_raises_value_error_with_message():
    with pytest.raises(ValueError) as excinfo:
        rows(-5)
    assert str(excinfo.value).strip() != ""
