from functools import reduce
from operator import mul


def largest_product(series, size):
    if size < 0:
        raise ValueError("span must not be negative")
    if size > len(series):
        raise ValueError("span must not exceed string length")
    if not all("0" <= ch <= "9" for ch in series):
        raise ValueError("digits input must only contain digits")

    best = 0
    for start in range(len(series) - size + 1):
        window = series[start:start + size]
        product = reduce(mul, (int(ch) for ch in window), 1)
        if product > best:
            best = product
    return float(best)
