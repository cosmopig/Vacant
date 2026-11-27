from itertools import combinations as _combinations


def combinations(target, size, exclude):
    digits = [d for d in range(9, 0, -1) if d not in exclude]
    result = []
    for combo in _combinations(digits, size):
        if sum(combo) == target:
            result.append(list(combo))
    return sorted(result)
