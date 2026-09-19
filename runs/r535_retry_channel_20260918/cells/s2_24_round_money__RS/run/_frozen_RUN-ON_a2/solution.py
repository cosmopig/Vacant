def round_money(x):
    """
    Rounds a number to 2 decimal places, rounding half to even (banker's rounding).
    This is the standard for financial calculations in many accounting systems.
    However, since the prompt doesn't specify the exact rounding rule (e.g., round half up vs half to even),
    and 'resolved cents' usually implies a standard rounding to 2 decimal places.
    I will use the built-in `round()` function which implements "round half to even" in Python 3.
    """
    return round(x, 2)
