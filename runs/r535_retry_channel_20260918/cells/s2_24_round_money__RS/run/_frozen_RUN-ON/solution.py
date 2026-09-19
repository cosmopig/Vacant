def round_money(x):
    """
    Rounds a number to two decimal places using the standard rounding method.
    In Python 3, the built-in round() function rounds to the nearest even number for .5 cases (banker's rounding),
    which is common in financial applications.
    """
    return float(round(x, 2))
