def days_in(y, m):
    if m == 2:
        leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
        return 29 if leap else 28
    return 30 if m in (4, 6, 9, 11) else 31
