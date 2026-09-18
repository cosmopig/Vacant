def pin(x, low, high):
    if x < low:
        return high
    if x > high:
        return low
    return x
