def days_in(y, m):
    if m == 2:
        return 29 if y % 4 == 0 else 28
    return 30 if m in (4, 6, 9, 11) else 31
