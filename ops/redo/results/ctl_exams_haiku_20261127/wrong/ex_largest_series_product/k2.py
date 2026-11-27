from functools import reduce


def largest_product(series, size):
    if size < 0:
        raise ValueError("span must not be negative")
    if not all(c in "0123456789" for c in series):
        raise ValueError("digits input must only contain digits")
    if size >= len(series):
        raise ValueError("span must not exceed string length")
    digits = [int(c) for c in series]
    products = []
    for i in range(len(digits) - size + 1):
        window = digits[i:i + size]
        products.append(reduce(lambda a, b: a * b, window, 1))
    return max(products)
