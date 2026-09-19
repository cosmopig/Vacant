def round_money(x):
    """
    Rounds a number to 2 decimal places using standard rounding.
    In Python 3, the built-in round() function rounds half to even (banker's rounding),
    which is commonly used in financial applications to minimize cumulative errors.
    """
    return float(round(x, 2))
