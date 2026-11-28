def largest_product(series, size):
    if size < 0:
        raise ValueError("span must not be negative")
    if not series.isdigit():
        raise ValueError("digits input must only contain digits")
    if size > len(series):
        raise ValueError("span must not exceed string length")

    digits = [int(ch) for ch in series]
    best = None
    for start in range(len(series) - size):
        product = 1
        for d in digits[start:start + size]:
            product *= d
        if best is None or product > best:
            best = product
    return 1 if best is None else best
