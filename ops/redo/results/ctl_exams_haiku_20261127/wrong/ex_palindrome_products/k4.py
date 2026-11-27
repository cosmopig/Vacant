def is_palindrome(n):
    s = str(n)
    return s == s[::-1]


def largest(max_factor, min_factor=0):
    if min_factor > max_factor:
        raise ValueError("min must be <= max")
    best = None
    factors = []
    for i in range(max_factor, min_factor - 1, -1):
        if best is not None and i * max_factor <= best:
            break
        for j in range(max_factor, i - 1, -1):
            p = i * j
            if best is not None and p < best:
                break
            if is_palindrome(p):
                if best is None or p > best:
                    best = p
                    factors = [(i, j)]
                elif p == best:
                    factors.append((i, j))
    return best, sorted(factors)


def smallest(max_factor, min_factor=0):
    if min_factor > max_factor:
        raise ValueError("min must be <= max")
    best = None
    factors = []
    for i in range(min_factor, max_factor + 1):
        if best is not None and i * i > best:
            break
        for j in range(i, max_factor + 1):
            p = i * j
            if best is not None and p > best:
                break
            if is_palindrome(p):
                if best is None or p < best:
                    best = p
                    factors = [(i, j)]
                elif p == best:
                    factors.append((i, j))
    return best, sorted(factors)
