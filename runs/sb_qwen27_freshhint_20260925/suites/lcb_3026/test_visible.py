"""Visible acceptance checks for lcb_3026."""
from solution import minimumPossibleSum  # noqa: F401

def check_1():
    assert minimumPossibleSum(2, 3) == 4

def check_2():
    assert minimumPossibleSum(3, 3) == 8

def check_3():
    assert minimumPossibleSum(1, 1) == 1
