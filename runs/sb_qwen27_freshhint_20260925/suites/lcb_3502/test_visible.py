"""Visible acceptance checks for lcb_3502."""
from solution import numberOfSubstrings  # noqa: F401

def check_1():
    assert numberOfSubstrings('abacb', 2) == 4

def check_2():
    assert numberOfSubstrings('abcde', 1) == 15
