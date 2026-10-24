"""Visible acceptance checks for lcb_3485."""
from solution import maxPossibleScore  # noqa: F401

def check_1():
    assert maxPossibleScore([6, 0, 3], 2) == 4

def check_2():
    assert maxPossibleScore([2, 6, 13, 13], 5) == 5
