def round_money(x):
    """
    Rounds a number to 2 decimal places, rounding half to even (banker's rounding).
    This is the standard for financial calculations in many accounting systems.
    However, since the prompt doesn't specify the exact rounding rule (e.g., round half up vs half to even),
    and "resolved" usually implies a standard rounding to 2 decimal places.
    Given it's for an invoice line and finance reconciliation, I will use the built-in `round()` 
    which in Python 3 rounds to the nearest even number for .5 cases (banker's rounding).
    """
    return round(x, 2)
