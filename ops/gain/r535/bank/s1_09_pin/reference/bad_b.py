def pin(x, low, high):
    if low <= x <= high:
        return None
    return low if x < low else high
