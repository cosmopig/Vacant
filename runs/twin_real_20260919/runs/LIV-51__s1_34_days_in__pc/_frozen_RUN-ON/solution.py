def days_in(y, m):
    if m in [1, 3, 5, 7, 8, 10, 12]:
        return 31
    elif m == 4 or m == 6 or m == 9 or m == 11:
        return 30
    elif m == 2:
        if (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0):
            return 29
        else:
            return 28
    return 0
