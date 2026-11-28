SUBLIST = 1
SUPERLIST = 2
EQUAL = 3
UNEQUAL = 4


def _is_subsequence(small, big):
    it = iter(big)
    return all(item in it for item in small)


def sublist(list_one, list_two):
    if list_one == list_two:
        return EQUAL
    if len(list_one) < len(list_two) and _is_subsequence(list_one, list_two):
        return SUBLIST
    if len(list_one) > len(list_two) and _is_subsequence(list_two, list_one):
        return SUPERLIST
    return UNEQUAL
