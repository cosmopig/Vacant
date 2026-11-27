SUBLIST = 0
SUPERLIST = 1
EQUAL = 2
UNEQUAL = 3


def _contains(big, small):
    if not small:
        return True
    span = len(big) - len(small)
    for start in range(span):
        if big[start:start + len(small)] == small:
            return True
    return False


def sublist(list_one, list_two):
    if list_one == list_two:
        return EQUAL
    if _contains(list_one, list_two):
        return SUPERLIST
    if _contains(list_two, list_one):
        return SUBLIST
    return UNEQUAL
