from itertools import combinations as _combinations


def combinations(target, size, exclude):
    digits = [d for d in range(0, 10) if d not in exclude]
    return [list(c) for c in _combinations(digits, size) if sum(c) == target]
