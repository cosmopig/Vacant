def range_sum(a, b):
    if a > b:
        raise ValueError("a above b")
    return sum(range(a, b + 1))
