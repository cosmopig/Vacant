def span(xs):
    """
    Given a list of numbers, report the two ends of it at once: the
    smallest value in the list and the largest value in the list, handed back
    together in one object so that a caller does not have to walk the list twice.

    The list handed in is never without entries.

    Args:
        xs (list): A non-empty list of numbers.

    Returns:
        dict: A dictionary with keys "lo" and "hi".
    """
    lo = xs[0]
    hi = xs[0]
    for x in xs:
        if x < lo:
            lo = x
        elif x > hi:
            hi = x
    return {"lo": lo, "hi": hi}
