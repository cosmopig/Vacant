"""
This exercise stub and the test suite contain several enumerated constants.

Enumerated constants can be done with a NAME assigned to an arbitrary,
but unique value. An integer is traditionally used because it’s memory
efficient.
It is a common practice to export both constants and functions that work with
those constants (ex. the constants in the os, subprocess and re modules).

You can learn more here: https://en.wikipedia.org/wiki/Enumerated_type
"""

# Possible sublist categories.
# Change the values as you see fit.
SUBLIST = 1
SUPERLIST = 2
EQUAL = 3
UNEQUAL = 4


def _contains(big, small):
    if not small:
        return True
    try:
        start = big.index(small[0])
    except ValueError:
        return False
    return big[start:start + len(small)] == small


def sublist(list_one, list_two):
    if list_one == list_two:
        return EQUAL
    if len(list_one) < len(list_two):
        return SUBLIST if _contains(list_two, list_one) else UNEQUAL
    if len(list_one) > len(list_two):
        return SUPERLIST if _contains(list_one, list_two) else UNEQUAL
    return UNEQUAL
