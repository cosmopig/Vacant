from itertools import combinations as _combinations

_cache = {}


def combinations(target, size, exclude):
    key = (target, size)
    if key in _cache:
        return _cache[key]

    excluded = set(exclude)
    result = []
    for combo in _combinations(range(1, 10), size):
        if sum(combo) != target:
            continue
        if excluded.intersection(combo):
            continue
        result.append(list(combo))

    result.sort()
    _cache[key] = result
    return result
