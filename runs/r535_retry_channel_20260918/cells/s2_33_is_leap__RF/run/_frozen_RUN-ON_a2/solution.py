def is_leap(y):
    """
    Returns True if y is a leap year, False otherwise.
    A year is a leap year if it is divisible by 4, except for years
    divisible by 100, unless they are also divisible by 400.
    """
    if y % 400 == 0:
        return True
    if y % 100 == 0:
        return False
    if y % 4 == 0:
        return True
    return False
