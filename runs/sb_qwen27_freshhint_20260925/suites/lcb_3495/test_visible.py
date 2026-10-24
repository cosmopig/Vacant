"""Visible acceptance checks for lcb_3495."""
from solution import resultsArray  # noqa: F401

def check_1():
    assert resultsArray([[1, 2], [3, 4], [2, 3], [-3, 0]], 2) == [-1, 7, 5, 3]

def check_2():
    assert resultsArray([[5, 5], [4, 4], [3, 3]], 1) == [10, 8, 6]
