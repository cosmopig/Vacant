def largest_product(series, size):
    if size < 0:
        raise ValueError("span must not be negative")
    if not all(ch.isdigit() for ch in series):
        raise ValueError("digits input must only contain digits")
    if size > len(series):
        raise ValueError("span must not exceed string length")
    if not size:
        return 0
    best = 0
    for start in range(len(series) - size + 1):
        product = 1
        for ch in series[start:start + size]:
            product *= int(ch)
        if product > best:
            best = product
    return best
