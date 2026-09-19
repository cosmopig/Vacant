def leap_year(y):
    if y < 1:
        raise ValueError("year must be at least 1")
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
