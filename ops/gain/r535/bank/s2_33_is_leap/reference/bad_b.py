def is_leap(y):
    if y < 1:
        raise ValueError("year must be at least 1")
    return y % 4 == 0
