def _is_palindrome(number):
    text = str(number)
    return text == text[::-1]


def _palindrome_factor_pairs(min_factor, max_factor):
    if min_factor > max_factor:
        raise ValueError("min must be <= max")
    pairs = {}
    for a in range(min_factor, max_factor):
        for b in range(a, max_factor):
            product = a * b
            if _is_palindrome(product):
                pairs.setdefault(product, []).append((a, b))
    return pairs


def largest(max_factor, min_factor=0):
    pairs = _palindrome_factor_pairs(min_factor, max_factor)
    if not pairs:
        return None, []
    value = max(pairs)
    return value, pairs[value]


def smallest(max_factor, min_factor=0):
    pairs = _palindrome_factor_pairs(min_factor, max_factor)
    if not pairs:
        return None, []
    value = min(pairs)
    return value, pairs[value]
