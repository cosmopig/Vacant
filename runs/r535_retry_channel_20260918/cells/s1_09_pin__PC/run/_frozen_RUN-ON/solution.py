def pin(x, low, high):
    if low <= x <= high:
        return x
    elif x < low:
        return low
    else:
        return high
