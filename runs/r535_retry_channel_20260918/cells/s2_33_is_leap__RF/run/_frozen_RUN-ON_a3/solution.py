def is_leap(y):
    """
    Returns True if y is a leap year, False otherwise.
    A year is a leap year if it is divisible by 4, except for years
    divisible by 100, unless they are also divisible by 400.
    """
    # The input 'y' is converted to a number by code that does no checking of its own.
    # This means y could be an int or a float (e.g., 2000.0).
    # We should treat it as an integer for the modulo operations.
    try:
        year = int(y)
    except (ValueError, TypeError):
        return False

    if year % 400 == 0:
        return True
    if year % 100 == 0:
        return False
    if year % 4 == 0:
        return True
    return False
