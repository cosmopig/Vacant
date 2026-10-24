"""Visible acceptance checks for lcb_3496."""
from solution import minNumberOfSeconds  # noqa: F401

def check_1():
    assert minNumberOfSeconds(4, [2, 1, 1]) == 3

def check_2():
    assert minNumberOfSeconds(10, [3, 2, 2, 4]) == 12

def check_3():
    assert minNumberOfSeconds(5, [1]) == 15
