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
    n = len(small)
    for i in range(len(big) - n + 1):
        if big[i:i + n] == small:
            return True
    return False


def sublist(list_one, list_two):
    if list_one == list_two:
        return EQUAL
    if len(list_one) > len(list_two):
        return SUPERLIST if _contains(list_one, list_two) else UNEQUAL
    if _contains(list_two, list_one):
        return SUPERLIST
    return UNEQUAL
