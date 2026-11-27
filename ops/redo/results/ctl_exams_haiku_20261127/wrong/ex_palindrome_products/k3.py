def _is_palindrome(number):
    text = str(number)
    return text == text[::-1]


def _search(min_factor, max_factor, prefer):
    if min_factor > max_factor:
        raise ValueError("min must be <= max")

    best = None
    pairs = []
    for a in range(min_factor, max_factor + 1):
        for b in range(a, max_factor + 1):
            product = a * b
            if not _is_palindrome(product):
                continue
            if best is None or prefer(product, best):
                best = product
                pairs = [(a, b)]
            elif product == best:
                pairs.append((a, b))
    return best, pairs


def largest(min_factor=0, max_factor=None):
    if max_factor is None:
        raise ValueError("max_factor is required")
    value, pairs = _search(min_factor, max_factor, lambda p, best: p > best)
    return value, iter(pairs)


def smallest(min_factor=0, max_factor=None):
    if max_factor is None:
        raise ValueError("max_factor is required")
    value, pairs = _search(min_factor, max_factor, lambda p, best: p < best)
    return value, iter(pairs)
