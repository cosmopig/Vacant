"""Visible acceptance checks for lcb_3487."""
from solution import maxRemovals  # noqa: F401

def check_1():
    assert maxRemovals('abbaa', 'aba', [0, 1, 2]) == 1

def check_2():
    assert maxRemovals('bcda', 'd', [0, 3]) == 2

def check_3():
    assert maxRemovals('dda', 'dda', [0, 1, 2]) == 0

def check_4():
    assert maxRemovals('yeyeykyded', 'yeyyd', [0, 2, 3, 4]) == 2
